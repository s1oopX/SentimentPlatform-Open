<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getAnalysisResultDetail } from '@/api/analysis'
import ErrorRetryAlert from '@/components/ErrorRetryAlert.vue'
import SafeHtml from '@/components/SafeHtml.vue'
import { ArrowLeft, Top, Bottom, Minus, Download, CircleCheck } from '@element-plus/icons-vue'
import { highlightKeywords } from '@/utils/highlightKeywords'

/**
 * @typedef {{
 *   id?: number
 *   sentiment?: number
 *   sentiment_display?: string
 *   confidence?: number
 *   keywords?: any[]
 *   comment_id?: number
 *   comment_content?: string
 *   project_name?: string
 *   category?: string
 *   created_at?: string
 *   analyst_note?: string
 *   [key: string]: any
 * }} ResultDetailData
 */
const route = useRoute()
const router = useRouter()
const loading = ref(true)
/** @type {import('vue').Ref<ResultDetailData | null>} */ const result = ref(null)
const errorMessage = ref('')

const padDatePart = (value) => String(value).padStart(2, '0')

const toLocalDateString = (value) => {
  if (!value) {
    return null
  }

  if (typeof value === 'string') {
    const directDateMatch = value.match(/^(\d{4})-(\d{2})-(\d{2})/)
    if (directDateMatch) {
      return `${directDateMatch[1]}-${directDateMatch[2]}-${directDateMatch[3]}`
    }
  }

  const parsedDate = new Date(value)
  if (Number.isNaN(parsedDate.getTime())) {
    return null
  }

  return `${parsedDate.getFullYear()}-${padDatePart(parsedDate.getMonth() + 1)}-${padDatePart(parsedDate.getDate())}`
}

const toLocalDateTimeText = (value) => {
  const localDateString = toLocalDateString(value)
  if (!localDateString) {
    return '--'
  }

  const parsedDate = new Date(value)
  if (Number.isNaN(parsedDate.getTime())) {
    return localDateString
  }

  return parsedDate.toLocaleString('zh-CN')
}

const isPositive = computed(() => result.value?.sentiment === 1)
const isNegative = computed(() => result.value?.sentiment === -1)
const sentimentLabel = computed(() => {
  if (!result.value) return ''
  if (result.value.sentiment_display) return result.value.sentiment_display
  if (isPositive.value) return '积极'
  if (isNegative.value) return '消极'
  return '中性'
})
const confidenceText = computed(() =>
  typeof result.value?.confidence === 'number'
    ? `${(result.value.confidence * 100).toFixed(2)}%`
    : '--'
)
const createdAtText = computed(() => toLocalDateTimeText(result.value?.created_at))
const highlightedContent = computed(() =>
  highlightKeywords(result.value?.comment_content ?? '', result.value?.keywords ?? [])
)

const reportPrefillQuery = computed(() => {
  const createdDate = toLocalDateString(result.value?.created_at)

  if (!createdDate) {
    return null
  }

  const query = {
    start_date: createdDate,
    prefill_source: 'result_detail',
  }

  if (result.value?.category) {
    query.category = result.value.category
  }

  return query
})

const canPrefillReport = computed(() => Boolean(reportPrefillQuery.value))

const goBackToHistory = () => {
  router.push({ name: 'History' })
}

const fetchDetail = async (id) => {
  loading.value = true
  result.value = null
  errorMessage.value = ''
  try {
    const res = await getAnalysisResultDetail(id)
    result.value = res.data || null
    if (!result.value) {
      errorMessage.value = '未找到相关分析记录'
    }
  } catch (/** @type {any} */ err) {
    result.value = null
    errorMessage.value = err?.response?.data?.error || '分析结果加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

const handleExport = () => {
  if (!reportPrefillQuery.value) {
    return
  }

  router.push({ path: '/user/reports', query: reportPrefillQuery.value })
}

watch(
  () => route.params.id,
  async (nextId) => {
    if (nextId) {
      await fetchDetail(nextId)
      return
    }

    loading.value = false
    result.value = null
    errorMessage.value = '未找到相关分析记录'
  },
  { immediate: true }
)
</script>

<template>
  <div v-loading="loading" class="max-w-4xl mx-auto space-y-6">
    <ErrorRetryAlert
      :message="errorMessage"
      :on-retry="route.params.id ? () => fetchDetail(route.params.id) : undefined"
      :loading="loading"
    />

    <!-- Title Section -->
    <div v-if="result" class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
      <div class="space-y-3">
        <button
          type="button"
          class="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-600 shadow-sm transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700"
          @click="goBackToHistory"
        >
          <el-icon><ArrowLeft /></el-icon>
          返回分析历史
        </button>
        <div>
          <h1 class="text-3xl font-bold text-slate-900">分析详情</h1>
          <p class="text-slate-500 mt-2 text-sm">
            ID: {{ result.id }} | 分析时间: {{ createdAtText }}
          </p>
        </div>
      </div>
      <el-button
        data-testid="result-export-report"
        type="primary"
        class="!rounded-lg"
        :disabled="!canPrefillReport"
        @click="handleExport"
      >
        <el-icon class="mr-2"><Download /></el-icon>
        导出报告
      </el-button>
    </div>

    <div v-if="result" class="space-y-6">
      <p v-if="!canPrefillReport" class="text-sm text-slate-500">
        当前结果缺少可用时间信息，无法直接预填报表条件
      </p>

      <!-- 情感结果卡片 -->
      <div class="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div class="px-6 py-4 border-b border-slate-100">
          <h3 class="font-bold text-slate-900">情感分析结果</h3>
        </div>
        <div class="p-6">
          <div class="flex items-center gap-6 p-6 bg-slate-50 rounded-xl border border-slate-100">
            <div
              class="h-16 w-16 rounded-xl bg-white shadow-sm flex items-center justify-center flex-shrink-0"
            >
              <el-icon
                :class="
                  isPositive ? 'text-green-600' : isNegative ? 'text-red-500' : 'text-slate-500'
                "
                :size="32"
              >
                <Top v-if="isPositive" />
                <Bottom v-else-if="isNegative" />
                <Minus v-else />
              </el-icon>
            </div>
            <div class="flex-1">
              <p class="text-xs font-medium text-slate-500 mb-2 uppercase tracking-wider">
                情感倾向
              </p>
              <div class="flex items-center gap-3">
                <el-tag
                  :type="isPositive ? 'success' : isNegative ? 'danger' : 'info'"
                  size="large"
                  class="!px-4 !py-1 !text-base !font-semibold"
                >
                  {{ sentimentLabel }}
                </el-tag>
                <span class="text-lg text-slate-700">
                  置信度:
                  <span class="font-bold text-slate-900">{{ confidenceText }}</span>
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div class="px-6 py-4 border-b border-slate-100">
          <h3 class="font-bold text-slate-900">业务上下文</h3>
        </div>
        <div class="p-6">
          <div class="grid grid-cols-2 gap-y-6 gap-x-4">
            <div v-if="result.category">
              <p class="text-xs text-slate-500 mb-1">分类</p>
              <p class="text-base font-medium text-slate-900">
                {{ result.category }}
              </p>
            </div>
            <div v-if="result.project_name">
              <p class="text-xs text-slate-500 mb-1">所属项目</p>
              <p class="text-base font-medium text-slate-900">
                {{ result.project_name }}
              </p>
            </div>
            <div v-if="result.source">
              <p class="text-xs text-slate-500 mb-1">来源</p>
              <p class="text-base font-medium text-slate-900">
                {{ result.source }}
              </p>
            </div>
            <div v-if="result.is_priority !== undefined">
              <p class="text-xs text-slate-500 mb-1">重点标记</p>
              <p class="text-base font-medium text-slate-900">
                {{ result.is_priority ? '是' : '否' }}
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- 关键词卡片 -->
      <div
        v-if="result.keywords?.length"
        class="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden"
      >
        <div class="px-6 py-4 border-b border-slate-100">
          <h3 class="font-bold text-slate-900">高频关键词</h3>
        </div>
        <div class="p-6 flex flex-wrap gap-2">
          <div
            v-for="(keyword, index) in result.keywords"
            :key="index"
            class="px-3 py-1.5 bg-slate-100 text-slate-700 rounded-lg text-sm font-medium border border-slate-200"
          >
            {{ keyword }}
          </div>
        </div>
      </div>

      <!-- 原始内容卡片 -->
      <div class="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div class="px-6 py-4 border-b border-slate-100">
          <h3 class="font-bold text-slate-900">原始内容</h3>
        </div>
        <div class="p-6">
          <div class="p-4 bg-slate-50 rounded-xl border border-slate-100">
            <SafeHtml
              tag="p"
              :html="highlightedContent"
              class="text-slate-800 text-base leading-relaxed whitespace-pre-wrap"
            />
          </div>
        </div>
      </div>
    </div>

    <div
      v-else-if="!loading"
      class="text-center py-20 bg-white rounded-xl border border-dashed border-slate-300"
    >
      <el-icon class="text-slate-300 mb-4" :size="48"><CircleCheck /></el-icon>
      <p class="text-slate-500">{{ errorMessage || '未找到相关分析记录' }}</p>
      <button
        type="button"
        class="mt-6 inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-600 shadow-sm transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700"
        @click="goBackToHistory"
      >
        <el-icon><ArrowLeft /></el-icon>
        返回分析历史
      </button>
    </div>
  </div>
</template>

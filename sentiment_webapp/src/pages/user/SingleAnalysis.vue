<script setup>
import { computed, reactive, ref } from 'vue'
import { performSingleAnalysis } from '@/api/analysis'
import { ElMessage } from 'element-plus'
import { useStorage, onKeyStroke } from '@vueuse/core'
import { extractErrorMessage } from '@/api/request'
import { MagicStick, TrendCharts, CircleCheck, Minus, Bottom } from '@element-plus/icons-vue'
import { highlightKeywords } from '@/utils/highlightKeywords'
import ErrorRetryAlert from '@/components/ErrorRetryAlert.vue'
import SafeHtml from '@/components/SafeHtml.vue'

/**
 * @typedef {{
 *   sentiment?: number
 *   sentiment_display?: string
 *   confidence?: number
 *   keywords?: any[]
 *   comment_id?: number
 *   comment_content?: string
 *   created_at?: string
 *   [key: string]: any
 * }} SingleAnalysisResult
 */
const loading = ref(false)
/** @type {import('vue').Ref<SingleAnalysisResult | null>} */ const result = ref(null)
const errorMessage = ref('')

const form = reactive({
  text: useStorage('sentiment-single-text-draft', ''),
})

onKeyStroke(['Enter'], (e) => {
  if (e.ctrlKey || e.metaKey) {
    e.preventDefault()
    if (form.text) handleAnalyze()
  }
})

const buildPayload = () => {
  return {
    content: String(form.text || '').trim(),
  }
}

const isPositive = computed(() => result.value?.sentiment === 1)
const isNegative = computed(() => result.value?.sentiment === -1)
const isNeutral = computed(() => result.value?.sentiment === 0)
const sentimentLabel = computed(() => {
  if (!result.value) return ''
  if (result.value.sentiment_display) return result.value.sentiment_display
  if (isPositive.value) return '积极'
  if (isNegative.value) return '消极'
  if (isNeutral.value) return '中性'
  return String(result.value.sentiment ?? '')
})
const confidenceText = computed(() =>
  typeof result.value?.confidence === 'number'
    ? `${(result.value.confidence * 100).toFixed(2)}%`
    : '--'
)
const highlightedContent = computed(() =>
  highlightKeywords(result.value?.comment_content ?? '', result.value?.keywords ?? [])
)

const handleAnalyze = async () => {
  const payload = buildPayload()
  if (!payload.content) {
    ElMessage.warning('请输入分析内容')
    return
  }
  loading.value = true
  result.value = null
  errorMessage.value = ''
  try {
    const res = await performSingleAnalysis(payload)
    result.value = res.data || null
    if (!result.value) {
      errorMessage.value = '分析结果为空，请稍后重试'
      ElMessage.error(errorMessage.value)
      return
    }
    ElMessage.success('分析完成')
    form.text = ''
  } catch (/** @type {any} */ err) {
    result.value = null
    errorMessage.value = extractErrorMessage(err, '分析请求失败，请稍后重试')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="max-w-4xl mx-auto space-y-8">
    <div class="space-y-2">
      <h1 class="text-3xl font-bold text-slate-900">单条分析</h1>
      <p class="text-slate-600 text-lg">输入评论内容进行情感分析</p>
    </div>

    <ErrorRetryAlert :message="errorMessage" :on-retry="handleAnalyze" :loading="loading" />

    <!-- Input Card -->
    <div class="bg-white rounded-xl border border-slate-200 shadow-sm">
      <div class="p-6 border-b border-slate-100">
        <h3 class="flex items-center gap-2 text-xl font-semibold text-slate-900">
          <el-icon class="text-blue-600"><MagicStick /></el-icon>
          输入分析内容
        </h3>
        <p class="text-base text-slate-500 mt-1">请输入您想要分析的评论或文本</p>
      </div>

      <div class="p-6 space-y-6">
        <div class="space-y-3">
          <label class="block text-sm font-semibold text-slate-900">
            <span class="text-red-500 mr-1">*</span>分析内容
          </label>
          <textarea
            v-model="form.text"
            rows="8"
            class="flex w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-base text-slate-900 placeholder:text-slate-400 leading-relaxed focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent transition-all duration-200 resize-y"
            placeholder="例如：这款产品真的很好用，体验不错，强烈推荐！ (支持 Ctrl+Enter 快捷提交)"
          ></textarea>
        </div>

        <el-button
          type="primary"
          class="w-full gap-2 !h-12 !text-base !font-semibold !rounded-xl shadow-md hover:shadow-lg transition-all"
          :loading="loading"
          @click="handleAnalyze"
        >
          <el-icon><MagicStick /></el-icon>
          {{ loading ? '分析中...' : '开始分析' }}
        </el-button>
      </div>
    </div>

    <!-- Analysis Result -->
    <div v-if="result" class="bg-white rounded-xl border border-green-200 shadow-sm">
      <div
        class="p-6 bg-gradient-to-r from-green-50 to-blue-50 border-b border-green-100 rounded-t-xl"
      >
        <h3 class="flex items-center gap-2 text-xl font-bold text-green-900">
          <el-icon class="text-green-600"><CircleCheck /></el-icon>
          分析结果
        </h3>
      </div>

      <div class="p-6 space-y-8">
        <div
          class="flex items-center gap-5 p-6 bg-gradient-to-r from-slate-50 to-slate-100/50 rounded-xl border border-slate-200"
        >
          <div
            class="h-16 w-16 rounded-xl bg-white shadow-sm flex items-center justify-center flex-shrink-0"
          >
            <el-icon
              :class="
                isPositive ? 'text-green-600' : isNegative ? 'text-red-500' : 'text-slate-500'
              "
              :size="32"
            >
              <TrendCharts v-if="isPositive" />
              <Bottom v-else-if="isNegative" />
              <Minus v-else />
            </el-icon>
          </div>
          <div class="flex-1 space-y-2">
            <p class="text-sm font-medium text-slate-600">情感倾向</p>
            <div class="flex items-center gap-3">
              <el-tag
                :type="isPositive ? 'success' : isNegative ? 'danger' : 'info'"
                size="large"
                class="!px-4 !text-base"
              >
                {{ sentimentLabel }}
              </el-tag>
              <span class="text-sm text-slate-500 font-medium pt-1">
                置信度: {{ confidenceText }}
              </span>
            </div>
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div class="p-4 bg-slate-50 rounded-xl border border-slate-200">
            <p class="text-sm font-semibold text-slate-600 mb-2">分析时间</p>
            <p class="text-base text-slate-900 font-medium">
              {{ result.created_at ? new Date(result.created_at).toLocaleString('zh-CN') : '-' }}
            </p>
          </div>
        </div>

        <div v-if="result.keywords?.length">
          <p class="text-sm font-semibold text-slate-600 mb-3">关键情感词</p>
          <div class="flex flex-wrap gap-2">
            <div
              v-for="(keyword, index) in result.keywords"
              :key="index"
              class="px-3 py-1.5 bg-yellow-100 text-yellow-800 rounded-lg text-sm font-medium border border-yellow-200"
            >
              {{ keyword }}
            </div>
          </div>
        </div>

        <div>
          <p class="text-sm font-semibold text-slate-600 mb-3">原始内容（关键词已高亮）</p>
          <div class="p-5 bg-slate-50 rounded-xl border border-slate-200">
            <SafeHtml
              tag="p"
              :html="highlightedContent"
              class="text-slate-900 leading-relaxed whitespace-pre-wrap"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

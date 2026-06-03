<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import ErrorRetryAlert from '@/components/ErrorRetryAlert.vue'
import { useRefreshOnActivated } from '@/composables/useRefreshOnActivated'
import { useRouter } from 'vue-router'
import { Clock, Document, Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

import { usePageSizeReset } from '@/composables/usePagination'
import { getAnalysisHistory, getAnalysisHistorySummary } from '@/api/analysis'
import { generateReport } from '@/api/report'
import { extractErrorMessage } from '@/api/request'
import KeywordStatList from '@/components/KeywordStatList.vue'
import WordCloudChart from '@/components/WordCloudChart.vue'
import MetricBarChart from '@/components/MetricBarChart.vue'
import SentimentChart from '@/components/SentimentChart.vue'
import TrendChart from '@/components/TrendChart.vue'
import { formatDateTimeText } from '@/utils/dateTime'

const router = useRouter()
const loading = ref(false)
const summaryLoading = ref(false)
const exportingPdf = ref(false)
/**
 * @typedef {{
 *   total?: number
 *   sentiment_counts?: { positive?: number; neutral?: number; negative?: number }
 *   trend?: any
 *   confidence_buckets?: any[]
 *   category_distribution?: any[]
 *   keyword_top?: any[]
 *   [key: string]: any
 * }} HistorySummary
 */
/** @type {import('vue').Ref<any[]>} */ const tableData = ref([])
const total = ref(0)
/** @type {import('vue').Ref<HistorySummary | null>} */ const summary = ref(null)
const errorMessage = ref('')
const summaryError = ref('')

const queryParams = reactive({
  page: 1,
  page_size: 10,
})

const requestParams = computed(() => ({
  page: queryParams.page,
  page_size: queryParams.page_size,
}))
const historySummaryData = computed(
  () => summary.value?.sentiment_counts || { positive: 0, neutral: 0, negative: 0 }
)
const hasSummary = computed(() => Number(summary.value?.total || 0) > 0)

const sentimentTagType = (sentiment) => {
  if (sentiment === 1) return 'success'
  if (sentiment === -1) return 'danger'
  return 'info'
}

const sentimentLabel = (row) =>
  row.sentiment_display || (row.sentiment === 1 ? '积极' : row.sentiment === -1 ? '消极' : '中性')
const formatConfidence = (confidence) =>
  confidence === null || confidence === undefined || confidence === ''
    ? '-'
    : `${(Number(confidence) * 100).toFixed(1)}%`
const normalizeProgress = (progress) => {
  const numericProgress = Number(progress)
  return Number.isFinite(numericProgress)
    ? Math.max(0, Math.min(100, Math.round(numericProgress)))
    : 100
}

const fetchSummary = async () => {
  summaryLoading.value = true
  summaryError.value = ''
  try {
    const res = await getAnalysisHistorySummary(requestParams.value)
    summary.value = res.data || null
  } catch (/** @type {any} */ err) {
    summary.value = null
    summaryError.value = err?.response?.data?.error || '历史图表加载失败，请稍后重试'
  } finally {
    summaryLoading.value = false
  }
}

const fetchHistory = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const res = await getAnalysisHistory(requestParams.value)
    tableData.value = Array.isArray(res?.data?.results) ? res.data.results : []
    total.value = Number(res?.data?.count || tableData.value.length)
  } catch (/** @type {any} */ err) {
    tableData.value = []
    total.value = 0
    errorMessage.value = err?.response?.data?.error || '分析历史加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

const refreshHistoryPage = async () => {
  await Promise.all([fetchHistory(), fetchSummary()])
}

const { handlePageSizeChange } = usePageSizeReset(queryParams, refreshHistoryPage)

const viewDetail = (row) => {
  router.push({ name: 'ResultDetail', params: { id: row.id } })
}

const exportCurrentPeriodPdf = async () => {
  exportingPdf.value = true
  try {
    await generateReport({
      report_type: 'weekly',
      report_format: 'pdf',
    })
    ElMessage.success('PDF 报表任务已提交')
    router.push('/user/reports')
  } catch (/** @type {any} */ err) {
    ElMessage.error(extractErrorMessage(err, 'PDF 报表生成失败，请稍后重试'))
  } finally {
    exportingPdf.value = false
  }
}

onMounted(refreshHistoryPage)

useRefreshOnActivated(refreshHistoryPage)
</script>

<template>
  <div class="space-y-8">
    <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
      <div class="space-y-2">
        <h1 class="text-3xl font-bold text-slate-900">分析历史</h1>
        <p class="text-lg text-slate-600">追踪并检索您过去的全部情感分析记录</p>
      </div>
      <el-button
        type="primary"
        :loading="exportingPdf"
        :disabled="!hasSummary"
        class="!h-11 !rounded-xl !px-5 !font-semibold"
        @click="exportCurrentPeriodPdf"
      >
        <el-icon class="mr-2"><Download /></el-icon>
        本期 PDF
      </el-button>
    </div>

    <ErrorRetryAlert :message="errorMessage" :on-retry="refreshHistoryPage" :loading="loading" />
    <el-alert
      v-if="summaryError"
      :title="summaryError"
      type="warning"
      show-icon
      :closable="false"
    />

    <div class="grid grid-cols-1 gap-6 xl:grid-cols-3">
      <div class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm xl:col-span-2">
        <h2 class="mb-4 text-lg font-semibold text-slate-900">历史趋势</h2>
        <div
          v-if="summaryLoading"
          class="flex h-72 items-center justify-center text-sm text-slate-400"
        >
          正在加载历史图表...
        </div>
        <TrendChart
          v-else-if="hasSummary"
          :dates="summary?.trend?.dates"
          :series="summary?.trend?.series"
          class="h-72"
        />
        <div v-else class="flex h-72 items-center justify-center text-sm text-slate-400">
          暂无趋势数据
        </div>
      </div>

      <div class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 class="mb-4 text-lg font-semibold text-slate-900">情感分布</h2>
        <div v-if="hasSummary" class="h-72">
          <SentimentChart :data="historySummaryData" />
        </div>
        <div v-else class="flex h-72 items-center justify-center text-sm text-slate-400">
          暂无情感分布数据
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 gap-6 xl:grid-cols-2">
      <MetricBarChart
        title="置信度分布"
        :items="summary?.confidence_buckets || []"
        label-key="label"
        value-key="value"
        empty-text="暂无置信度分布数据"
      />
      <MetricBarChart
        title="分类分布"
        :items="summary?.category_distribution || []"
        label-key="category"
        value-key="count"
        empty-text="暂无分类分布数据"
      />
    </div>

    <div class="grid grid-cols-1 gap-6 xl:grid-cols-2">
      <WordCloudChart
        title="高频情感词云"
        :items="summary?.keyword_top || []"
        empty-text="暂无词云数据"
      />
      <KeywordStatList
        title="高频关键词"
        :items="summary?.keyword_top || []"
        empty-text="暂无关键词数据"
      />
    </div>

    <div class="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <el-table v-loading="loading" :data="tableData" class="min-h-[320px]">
        <template #empty>
          <div class="py-10 text-sm text-slate-500">
            {{ errorMessage || '暂无历史记录' }}
          </div>
        </template>
        <el-table-column prop="id" label="记录ID" width="100" />
        <el-table-column label="文本片段" min-width="320">
          <template #default="{ row }">
            <div class="flex items-center gap-3">
              <el-icon class="text-slate-400"><Document /></el-icon>
              <span class="truncate font-medium text-slate-700">{{
                row.comment_content || '-'
              }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="情感定位" width="140" align="center">
          <template #default="{ row }">
            <el-tag :type="sentimentTagType(row.sentiment)">
              {{ sentimentLabel(row) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="置信度" width="120" align="center">
          <template #default="{ row }">
            <span class="font-mono text-slate-500">
              {{ formatConfidence(row.confidence) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="150">
          <template #default="{ row }">
            <div class="space-y-1">
              <span class="text-xs text-slate-500">
                {{ row.analysis_status_display || '已完成' }}
              </span>
              <el-progress
                :percentage="normalizeProgress(row.progress)"
                :stroke-width="6"
                :show-text="false"
                status="success"
              />
            </div>
          </template>
        </el-table-column>
        <el-table-column label="分析时间" width="220">
          <template #default="{ row }">
            <div class="flex items-center gap-2 text-sm text-slate-500">
              <el-icon><Clock /></el-icon>
              {{ formatDateTimeText(row.created_at) }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewDetail(row)">查看详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="flex justify-end border-t border-slate-100 bg-white p-4">
        <el-pagination
          v-model:current-page="queryParams.page"
          v-model:page-size="queryParams.page_size"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="total"
          @size-change="handlePageSizeChange"
          @current-change="refreshHistoryPage"
        />
      </div>
    </div>
  </div>
</template>

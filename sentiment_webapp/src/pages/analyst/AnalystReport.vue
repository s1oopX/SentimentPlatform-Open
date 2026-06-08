<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  DataLine,
  Download,
  Opportunity,
  PieChart,
  Refresh,
  TrendCharts,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

import { exportAnalystReport, getAnalystReport } from '@/api/analysis'
import { buildDateRangeParams, normalizeText } from '@/utils/filterUtils'
import { useRouteFilterSync } from '@/composables/useRouteFilterSync'
import { extractBlobErrorMessage } from '@/utils/blobReader'
import { parseContentDispositionFilename } from '@/utils/contentDisposition'
import { downloadBlob } from '@/utils/download'
import AppPanel from '@/components/AppPanel.vue'
import KeywordStatList from '@/components/KeywordStatList.vue'
import MetricBarChart from '@/components/MetricBarChart.vue'
import PageHeader from '@/components/PageHeader.vue'
import SentimentChart from '@/components/SentimentChart.vue'
import StatCard from '@/components/StatCard.vue'
import TrendChart from '@/components/TrendChart.vue'
import WordCloudChart from '@/components/WordCloudChart.vue'

/**
 * @typedef {{
 *   summary?: Record<string, any>
 *   detail_rows?: any[]
 *   trend?: { dates?: string[]; series?: any[]; detail?: any[] }
 *   range?: { start_date?: string; end_date?: string }
 *   priority_trend?: { dates?: string[]; data?: number[] }
 *   quality_summary?: Record<string, any>
 *   correction_matrix?: any[]
 *   keyword_top?: any[]
 *   sentiment_distribution?: any
 *   category_distribution?: any[]
 *   project_distribution?: any[]
 *   confidence_buckets?: any[]
 *   source_distribution?: any[]
 *   [key: string]: any
 * }} AnalystReportData
 */
const route = useRoute()
const router = useRouter()
/** @type {import('vue').Ref<AnalystReportData | null>} */ const reportData = ref(null)
const routeFilterKeys = ['category', 'start_date', 'end_date']
const exportFormat = ref('xlsx')
const exporting = ref(false)

const buildReportParams = (f) => {
  const params = {}
  const cat = normalizeText(f.category)
  if (cat) params.category = cat
  return { ...params, ...buildDateRangeParams(f) }
}

const {
  filters,
  loading,
  errorMessage,
  applyFilters,
  resetFilters,
  fetchData: fetchReport,
} = useRouteFilterSync({
  router,
  route,
  filterKeys: routeFilterKeys,
  buildParams: buildReportParams,
  fetchFn: (params) => getAnalystReport(params),
  onFetched: (res) => {
    reportData.value = res.data || null
  },
})

const formatNumber = (value) => {
  const number = Number(value)
  return Number.isFinite(number) ? number.toLocaleString('zh-CN') : '0'
}

const formatPercent = (value) => {
  const number = Number(value)
  return Number.isFinite(number) ? `${number.toFixed(1)}%` : '0.0%'
}

const summaryCards = computed(() => {
  const summary = reportData.value?.summary || {}
  return [
    { title: '全部记录', value: summary.total, tone: 'slate', icon: DataLine },
    { title: '积极样本', value: summary.positive, tone: 'blue', icon: TrendCharts },
    { title: '中性样本', value: summary.neutral, tone: 'amber', icon: PieChart },
    { title: '消极样本', value: summary.negative, tone: 'red', icon: PieChart },
    { title: '重点关注', value: summary.priority_count, tone: 'red', icon: Opportunity },
  ]
})

const qualityCards = computed(() => {
  const quality = reportData.value?.quality_summary || {}
  return [
    {
      title: '低置信样本',
      value: quality.low_confidence_count,
      note: `占比 ${formatPercent(quality.low_confidence_rate)}`,
      tone: 'amber',
      icon: DataLine,
    },
    {
      title: '待复核',
      value: quality.pending_review_count,
      note: '低于 70% 且未审核',
      tone: 'red',
      icon: Opportunity,
    },
    {
      title: '已审核',
      value: quality.reviewed_count,
      note: `覆盖率 ${formatPercent(quality.review_rate)}`,
      tone: 'green',
      icon: TrendCharts,
    },
    {
      title: '已审核修正率',
      value: formatPercent(quality.correction_rate),
      note: `${formatNumber(quality.corrected_count)} / ${formatNumber(quality.reviewed_count)} 条审核被修正`,
      tone: 'blue',
      icon: PieChart,
    },
  ]
})

const rangeLabel = computed(() => {
  const startDate = filters.start_date || reportData.value?.range?.start_date
  const endDate = filters.end_date || reportData.value?.range?.end_date
  if (!startDate || !endDate) return ''
  return `${startDate} 至 ${endDate}`
})
const priorityTrendSeries = computed(() => {
  const dates = reportData.value?.priority_trend?.dates || []
  const values = reportData.value?.priority_trend?.data || []
  if (!dates.length) return []
  return [{ name: '重点评论', key: 'priority', data: values }]
})

const correctionMatrixRows = computed(() =>
  Array.isArray(reportData.value?.correction_matrix) ? reportData.value.correction_matrix : []
)

const handleExport = async () => {
  if (exporting.value) return
  exporting.value = true
  try {
    const response = await exportAnalystReport({
      ...buildReportParams(filters),
      format: exportFormat.value,
    })
    const suffix = exportFormat.value === 'csv' ? 'csv' : 'xlsx'
    const filename = parseContentDispositionFilename(
      response?.headers?.['content-disposition'],
      `分析师报表.${suffix}`
    )
    const blob = response?.data instanceof Blob ? response.data : new Blob([response?.data || ''])
    downloadBlob(blob, filename)
    ElMessage.success('报表已开始下载')
  } catch (/** @type {any} */ err) {
    const message = await extractBlobErrorMessage(err, '分析师报表导出失败，请稍后重试')
    ElMessage.error(message)
  } finally {
    exporting.value = false
  }
}
</script>

<template>
  <div class="space-y-6">
    <PageHeader
      title="分析师报表"
      description="回顾全量分析结果与人工审核质量指标"
      :meta="rangeLabel ? `统计范围：${rangeLabel}` : ''"
    >
      <template #actions>
        <div class="flex flex-wrap items-center gap-3">
          <el-select v-model="exportFormat" class="!w-28" size="large">
            <el-option label="XLSX" value="xlsx" />
            <el-option label="CSV" value="csv" />
          </el-select>
          <el-button
            type="primary"
            class="!h-10 !rounded-lg"
            :loading="exporting"
            @click="handleExport"
          >
            <el-icon class="mr-1"><Download /></el-icon>
            导出报表
          </el-button>
          <el-button :icon="Refresh" circle :loading="loading" @click="fetchReport" />
        </div>
      </template>
    </PageHeader>

    <!-- Filters -->
    <div
      class="grid grid-cols-1 items-end gap-4 rounded-xl border border-slate-200 bg-slate-50/50 p-5 md:grid-cols-4"
    >
      <div class="space-y-1.5">
        <label class="text-xs font-semibold text-slate-500 uppercase tracking-wider">分类</label>
        <el-input
          v-model="filters.category"
          placeholder="输入分类名称"
          clearable
          class="el-input-rounded"
          @change="applyFilters"
        />
      </div>
      <div class="space-y-1.5">
        <label class="text-xs font-semibold text-slate-500 uppercase tracking-wider"
          >开始日期</label
        >
        <el-date-picker
          v-model="filters.start_date"
          type="date"
          placeholder="选择日期"
          value-format="YYYY-MM-DD"
          class="!w-full el-input-rounded"
          @change="applyFilters"
        />
      </div>
      <div class="space-y-1.5">
        <label class="text-xs font-semibold text-slate-500 uppercase tracking-wider"
          >结束日期</label
        >
        <el-date-picker
          v-model="filters.end_date"
          type="date"
          placeholder="选择日期"
          value-format="YYYY-MM-DD"
          class="!w-full el-input-rounded"
          @change="applyFilters"
        />
      </div>
      <button
        type="button"
        class="h-[32px] self-end rounded-xl border border-slate-200 px-4 text-sm font-medium text-slate-600 transition hover:border-slate-300 hover:bg-white"
        @click="resetFilters"
      >
        重置
      </button>
    </div>

    <!-- Loading / Error / Empty -->
    <div
      v-if="loading"
      class="flex items-center justify-center rounded-xl border border-dashed border-slate-200 py-20 text-slate-400"
    >
      正在加载报表数据...
    </div>
    <div
      v-else-if="errorMessage"
      class="rounded-xl border border-rose-200 bg-rose-50 p-6 text-sm text-rose-700"
    >
      {{ errorMessage }}
    </div>
    <div
      v-else-if="!reportData"
      class="rounded-xl border border-dashed border-slate-200 py-20 text-center text-slate-400"
    >
      暂无报表数据
    </div>

    <!-- Content -->
    <template v-else>
      <!-- KPI Cards -->
      <div class="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
        <StatCard
          v-for="card in summaryCards"
          :key="card.title"
          :title="card.title"
          :value="formatNumber(card.value)"
          :icon="card.icon"
          :tone="card.tone"
        />
      </div>

      <div class="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard
          v-for="card in qualityCards"
          :key="card.title"
          :title="card.title"
          :value="card.value"
          :note="card.note"
          :icon="card.icon"
          :tone="card.tone"
        />
      </div>

      <!-- Charts Row 1: Sentiment + Trend -->
      <div class="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <AppPanel title="情感分布">
          <SentimentChart :data="reportData.sentiment_distribution" class="h-64" />
        </AppPanel>
        <AppPanel title="情感趋势">
          <TrendChart
            v-if="reportData.trend?.dates?.length"
            :dates="reportData.trend.dates"
            :series="reportData.trend.series"
            class="h-64"
          />
          <p v-else class="py-10 text-center text-sm text-slate-400">暂无趋势数据</p>
        </AppPanel>
      </div>

      <!-- Charts Row 2: Priority Trend + Word Cloud -->
      <div class="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <AppPanel title="重点关注趋势">
          <TrendChart
            v-if="priorityTrendSeries.length"
            :dates="reportData.priority_trend?.dates"
            :series="priorityTrendSeries"
            class="h-64"
          />
          <p v-else class="py-10 text-center text-sm text-slate-400">暂无重点趋势</p>
        </AppPanel>
        <WordCloudChart
          title="高频情感词云"
          :items="reportData.keyword_top || []"
          empty-text="暂无词云数据"
        />
      </div>

      <!-- Bar Charts + Keywords -->
      <div class="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <MetricBarChart
          title="分类分布"
          :items="reportData.category_distribution || []"
          label-key="category"
          value-key="count"
          empty-text="暂无分类分布数据"
        />
        <MetricBarChart
          title="项目分布"
          :items="reportData.project_distribution || []"
          label-key="label"
          value-key="value"
          empty-text="暂无项目分布数据"
        />
        <MetricBarChart
          title="置信度分布"
          :items="reportData.confidence_buckets || []"
          label-key="label"
          value-key="value"
          empty-text="暂无置信度分布数据"
        />
        <KeywordStatList
          title="高频关键词"
          :items="reportData.keyword_top || []"
          empty-text="暂无关键词数据"
        />
      </div>

      <AppPanel title="模型标签与最终标签差异">
        <el-table
          v-if="correctionMatrixRows.length"
          :data="correctionMatrixRows"
          size="small"
          class="w-full"
        >
          <el-table-column prop="model_sentiment_display" label="模型标签" />
          <el-table-column prop="final_sentiment_display" label="最终标签" />
          <el-table-column prop="count" label="数量" width="120" align="right" />
        </el-table>
        <p v-else class="py-10 text-center text-sm text-slate-400">暂无人工修正差异</p>
      </AppPanel>
    </template>
  </div>
</template>

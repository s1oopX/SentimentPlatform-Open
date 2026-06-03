<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ChatLineRound, Filter, View } from '@element-plus/icons-vue'

import { getAnalystOverview } from '@/api/analysis'
import { buildDateRangeParams } from '@/utils/filterUtils'
import { useRouteFilterSync } from '@/composables/useRouteFilterSync'
import KeywordStatList from '@/components/KeywordStatList.vue'
import AppPanel from '@/components/AppPanel.vue'
import WordCloudChart from '@/components/WordCloudChart.vue'
import MetricBarChart from '@/components/MetricBarChart.vue'
import PageHeader from '@/components/PageHeader.vue'
import SentimentChart from '@/components/SentimentChart.vue'
import StatCard from '@/components/StatCard.vue'
import TrendChart from '@/components/TrendChart.vue'

/**
 * @typedef {{
 *   stats?: Record<string, any>
 *   trend?: { dates?: string[]; series?: any[]; detail?: any[] }
 *   range?: { start_date?: string; end_date?: string }
 *   keyword_top?: any[]
 *   sentiment_distribution?: any
 *   category_distribution?: any[]
 *   project_distribution?: any[]
 *   confidence_buckets?: any[]
 *   source_distribution?: any[]
 *   recent_results?: any[]
 *   [key: string]: any
 * }} AnalystOverviewData
 */
const route = useRoute()
const router = useRouter()
/** @type {import('vue').Ref<AnalystOverviewData | null>} */ const overview = ref(null)
const routeFilterKeys = ['start_date', 'end_date']

const { filters, loading, errorMessage, applyFilters, resetFilters } = useRouteFilterSync({
  router,
  route,
  filterKeys: routeFilterKeys,
  buildParams: (f) => buildDateRangeParams(f),
  fetchFn: (params) => getAnalystOverview(params),
  onFetched: (res) => {
    overview.value = res.data || null
  },
})

const formatNumber = (value) => {
  const number = Number(value)
  return Number.isFinite(number) ? number.toLocaleString('zh-CN') : '0'
}

const statsCards = computed(() => {
  const stats = overview.value?.stats || {}
  return [
    {
      title: '全部记录',
      value: stats.total,
      description: '当前筛选范围内的总样本',
      icon: ChatLineRound,
      tone: 'blue',
    },
    {
      title: '积极',
      value: stats.positive,
      description: '正向样本数量',
      icon: View,
      tone: 'green',
    },
    { title: '中性', value: stats.neutral, description: '中性样本数量', icon: View, tone: 'amber' },
    {
      title: '消极',
      value: stats.negative,
      description: '负向样本数量',
      icon: Filter,
      tone: 'red',
    },
    {
      title: '重点关注',
      value: stats.priority_count,
      description: '需要重点跟进的样本',
      icon: Filter,
      tone: 'slate',
    },
  ]
})

const hasTrend = computed(
  () => Array.isArray(overview.value?.trend?.dates) && overview.value.trend.dates.length > 0
)
const recentResultsPreview = computed(() =>
  Array.isArray(overview.value?.recent_results) ? overview.value.recent_results.slice(0, 6) : []
)
const rangeLabel = computed(() => {
  const startDate = filters.start_date || overview.value?.range?.start_date
  const endDate = filters.end_date || overview.value?.range?.end_date
  if (!startDate || !endDate) {
    return ''
  }
  return `${startDate} 至 ${endDate}`
})
</script>

<template>
  <div class="space-y-6">
    <PageHeader
      title="分析师工作台"
      description="数据标注与专家审核"
      :meta="rangeLabel ? `当前默认统计范围：${rangeLabel}` : ''"
    />

    <div
      class="grid grid-cols-1 items-end gap-4 rounded-xl border border-slate-200 bg-slate-50/50 p-6 md:grid-cols-3"
    >
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
        重置筛选
      </button>
    </div>

    <div
      v-if="loading"
      class="flex items-center justify-center rounded-xl border border-dashed border-slate-200 py-20 text-slate-400"
    >
      正在加载分析师概览...
    </div>
    <div
      v-else-if="errorMessage"
      class="rounded-xl border border-rose-200 bg-rose-50 p-6 text-rose-700"
    >
      {{ errorMessage }}
    </div>
    <div
      v-else-if="!overview"
      class="rounded-xl border border-dashed border-slate-200 py-20 text-center text-slate-400"
    >
      暂无分析师概览数据
    </div>

    <template v-else>
      <!-- KPI Cards -->
      <div class="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
        <StatCard
          v-for="card in statsCards"
          :key="card.title"
          :title="card.title"
          :value="formatNumber(card.value)"
          :note="card.description"
          :icon="card.icon"
          :tone="card.tone"
        />
      </div>

      <!-- Charts Row 1: Sentiment + Trend -->
      <div class="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <AppPanel title="情感分布">
          <SentimentChart :data="overview.sentiment_distribution" class="h-64" />
        </AppPanel>
        <AppPanel title="审核趋势">
          <TrendChart
            v-if="hasTrend"
            :dates="overview.trend?.dates"
            :series="overview.trend?.series"
            class="h-64"
          />
          <p v-else class="py-10 text-center text-sm text-slate-400">暂无趋势数据</p>
        </AppPanel>
      </div>

      <!-- Charts Row 2: Bar Charts -->
      <div class="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <MetricBarChart
          title="分类分布"
          :items="overview.category_distribution || []"
          label-key="category"
          value-key="count"
          empty-text="暂无分类分布数据"
        />
        <MetricBarChart
          title="项目分布"
          :items="overview.project_distribution || []"
          label-key="label"
          value-key="value"
          empty-text="暂无项目分布数据"
        />
        <MetricBarChart
          title="置信度分布"
          :items="overview.confidence_buckets || []"
          label-key="label"
          value-key="value"
          empty-text="暂无置信度分布数据"
        />
        <MetricBarChart
          title="来源分布"
          :items="overview.source_distribution || []"
          label-key="label"
          value-key="value"
          empty-text="暂无来源分布数据"
        />
      </div>

      <!-- Word Cloud + Keywords + Recent -->
      <div class="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <WordCloudChart
          title="高频情感词云"
          :items="overview.keyword_top || []"
          empty-text="暂无词云数据"
        />
        <KeywordStatList
          title="高频关键词"
          :items="overview.keyword_top || []"
          empty-text="暂无关键词数据"
        />
        <AppPanel title="最近审核">
          <div v-if="recentResultsPreview.length" class="space-y-2">
            <div
              v-for="item in recentResultsPreview"
              :key="item.id"
              class="rounded-lg border border-slate-100 px-3 py-2.5 text-sm text-slate-600 line-clamp-2"
            >
              {{ item.comment_content }}
            </div>
          </div>
          <p v-else class="py-10 text-center text-sm text-slate-400">暂无最近审核</p>
        </AppPanel>
      </div>
    </template>
  </div>
</template>

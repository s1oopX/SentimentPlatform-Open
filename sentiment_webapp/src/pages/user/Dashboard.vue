<script setup>
import { computed, onMounted, ref } from 'vue'
import ErrorRetryAlert from '@/components/ErrorRetryAlert.vue'
import AppPanel from '@/components/AppPanel.vue'
import {
  Document,
  Top,
  Minus,
  Bottom,
  ArrowRight,
  FolderOpened,
  Clock,
} from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'

import { getAnalysisHistorySummary } from '@/api/analysis'
import KeywordStatList from '@/components/KeywordStatList.vue'
import WordCloudChart from '@/components/WordCloudChart.vue'
import MetricBarChart from '@/components/MetricBarChart.vue'
import PageHeader from '@/components/PageHeader.vue'
import SentimentChart from '@/components/SentimentChart.vue'
import StatCard from '@/components/StatCard.vue'
import TrendChart from '@/components/TrendChart.vue'

const router = useRouter()
const loading = ref(true)
const errorMessage = ref('')
/**
 * @typedef {{
 *   total?: number
 *   sentiment_counts?: { positive?: number; neutral?: number; negative?: number }
 *   trend?: any
 *   confidence_buckets?: any[]
 *   category_distribution?: any[]
 *   keyword_top?: any[]
 *   [key: string]: any
 * }} DashboardSummary
 */
/** @type {import('vue').Ref<DashboardSummary | null>} */ const summary = ref(null)

const sentimentCounts = computed(() => summary.value?.sentiment_counts || null)
const hasSummary = computed(() => {
  const total = summary.value?.total
  return typeof total === 'number' && total > 0
})
const chartData = computed(() => ({
  positive: sentimentCounts.value?.positive || 0,
  neutral: sentimentCounts.value?.neutral || 0,
  negative: sentimentCounts.value?.negative || 0,
}))

const summaryCards = computed(() => [
  {
    title: '总分析数',
    value: summary.value?.total,
    icon: Document,
    note: '累计分析记录',
    tone: 'slate',
  },
  {
    title: '积极情感',
    value: sentimentCounts.value?.positive,
    icon: Top,
    note: `占比 ${calcPercent(sentimentCounts.value?.positive, summary.value?.total)}`,
    tone: 'green',
  },
  {
    title: '中性情感',
    value: sentimentCounts.value?.neutral,
    icon: Minus,
    note: `占比 ${calcPercent(sentimentCounts.value?.neutral, summary.value?.total)}`,
    tone: 'orange',
  },
  {
    title: '消极情感',
    value: sentimentCounts.value?.negative,
    icon: Bottom,
    note: `占比 ${calcPercent(sentimentCounts.value?.negative, summary.value?.total)}`,
    tone: 'red',
  },
])

const fetchSummary = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const res = await getAnalysisHistorySummary()
    summary.value = res.data || null
  } catch (/** @type {any} */ err) {
    summary.value = null
    errorMessage.value = err?.response?.data?.error || '分析概览加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

onMounted(fetchSummary)

const formatNumber = (num) => (typeof num === 'number' ? num.toLocaleString('zh-CN') : '--')
const calcPercent = (val, total) =>
  typeof val === 'number' && typeof total === 'number' && total > 0
    ? `${((val / total) * 100).toFixed(1)}%`
    : '--'
</script>

<template>
  <div class="space-y-6">
    <ErrorRetryAlert :message="errorMessage" :on-retry="fetchSummary" :loading="loading" />

    <PageHeader title="欢迎回来" description="这里是您的分析数据总览" />

    <div v-loading="loading" class="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
      <StatCard
        v-for="card in summaryCards"
        :key="card.title"
        :title="card.title"
        :value="formatNumber(card.value)"
        :note="card.note"
        :icon="card.icon"
        :tone="card.tone"
      />
    </div>

    <AppPanel title="快速操作" description="选择您想要进行的操作">
      <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div
          class="group cursor-pointer rounded-xl border border-slate-200 bg-white p-5 transition-all duration-300 hover:-translate-y-1 hover:border-indigo-300 hover:shadow-premium-hover hover:ring-4 ring-indigo-50"
          @click="router.push('/user/analysis')"
        >
          <div class="flex items-center gap-4">
            <div
              class="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-50 to-sky-50 shadow-inner group-hover:from-indigo-100 group-hover:to-sky-100 transition-colors"
            >
              <el-icon class="text-indigo-600" :size="24"><Document /></el-icon>
            </div>
            <div class="flex-1">
              <p
                class="font-bold text-slate-800 tracking-tight transition-colors group-hover:text-indigo-600"
              >
                单条分析
              </p>
              <p class="text-sm text-slate-500 mt-0.5">快速分析单条评论</p>
            </div>
            <div
              class="flex h-8 w-8 items-center justify-center rounded-full bg-slate-50 text-slate-400 opacity-0 transition-all group-hover:opacity-100 group-hover:translate-x-1 group-hover:bg-indigo-50 group-hover:text-indigo-500"
            >
              <el-icon><ArrowRight /></el-icon>
            </div>
          </div>
        </div>

        <div
          class="group cursor-pointer rounded-xl border border-slate-200 bg-white p-5 transition-all duration-300 hover:-translate-y-1 hover:border-violet-300 hover:shadow-premium-hover hover:ring-4 ring-violet-50"
          @click="router.push('/user/analysis/batch')"
        >
          <div class="flex items-center gap-4">
            <div
              class="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-50 to-purple-50 shadow-inner group-hover:from-violet-100 group-hover:to-purple-100 transition-colors"
            >
              <el-icon class="text-violet-600" :size="24"><FolderOpened /></el-icon>
            </div>
            <div class="flex-1">
              <p
                class="font-bold text-slate-800 tracking-tight transition-colors group-hover:text-violet-600"
              >
                批量分析
              </p>
              <p class="text-sm text-slate-500 mt-0.5">上传文件批量分析</p>
            </div>
            <div
              class="flex h-8 w-8 items-center justify-center rounded-full bg-slate-50 text-slate-400 opacity-0 transition-all group-hover:opacity-100 group-hover:translate-x-1 group-hover:bg-violet-50 group-hover:text-violet-500"
            >
              <el-icon><ArrowRight /></el-icon>
            </div>
          </div>
        </div>

        <div
          class="group cursor-pointer rounded-xl border border-slate-200 bg-white p-5 transition-all duration-300 hover:-translate-y-1 hover:border-emerald-300 hover:shadow-premium-hover hover:ring-4 ring-emerald-50"
          @click="router.push('/user/history')"
        >
          <div class="flex items-center gap-4">
            <div
              class="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-50 to-teal-50 shadow-inner group-hover:from-emerald-100 group-hover:to-teal-100 transition-colors"
            >
              <el-icon class="text-emerald-600" :size="24"><Clock /></el-icon>
            </div>
            <div class="flex-1">
              <p
                class="font-bold text-slate-800 tracking-tight transition-colors group-hover:text-emerald-600"
              >
                分析历史
              </p>
              <p class="text-sm text-slate-500 mt-0.5">查看历史分析记录</p>
            </div>
            <div
              class="flex h-8 w-8 items-center justify-center rounded-full bg-slate-50 text-slate-400 opacity-0 transition-all group-hover:opacity-100 group-hover:translate-x-1 group-hover:bg-emerald-50 group-hover:text-emerald-500"
            >
              <el-icon><ArrowRight /></el-icon>
            </div>
          </div>
        </div>
      </div>
    </AppPanel>

    <div class="grid grid-cols-1 gap-6 xl:grid-cols-2">
      <WordCloudChart
        title="热门词云"
        :items="summary?.keyword_top || []"
        empty-text="暂无词云数据"
      />
      <KeywordStatList
        title="热门关键词"
        :items="summary?.keyword_top || []"
        empty-text="暂无可用关键词数据"
      />
    </div>

    <div v-if="hasSummary" class="grid grid-cols-1 gap-6 xl:grid-cols-2">
      <AppPanel title="情感分布">
        <SentimentChart :data="chartData" class="h-72" />
      </AppPanel>
      <AppPanel title="趋势变化">
        <TrendChart :dates="summary?.trend?.dates" :series="summary?.trend?.series" class="h-72" />
      </AppPanel>
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

    <div
      v-else
      class="rounded-xl border border-dashed border-slate-300 bg-white/70 px-8 py-14 text-center text-slate-500"
    >
      <p class="text-base font-semibold text-slate-700">暂无可用情感分布数据</p>
      <p class="mt-2 text-sm">完成分析后，这里会展示趋势、关键词和置信度分布。</p>
    </div>
  </div>
</template>

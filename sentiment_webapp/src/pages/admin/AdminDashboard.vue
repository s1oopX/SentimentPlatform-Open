<script setup>
import { computed, onMounted, ref } from 'vue'
import ErrorRetryAlert from '@/components/ErrorRetryAlert.vue'
import AppPanel from '@/components/AppPanel.vue'
import MetricBarChart from '@/components/MetricBarChart.vue'
import PageHeader from '@/components/PageHeader.vue'
import SentimentChart from '@/components/SentimentChart.vue'
import StatCard from '@/components/StatCard.vue'
import TrendChart from '@/components/TrendChart.vue'
import WordCloudChart from '@/components/WordCloudChart.vue'
import { User, Document, DataLine, ChatLineRound, TrendCharts } from '@element-plus/icons-vue'
import { getAdminDashboardStats } from '@/api/admin'

const loading = ref(false)
const errorMessage = ref('')
/**
 * @typedef {{
 *   total_users?: number
 *   total_analyses?: number
 *   total_comments?: number
 *   total_reports?: number
 *   total_projects?: number
 *   active_models?: number
 *   trend_metrics?: Record<string, any>
 *   sentiment_distribution?: Record<string, any>
 *   role_distribution?: any[]
 *   recent_users?: any[]
 *   recent_analyses?: any[]
 *   keyword_top?: any[]
 *   trend?: any
 *   category_distribution?: any[]
 *   confidence_buckets?: any[]
 *   [key: string]: any
 * }} AdminDashboardSummary
 */
/** @type {import('vue').Ref<AdminDashboardSummary | null>} */ const summary = ref(null)

const cards = computed(() => [
  {
    key: 'total_users',
    title: '系统用户',
    value: summary.value?.total_users,
    suffix: '个注册用户',
    trend: summary.value?.trend_metrics?.total_users,
    icon: User,
    tone: 'blue',
  },
  {
    key: 'total_analyses',
    title: '累计分析',
    value: summary.value?.total_analyses,
    suffix: '条分析记录',
    trend: summary.value?.trend_metrics?.total_analyses,
    icon: DataLine,
    tone: 'indigo',
  },
  {
    key: 'total_comments',
    title: '评论总数',
    value: summary.value?.total_comments,
    suffix: '条原始评论',
    trend: summary.value?.trend_metrics?.total_comments,
    icon: ChatLineRound,
    tone: 'orange',
  },
  {
    key: 'today_analyses',
    title: '今日分析',
    value: summary.value?.today_analyses,
    suffix: '条新增分析',
    trend: summary.value?.trend_metrics?.today_analyses,
    icon: Document,
    tone: 'slate',
  },
  {
    key: 'active_users_7d',
    title: '7日活跃用户',
    value: summary.value?.active_users_7d,
    suffix: '位活跃用户',
    trend: summary.value?.trend_metrics?.active_users_7d,
    icon: TrendCharts,
    tone: 'green',
  },
  {
    key: 'daily_avg_active_users',
    title: '日均活跃用户',
    value: summary.value?.daily_avg_active_users,
    suffix: '人/天',
    trend: summary.value?.trend_metrics?.daily_avg_active_users,
    icon: TrendCharts,
    tone: 'emerald',
  },
])

const formatNumber = (num) => (typeof num === 'number' ? num.toLocaleString('zh-CN') : '--')

const formatTrend = (pct) => {
  if (typeof pct !== 'number') return ''
  const sign = pct >= 0 ? '+' : ''
  return `${sign}${pct}%`
}

const fetchStats = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const res = await getAdminDashboardStats()
    summary.value = res.data || null
  } catch (/** @type {any} */ err) {
    summary.value = null
    errorMessage.value = err?.response?.data?.error || '控制台数据加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

onMounted(fetchStats)
</script>

<template>
  <div class="space-y-6">
    <PageHeader title="控制台总览" description="系统全局状态与资源监控（默认近 7 天统计范围）" />

    <ErrorRetryAlert :message="errorMessage" :on-retry="fetchStats" :loading="loading" />

    <!-- Metric Cards -->
    <div class="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
      <StatCard
        v-for="card in cards"
        :key="card.key"
        :title="card.title"
        :value="formatNumber(card.value)"
        :note="card.suffix"
        :trend="card.trend != null ? formatTrend(card.trend) : undefined"
        :icon="card.icon"
        :tone="card.tone"
        :loading="loading"
      />
    </div>

    <!-- Role Activity + Sentiment Distribution -->
    <div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <MetricBarChart
        :items="summary?.role_action_frequency || []"
        label-key="label"
        value-key="value"
        title="各角色操作频次"
        empty-text="暂无操作频次数据"
      />
      <AppPanel title="情感分布" :padded="false">
        <div class="px-6 pb-4">
          <SentimentChart
            v-if="summary?.sentiment_distribution"
            :data="summary.sentiment_distribution"
            class="h-56"
          />
          <div v-else class="flex h-56 items-center justify-center text-sm text-slate-400">
            暂无情感分布数据
          </div>
        </div>
      </AppPanel>
    </div>

    <!-- Sentiment Trend + Keyword Cloud -->
    <div class="grid grid-cols-1 items-start gap-6 lg:grid-cols-2">
      <AppPanel title="情感趋势" :padded="false">
        <div class="px-6 pb-4">
          <TrendChart
            v-if="summary?.sentiment_trend?.dates?.length"
            :dates="summary.sentiment_trend.dates"
            :series="summary.sentiment_trend.series"
            class="h-56"
          />
          <div v-else class="flex h-56 items-center justify-center text-sm text-slate-400">
            暂无趋势数据
          </div>
        </div>
      </AppPanel>
      <WordCloudChart
        :items="summary?.keyword_top || []"
        item-key="name"
        value-key="value"
        title="高频情感词"
        empty-text="暂无关键词数据"
      />
    </div>
  </div>
</template>

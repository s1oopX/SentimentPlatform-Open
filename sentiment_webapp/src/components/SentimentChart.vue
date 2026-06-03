<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { init, SENTIMENT_PIE_COLORS, GLOBAL_TOOLTIP } from '@/lib/echarts'
import { hasCanvasSupport } from '@/utils/canvasSupport'

const props = defineProps({
  data: {
    type: [Object, Array],
    default: () => ({ positive: 0, neutral: 0, negative: 0 }),
  },
})

/** @type {import('vue').Ref<HTMLDivElement | null>} */ const chartRef = ref(null)
const displayMode = ref('pie')
const chartColors = SENTIMENT_PIE_COLORS
/** @type {any} */ let chartInstance = null
let chartDisabled = false

const normalizedItems = computed(() => {
  if (Array.isArray(props.data)) {
    return props.data.map((item) => ({
      name: item.name || item.label || '未命名',
      value: Number(item.value || item.count || 0),
    }))
  }

  const payload = props.data || {}
  return [
    { name: '积极', value: Number(payload.positive || 0) },
    { name: '中性', value: Number(payload.neutral || 0) },
    { name: '消极', value: Number(payload.negative || 0) },
  ]
})

const axisLabelColor = '#475569'
const splitLineColor = '#e2e8f0'

const initChart = () => {
  if (!chartRef.value || chartDisabled) return
  if (!hasCanvasSupport()) {
    chartDisabled = true
    return
  }
  chartInstance = init(chartRef.value)
  updateChart()
}

const buildPieOption = () => ({
  tooltip: { ...GLOBAL_TOOLTIP, trigger: 'item' },
  legend: {
    bottom: 0,
    left: 'center',
  },
  color: chartColors,
  series: [
    {
      name: 'Sentiment',
      type: 'pie',
      radius: ['42%', '72%'],
      center: ['50%', '43%'],
      avoidLabelOverlap: false,
      itemStyle: {
        borderRadius: 6,
        borderColor: '#ffffff',
        borderWidth: 2,
      },
      label: { show: false, position: 'center' },
      emphasis: {
        label: { show: true, fontSize: 16, fontWeight: 'bold' },
      },
      labelLine: { show: false },
      data: normalizedItems.value,
    },
  ],
})

const buildBarOption = () => ({
  tooltip: { ...GLOBAL_TOOLTIP, trigger: 'axis', axisPointer: { type: 'shadow' } },
  grid: {
    left: '3%',
    right: '4%',
    bottom: '4%',
    top: '6%',
  },
  xAxis: {
    type: 'category',
    data: normalizedItems.value.map((item) => item.name),
    axisTick: { alignWithLabel: true },
    axisLine: { lineStyle: { color: splitLineColor } },
    axisLabel: { color: axisLabelColor },
  },
  yAxis: {
    type: 'value',
    axisLine: { show: false },
    axisLabel: { color: axisLabelColor },
    splitLine: { lineStyle: { color: splitLineColor } },
  },
  series: [
    {
      name: 'Sentiment',
      type: 'bar',
      barWidth: '48%',
      data: normalizedItems.value.map((item, index) => ({
        value: item.value,
        itemStyle: {
          color: chartColors[index % chartColors.length],
          borderRadius: [8, 8, 0, 0],
        },
      })),
    },
  ],
})

const updateChart = () => {
  if (!chartInstance) return
  chartInstance.setOption(displayMode.value === 'bar' ? buildBarOption() : buildPieOption(), true)
}

watch(
  () => props.data,
  () => {
    if (!chartInstance) {
      initChart()
    }
    updateChart()
  },
  { deep: true }
)

watch(displayMode, () => {
  updateChart()
})

const handleResize = () => {
  if (chartInstance) {
    chartInstance.resize()
  }
}

onMounted(() => {
  initChart()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
  window.removeEventListener('resize', handleResize)
})
</script>

<template>
  <div class="relative h-full min-h-[220px] w-full">
    <div class="absolute right-0 top-3 z-10">
      <div
        class="inline-flex rounded-full border border-slate-200 bg-white/95 p-1 text-xs shadow-sm"
      >
        <button
          data-testid="sentiment-mode-pie"
          type="button"
          class="rounded-full px-3 py-1.5 transition"
          :class="
            displayMode === 'pie'
              ? 'bg-slate-900 text-white '
              : 'text-slate-500 hover:text-slate-900 '
          "
          @click="displayMode = 'pie'"
        >
          饼图
        </button>
        <button
          data-testid="sentiment-mode-bar"
          type="button"
          class="rounded-full px-3 py-1.5 transition"
          :class="
            displayMode === 'bar'
              ? 'bg-slate-900 text-white '
              : 'text-slate-500 hover:text-slate-900 '
          "
          @click="displayMode = 'bar'"
        >
          柱图
        </button>
      </div>
    </div>
    <div ref="chartRef" class="h-full min-h-[220px] w-full"></div>
  </div>
</template>

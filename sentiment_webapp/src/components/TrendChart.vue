<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  graphic,
  init,
  GLOBAL_TOOLTIP,
  GLOBAL_SPLIT_LINE,
  CHART_COLOR_SEQUENCE,
} from '@/lib/echarts'
import { hasCanvasSupport } from '@/utils/canvasSupport'

const props = defineProps({
  data: {
    type: Object,
    default: () => ({ dates: [], values: [] }),
  },
  dates: {
    type: Array,
    default: () => [],
  },
  series: {
    type: Array,
    default: () => [],
  },
})

/** @type {import('vue').Ref<HTMLDivElement | null>} */ const chartRef = ref(null)
/** @type {any} */ let chartInstance = null
let chartDisabled = false

const palette = {
  positive: '#10b981',
  neutral: '#f59e0b',
  negative: '#f43f5e',
  priority: '#6366f1',
  total: '#475569',
}

const normalizedDates = computed(() => (props.dates.length ? props.dates : props.data?.dates || []))
const normalizedSeries = computed(() => {
  if (props.series.length) {
    return props.series
  }

  if (Array.isArray(props.data?.series) && props.data.series.length) {
    return props.data.series
  }

  if (Array.isArray(props.data?.values)) {
    return [
      {
        name: '分析量',
        key: 'total',
        data: props.data.values,
      },
    ]
  }

  return []
})

const initChart = () => {
  if (!chartRef.value || chartDisabled) return
  if (chartInstance) return
  if (!hasCanvasSupport()) {
    chartDisabled = true
    return
  }
  if (!chartRef.value.clientWidth || !chartRef.value.clientHeight) {
    setTimeout(initChart, 100)
    return
  }
  chartInstance = init(chartRef.value)
  updateChart()
}

const updateChart = () => {
  if (!chartInstance) return

  const axisColor = '#475569'

  const hasSecondAxis = normalizedSeries.value.some((item) => Number(item?.yAxisIndex) >= 1)
  const baseYAxis = {
    type: 'value',
    axisLabel: { color: axisColor },
    splitLine: GLOBAL_SPLIT_LINE,
  }
  const yAxis = hasSecondAxis
    ? [
        { ...baseYAxis, name: '损失', position: 'left' },
        {
          ...baseYAxis,
          name: '指标',
          position: 'right',
          min: 0,
          max: 1,
          splitLine: { show: false },
        },
      ]
    : baseYAxis

  chartInstance.setOption(
    {
      textStyle: { color: axisColor },
      tooltip: { ...GLOBAL_TOOLTIP, trigger: 'axis' },
      legend: { top: 0, textStyle: { color: axisColor } },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        top: '12%',
      },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: normalizedDates.value,
        axisLabel: { color: axisColor },
        axisLine: { lineStyle: { color: '#e2e8f0' } },
      },
      yAxis,
      series: normalizedSeries.value.map((item, index) => {
        const color =
          item.color ||
          palette[item.key] ||
          CHART_COLOR_SEQUENCE[index % CHART_COLOR_SEQUENCE.length]
        const yAxisIndex = hasSecondAxis ? Number(item?.yAxisIndex) || 0 : 0
        return {
          name: item.name || item.label || `Series ${index + 1}`,
          type: 'line',
          smooth: true,
          symbolSize: 8,
          data: item.data || [],
          yAxisIndex,
          areaStyle:
            index === 0 && yAxisIndex === 0
              ? {
                  color: new graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: `${color}66` },
                    { offset: 1, color: `${color}0f` },
                  ]),
                }
              : undefined,
          itemStyle: { color },
          lineStyle: { width: 3 },
        }
      }),
    },
    true
  )
}

watch(
  () => [props.data, props.dates, props.series],
  () => {
    if (!chartInstance) {
      initChart()
    }
    updateChart()
  },
  { deep: true }
)

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
  <div ref="chartRef" class="h-full min-h-[220px] w-full"></div>
</template>

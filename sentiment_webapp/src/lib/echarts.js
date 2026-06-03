import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { LegendComponent, GridComponent, TooltipComponent } from 'echarts/components'
import { init, use, graphic } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'

use([
  BarChart,
  LineChart,
  PieChart,
  LegendComponent,
  GridComponent,
  TooltipComponent,
  CanvasRenderer,
])

export { graphic, init }

// ── 全局图表主题常量 ──

/** 情感语义色 */
export const SENTIMENT_COLORS = {
  positive: '#10b981', // emerald-500
  negative: '#f43f5e', // rose-500
  neutral: '#f59e0b', // amber-500
}

/** 默认 series 色序 */
export const CHART_COLOR_SEQUENCE = [
  '#6366f1', // indigo-500
  '#10b981', // emerald-500
  '#f43f5e', // rose-500
  '#f59e0b', // amber-500
  '#8b5cf6', // violet-500
  '#06b6d4', // cyan-500
  '#ec4899', // pink-500
]

/** 情感色数组（饼图/柱状图用，顺序：积极、中性、消极） */
export const SENTIMENT_PIE_COLORS = [
  SENTIMENT_COLORS.positive,
  SENTIMENT_COLORS.neutral,
  SENTIMENT_COLORS.negative,
]

/** 全局 Tooltip 配置 */
export const GLOBAL_TOOLTIP = {
  backgroundColor: 'rgba(255, 255, 255, 0.95)',
  borderColor: '#e2e8f0',
  borderWidth: 1,
  borderRadius: 12,
  textStyle: { color: '#1e293b', fontSize: 13, fontWeight: 500 },
  padding: [10, 14],
  extraCssText:
    'box-shadow: 0 10px 24px -4px rgb(0 0 0 / 0.08), 0 4px 10px -4px rgb(0 0 0 / 0.04); backdrop-filter: blur(8px);',
}

/** 全局网格线（去噪虚线） */
export const GLOBAL_SPLIT_LINE = {
  lineStyle: { type: 'dashed', color: '#f1f5f9', width: 1.5 },
}

/** 全局 Grid 间距 */
export const GLOBAL_GRID = {
  left: 48,
  right: 24,
  top: 36,
  bottom: 32,
  containLabel: false,
}

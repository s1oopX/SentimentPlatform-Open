<script setup>
import { computed } from 'vue'

const props =
  /** @type {{ matrix: Array<Array<string | number>>, xLabels: Array<string | number>, yLabels: Array<string | number> }} */ (
    defineProps({
      matrix: {
        type: Array,
        default: () => [],
      },
      xLabels: {
        type: Array,
        default: () => [],
      },
      yLabels: {
        type: Array,
        default: () => [],
      },
    })
  )

const { matrix, xLabels, yLabels } = props

const maxValue = computed(() => {
  let max = 0
  for (const row of props.matrix || []) {
    for (const value of row || []) {
      const numeric = Number(value) || 0
      if (numeric > max) max = numeric
    }
  }
  return max
})

/** @param {string | number} value */
const cellStyle = (value) => {
  const numeric = Number(value) || 0
  if (maxValue.value <= 0) return {}
  const ratio = Math.min(numeric / maxValue.value, 1)
  // 蓝色色阶：低值浅蓝、高值深蓝；高对比度时切换为白字
  const backgroundColor = `rgba(37, 99, 235, ${ratio.toFixed(3)})`
  const color = ratio >= 0.55 ? '#ffffff' : '#1e293b'
  return { backgroundColor, color }
}
</script>

<template>
  <div
    class="w-full self-start overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm"
  >
    <div
      class="grid"
      :style="{ gridTemplateColumns: `120px repeat(${xLabels.length || 3}, minmax(0, 1fr))` }"
    >
      <div
        class="border-b border-r border-slate-200 bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-500"
      >
        真实值 / 预测值
      </div>
      <div
        v-for="label in xLabels"
        :key="label"
        class="border-b border-r border-slate-200 bg-slate-50 px-4 py-3 text-center text-sm font-semibold text-slate-600 last:border-r-0"
      >
        {{ label }}
      </div>

      <template v-for="(row, rowIndex) in matrix" :key="rowIndex">
        <div
          class="border-b border-r border-slate-200 bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-600"
        >
          {{ yLabels[rowIndex] || `类别 ${rowIndex + 1}` }}
        </div>
        <div
          v-for="(value, colIndex) in row"
          :key="`${rowIndex}-${colIndex}`"
          :style="cellStyle(value)"
          class="border-b border-r border-slate-200 px-4 py-3 text-center text-sm font-medium transition-colors last:border-r-0"
        >
          {{ value }}
        </div>
      </template>
    </div>
  </div>
</template>

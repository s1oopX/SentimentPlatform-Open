<script setup>
import { computed } from 'vue'

/**
 * @typedef {Record<string, string | number | null | undefined>} WordCloudItem
 */
const props = defineProps({
  items: {
    type: /** @type {import('vue').PropType<WordCloudItem[]>} */ (Array),
    default: () => [],
  },
  itemKey: {
    type: String,
    default: 'keyword',
  },
  valueKey: {
    type: String,
    default: 'count',
  },
  title: {
    type: String,
    default: '',
  },
  emptyText: {
    type: String,
    default: '暂无词云数据',
  },
})

const wordData = computed(() =>
  (props.items || [])
    .filter((item) => item[props.itemKey] && item[props.valueKey])
    .map((item) => ({
      name: String(item[props.itemKey]),
      value: Number(item[props.valueKey]) || 0,
    }))
)

const COLORS = [
  '#6366f1',
  '#8b5cf6',
  '#a855f7',
  '#d946ef',
  '#ec4899',
  '#f43f5e',
  '#ef4444',
  '#f97316',
  '#eab308',
  '#22c55e',
  '#14b8a6',
  '#06b6d4',
  '#3b82f6',
  '#2563eb',
]

const maxValue = computed(() => Math.max(...wordData.value.map((item) => item.value), 0))

const cloudItems = computed(() =>
  wordData.value.map((item, index) => {
    const ratio = maxValue.value ? item.value / maxValue.value : 0
    return {
      ...item,
      color: COLORS[index % COLORS.length],
      fontSize: `${Math.round(15 + ratio * 21)}px`,
      weight: ratio > 0.66 ? 800 : ratio > 0.33 ? 700 : 600,
    }
  })
)
</script>

<template>
  <div class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
    <h3 v-if="title" class="text-base font-semibold text-slate-900">{{ title }}</h3>
    <div v-if="cloudItems.length" class="word-cloud-fallback mt-4">
      <span
        v-for="item in cloudItems"
        :key="item.name"
        class="word-cloud-token"
        :style="{ color: item.color, fontSize: item.fontSize, fontWeight: item.weight }"
        :title="`${item.name}: ${item.value}`"
      >
        {{ item.name }}
      </span>
    </div>
    <div v-else class="mt-4 flex h-72 items-center justify-center text-sm text-slate-400">
      {{ emptyText }}
    </div>
  </div>
</template>

<style scoped>
.word-cloud-fallback {
  display: flex;
  min-height: 18rem;
  align-items: center;
  justify-content: center;
  align-content: center;
  gap: 14px 18px;
  flex-wrap: wrap;
  padding: 22px;
}

.word-cloud-token {
  display: inline-flex;
  line-height: 1.1;
  letter-spacing: 0;
  white-space: nowrap;
}
</style>

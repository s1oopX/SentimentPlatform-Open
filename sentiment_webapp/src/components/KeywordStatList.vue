<script setup>
import { computed } from 'vue'

/**
 * @typedef {Record<string, string | number | null | undefined>} KeywordStatItem
 */
const props = defineProps({
  items: {
    type: /** @type {import('vue').PropType<KeywordStatItem[]>} */ (Array),
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
    default: '暂无关键词数据',
  },
  maxItems: {
    type: Number,
    default: 12,
  },
})

/** @param {any} value */ const formatValue = (value) => Number(value || 0).toLocaleString('zh-CN')
const visibleItems = computed(() => (props.items || []).slice(0, props.maxItems))
</script>

<template>
  <div class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
    <h3 v-if="title" class="text-base font-semibold text-slate-700">{{ title }}</h3>
    <div v-if="visibleItems.length" class="mt-4 space-y-2">
      <div
        v-for="item in visibleItems"
        :key="`${item[itemKey]}-${item[valueKey]}`"
        class="flex items-center justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2 text-sm"
      >
        <span class="truncate font-medium text-slate-700">{{ item[itemKey] }}</span>
        <span class="tabular-nums font-mono text-slate-500">{{ formatValue(item[valueKey]) }}</span>
      </div>
    </div>
    <div v-else class="mt-4 text-sm text-slate-400">{{ emptyText }}</div>
  </div>
</template>

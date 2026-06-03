<script setup>
import { computed } from 'vue'

const props =
  /** @type {{ items: Array<Record<string, any>>, labelKey: string, valueKey: string, title: string, emptyText: string }} */ (
    defineProps({
      items: {
        type: Array,
        default: () => [],
      },
      labelKey: {
        type: String,
        default: 'label',
      },
      valueKey: {
        type: String,
        default: 'value',
      },
      title: {
        type: String,
        default: '',
      },
      emptyText: {
        type: String,
        default: '暂无数据',
      },
    })
  )

const normalizedItems = computed(() => {
  return (props.items || []).map((item) => ({
    label: item?.[props.labelKey] ?? item?.label ?? item?.category ?? item?.group_value ?? '未命名',
    value: Number(item?.[props.valueKey] ?? item?.value ?? item?.count ?? 0),
  }))
})

const maxValue = computed(() => {
  const values = normalizedItems.value.map((item) => item.value)
  return Math.max(...values, 0)
})

/** @param {any} value */ const formatValue = (value) => Number(value || 0).toLocaleString('zh-CN')
</script>

<template>
  <div
    class="flex h-full min-h-[300px] flex-col rounded-xl border border-slate-200 bg-white p-7 shadow-sm"
  >
    <h3 v-if="title" class="text-lg font-bold tracking-tight text-slate-900">{{ title }}</h3>
    <div v-if="normalizedItems.length" class="mt-5 flex flex-1 flex-col justify-evenly">
      <div v-for="item in normalizedItems" :key="`${item.label}-${item.value}`" class="space-y-3">
        <div class="flex items-center justify-between gap-4 text-base">
          <span class="truncate font-semibold text-slate-800">{{ item.label }}</span>
          <span class="font-mono text-sm font-semibold tabular-nums text-slate-600">
            {{ formatValue(item.value) }}
          </span>
        </div>
        <div class="h-2.5 overflow-hidden rounded-full bg-slate-100">
          <div
            class="h-full rounded-full bg-indigo-500"
            :style="{
              width: `${maxValue ? Math.max((item.value / maxValue) * 100, item.value > 0 ? 12 : 0) : 0}%`,
            }"
          />
        </div>
      </div>
    </div>
    <div v-else class="flex flex-1 items-center justify-center text-sm text-slate-400">
      {{ emptyText }}
    </div>
  </div>
</template>

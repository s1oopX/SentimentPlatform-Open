<script setup>
import { computed } from 'vue'

const props = defineProps({
  title: {
    type: String,
    required: true,
  },
  value: {
    type: [String, Number],
    default: '--',
  },
  note: {
    type: String,
    default: '',
  },
  trend: {
    type: [String, Number],
    default: null,
  },
  icon: {
    type: [Object, Function],
    default: null,
  },
  tone: {
    type: String,
    default: 'slate',
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

const toneClass = computed(() => {
  const classes = {
    blue: {
      iconBg: 'bg-blue-50',
      iconText: 'text-blue-600',
    },
    green: {
      iconBg: 'bg-emerald-50',
      iconText: 'text-emerald-600',
    },
    orange: {
      iconBg: 'bg-amber-50',
      iconText: 'text-amber-600',
    },
    amber: {
      iconBg: 'bg-amber-50',
      iconText: 'text-amber-600',
    },
    red: {
      iconBg: 'bg-rose-50',
      iconText: 'text-rose-600',
    },
    indigo: {
      iconBg: 'bg-indigo-50',
      iconText: 'text-indigo-600',
    },
    emerald: {
      iconBg: 'bg-emerald-50',
      iconText: 'text-emerald-600',
    },
    slate: {
      iconBg: 'bg-slate-100',
      iconText: 'text-slate-600',
    },
  }
  return classes[props.tone] || classes.slate
})

const trendClass = computed(() => {
  if (typeof props.trend === 'number') {
    return props.trend >= 0 ? 'text-emerald-600' : 'text-rose-600'
  }
  return String(props.trend || '')
    .trim()
    .startsWith('-')
    ? 'text-rose-600'
    : 'text-emerald-600'
})
</script>

<template>
  <div
    v-loading="loading"
    class="group rounded-xl border border-slate-200 bg-white p-6 shadow-premium transition-all duration-300 hover:-translate-y-0.5 hover:shadow-premium-hover hover:border-slate-300"
  >
    <div class="flex items-start justify-between gap-4">
      <div class="min-w-0 space-y-1.5 flex-1">
        <p
          class="text-sm font-medium leading-5 text-slate-500 transition-colors group-hover:text-slate-600"
        >
          {{ title }}
        </p>
        <p class="text-3xl font-bold tabular-nums text-slate-800 tracking-tight">{{ value }}</p>
        <div
          v-if="note || trend !== null"
          class="flex flex-wrap items-center gap-2 pt-1 opacity-90 transition-opacity group-hover:opacity-100"
        >
          <p v-if="note" class="text-xs font-medium text-slate-400">{{ note }}</p>
          <span v-if="trend !== null" class="text-xs font-semibold" :class="trendClass">
            {{ trend }}
          </span>
        </div>
      </div>
      <div
        v-if="icon"
        class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl"
        :class="toneClass.iconBg"
      >
        <el-icon :size="22" :class="toneClass.iconText">
          <component :is="icon" />
        </el-icon>
      </div>
    </div>
  </div>
</template>

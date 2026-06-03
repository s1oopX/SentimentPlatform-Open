<script setup>
defineProps({
  title: {
    type: String,
    required: true,
  },
  description: {
    type: String,
    default: '',
  },
  meta: {
    type: String,
    default: '',
  },
})
</script>

<template>
  <div class="mb-6 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
    <div class="space-y-1">
      <h1 class="text-2xl font-bold text-slate-800">{{ title }}</h1>
      <p v-if="description" class="text-sm text-slate-500">{{ description }}</p>
      <p v-if="meta" class="text-xs text-slate-400">{{ meta }}</p>
    </div>
    <div v-if="$slots.actions" class="flex flex-wrap items-center gap-3">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    default: '',
  },
  description: {
    type: String,
    default: '',
  },
  padded: {
    type: Boolean,
    default: true,
  },
})
</script>

<template>
  <section class="rounded-xl border border-slate-200 bg-white shadow-premium">
    <div
      v-if="title || description || $slots.actions"
      class="flex flex-col gap-3 border-b border-slate-100/80 px-6 py-5 md:flex-row md:items-center md:justify-between"
    >
      <div class="space-y-1.5">
        <h2 v-if="title" class="text-base font-bold text-slate-800 tracking-tight">{{ title }}</h2>
        <p v-if="description" class="text-sm text-slate-500 font-medium">{{ description }}</p>
      </div>
      <div v-if="$slots.actions" class="flex flex-wrap items-center gap-2">
        <slot name="actions" />
      </div>
    </div>
    <div :class="padded ? 'p-6' : ''">
      <slot />
    </div>
  </section>
</template>

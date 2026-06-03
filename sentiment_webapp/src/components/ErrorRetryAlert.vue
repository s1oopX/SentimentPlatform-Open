<script setup>
import { Refresh } from '@element-plus/icons-vue'

defineProps({
  message: { type: String, required: true },
  onRetry: { type: Function, default: null },
  loading: { type: Boolean, default: false },
  retryText: { type: String, default: '重试' },
})
</script>

<template>
  <div
    v-if="message"
    class="flex items-start justify-between gap-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3"
    role="alert"
  >
    <div class="flex-1 text-sm font-medium text-red-700">
      {{ message }}
    </div>
    <el-button v-if="onRetry" size="small" :icon="Refresh" :loading="loading" @click="onRetry">
      {{ retryText }}
    </el-button>
  </div>
</template>

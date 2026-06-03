<script setup>
import { computed } from 'vue'
import DOMPurify from 'dompurify'

const props = defineProps({
  html: {
    type: String,
    required: true,
  },
  tag: {
    type: String,
    default: 'span',
  },
})

const sanitizedHtml = computed(() =>
  DOMPurify.sanitize(props.html, {
    RETURN_TRUSTED_TYPE: false,
    USE_PROFILES: {
      html: true,
      svg: true,
      svgFilters: true,
    },
  })
)
</script>

<template>
  <p v-if="tag === 'p'" v-html="sanitizedHtml"></p>
  <div v-else-if="tag === 'div'" v-html="sanitizedHtml"></div>
  <span v-else v-html="sanitizedHtml"></span>
</template>

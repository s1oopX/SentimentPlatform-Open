<script setup>
const props = defineProps({
  size: {
    type: String,
    default: 'default',
  },
})

const logoSrc = '/brand/yx-logo.svg'
</script>

<template>
  <div class="auth-brand-badge" :class="`auth-brand-badge--${props.size}`" aria-hidden="true">
    <img class="auth-brand-badge__image" :src="logoSrc" alt="" />
  </div>
</template>

<style scoped>
.auth-brand-badge {
  display: flex;
  align-items: center;
  justify-content: center;
}

.auth-brand-badge__image {
  display: block;
  height: 3.5rem;
  width: 3.5rem;
  filter: drop-shadow(0 12px 24px rgba(15, 23, 42, 0.18));
}

.auth-brand-badge--compact .auth-brand-badge__image {
  height: 3rem;
  width: 3rem;
  filter: drop-shadow(0 10px 20px rgba(15, 23, 42, 0.14));
}
</style>

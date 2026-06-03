<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <div
    class="min-h-screen flex flex-col items-center justify-center text-center space-y-6 bg-white"
  >
    <p class="text-9xl font-bold text-slate-100 select-none">404</p>
    <div class="-mt-8 space-y-2">
      <h1 class="text-2xl font-bold text-slate-900">页面不存在</h1>
      <p class="text-slate-500">请检查地址是否正确，或返回首页重新导航</p>
    </div>
    <el-button type="primary" class="!rounded-xl !h-11 !px-8" @click="router.replace('/')">
      返回首页
    </el-button>
  </div>
</template>

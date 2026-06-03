<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { getDefaultHomeRoute } from '@/router/access'
import { normalizeLoginRedirectValue } from '@/router/loginRedirect'
import AuthBrandBadge from '@/components/AuthBrandBadge.vue'
import SafeHtml from '@/components/SafeHtml.vue'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Refresh } from '@element-plus/icons-vue'
import { buildLoginPayload, validateLoginIdentifier } from '@/utils/loginIdentifier'
import { sanitizeCaptchaSvg } from '@/utils/captchaSanitize'
import { getCaptcha } from '@/api/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const baseUrl = import.meta.env.BASE_URL || '/'

const loading = ref(false)
/** @type {import('vue').Ref<import('element-plus').FormInstance | null>} */
const formRef = ref(null)

const form = reactive({
  identifier: '',
  password: '',
  captcha_key: '',
  captcha_code: '',
})

const captchaSvg = ref('')
const captchaLoading = ref(false)

const refreshCaptcha = async () => {
  captchaLoading.value = true
  try {
    const res = await getCaptcha()
    captchaSvg.value = sanitizeCaptchaSvg(res.data.captcha_svg)
    form.captcha_key = res.data.captcha_key
    form.captcha_code = ''
  } catch {
    // Error handled in interceptor
  } finally {
    captchaLoading.value = false
  }
}

onMounted(refreshCaptcha)

const rules = {
  identifier: [{ required: true, validator: validateLoginIdentifier, trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  captcha_code: [{ required: true, message: '请输入验证码', trigger: 'blur' }],
}

const navigateAfterLogin = async (target) => {
  // Wait for Vue reactivity to propagate token/user state
  await nextTick()
  try {
    await router.replace(target)
  } catch {
    // NavigationDuplicated or guard rejection — use fallback
    const resolved = router.resolve(target)
    if (resolved?.href && resolved.href !== router.currentRoute.value.fullPath) {
      window.location.href = resolved.href
    }
  }
}

const handleLogin = async () => {
  if (!formRef.value) return
  let valid = false
  await formRef.value.validate((result) => {
    valid = result
  })
  if (!valid) return

  loading.value = true
  const payload = buildLoginPayload(form)
  if (!payload) {
    loading.value = false
    return
  }
  try {
    await authStore.login({
      ...payload,
      captcha_key: form.captcha_key,
      captcha_code: form.captcha_code,
    })
    ElMessage.success('登录成功')
    const target =
      normalizeLoginRedirectValue(route.query.redirect, baseUrl) ||
      getDefaultHomeRoute(authStore.user)
    await navigateAfterLogin(target)
  } catch {
    refreshCaptcha()
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div
    class="min-h-screen flex items-center justify-center bg-gradient-to-b from-slate-50 to-white relative overflow-hidden py-12 px-4"
  >
    <!-- Decorative Orbs (Matching Landing Page) -->
    <div
      class="absolute top-[-10%] left-[-5%] w-[40%] h-[40%] rounded-full bg-blue-100/40 blur-3xl pointer-events-none"
    ></div>
    <div
      class="absolute bottom-[-10%] right-[-5%] w-[40%] h-[40%] rounded-full bg-indigo-100/40 blur-3xl pointer-events-none"
    ></div>

    <!-- 返回落地页按钮 -->
    <a
      class="fixed top-6 left-6 flex items-center gap-2 px-4 py-2 text-slate-600 hover:text-slate-900 hover:bg-white/80 rounded-lg backdrop-blur-sm transition-all duration-200 shadow-sm hover:shadow cursor-pointer z-10"
      @click="router.push('/')"
    >
      <el-icon><ArrowLeft /></el-icon>
      <span class="text-sm font-medium">返回首页</span>
    </a>

    <div
      class="w-full max-w-md bg-white rounded-2xl border border-slate-100 shadow-premium overflow-hidden transition-all duration-300 hover:shadow-premium-hover"
    >
      <div class="px-8 pt-8 pb-4 text-center space-y-1">
        <div class="flex items-center justify-center mb-2">
          <AuthBrandBadge />
        </div>
        <h2 class="text-2xl font-bold text-slate-800 tracking-tight">欢迎回来</h2>
        <p class="text-slate-500 font-medium text-sm">登录云析智研以继续使用</p>
      </div>

      <div class="px-8 pb-8">
        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-position="top"
          @keyup.enter="handleLogin"
        >
          <el-form-item
            label="账号"
            prop="identifier"
            class="form-label-sm font-medium text-slate-700"
          >
            <el-input
              v-model="form.identifier"
              placeholder="请输入邮箱或手机号"
              class="h-12 el-input-rounded"
            />
          </el-form-item>

          <el-form-item
            label="密码"
            prop="password"
            class="form-label-sm font-medium text-slate-700"
          >
            <el-input
              v-model="form.password"
              type="password"
              placeholder="••••••••"
              show-password
              autocomplete="current-password"
              class="h-12 el-input-rounded"
            />
          </el-form-item>

          <el-form-item
            label="验证码"
            prop="captcha_code"
            class="form-label-sm font-medium text-slate-700"
          >
            <div class="flex items-center gap-3 w-full">
              <el-input
                v-model="form.captcha_code"
                placeholder="请输入验证码"
                class="h-12 el-input-rounded flex-1 tracking-widest"
                maxlength="6"
              />
              <SafeHtml
                v-if="captchaSvg"
                tag="div"
                :html="captchaSvg"
                class="h-12 min-w-[120px] rounded-xl border border-slate-200 overflow-hidden cursor-pointer flex items-center justify-center bg-slate-50 shadow-sm transition-transform hover:scale-[1.02]"
                :class="{ 'opacity-50': captchaLoading }"
                @click="refreshCaptcha"
              />
              <el-button
                v-else
                class="!h-12 !min-w-[120px] !rounded-xl"
                :loading="captchaLoading"
                @click="refreshCaptcha"
              >
                <el-icon><Refresh /></el-icon>
              </el-button>
            </div>
          </el-form-item>

          <div class="flex items-center justify-end mb-6 mt-[-4px]">
            <el-link
              type="info"
              underline="never"
              class="text-sm font-medium hover:text-indigo-600 transition-colors"
              @click="router.push('/reset-password')"
            >
              忘记密码？
            </el-link>
          </div>

          <el-button
            type="primary"
            class="w-full !h-12 !text-base !font-semibold !rounded-xl shadow-premium hover:-translate-y-0.5 hover:shadow-premium-hover transition-all duration-300"
            :loading="loading"
            @click="handleLogin"
          >
            登录
          </el-button>
        </el-form>

        <div class="relative w-full my-6">
          <div class="absolute inset-0 flex items-center">
            <div class="w-full border-t border-slate-100"></div>
          </div>
          <div class="relative flex justify-center text-xs">
            <span class="bg-white px-3 text-slate-400 font-medium">或</span>
          </div>
        </div>

        <p class="text-sm text-center text-slate-600">
          还没有账号？
          <a
            class="text-slate-900 hover:text-indigo-600 hover:underline font-bold underline-offset-4 cursor-pointer transition-all"
            @click="router.push('/register')"
          >
            立即注册
          </a>
        </p>
      </div>
    </div>
  </div>
</template>

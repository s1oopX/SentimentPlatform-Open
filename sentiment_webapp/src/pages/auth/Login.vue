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
  <div class="login-page">
    <button class="back-button" type="button" @click="router.push('/')">
      <el-icon><ArrowLeft /></el-icon>
      <span>返回首页</span>
    </button>

    <div class="login-shell">
      <aside class="login-context">
        <div class="context-brand">
          <AuthBrandBadge />
          <span>云析智研</span>
        </div>
        <h1>进入情感分析工作台</h1>
        <p>登录后按角色进入用户仪表盘、分析师工作台或管理员控制台。</p>
        <div class="context-list" aria-hidden="true">
          <div>
            <strong>USER</strong>
            <span>评论分析与报告中心</span>
          </div>
          <div>
            <strong>ANALYST</strong>
            <span>全局审核与趋势洞察</span>
          </div>
          <div>
            <strong>ADMIN</strong>
            <span>模型、数据集与系统运维</span>
          </div>
        </div>
      </aside>

      <section class="login-card">
        <div class="login-card__header">
          <h2>欢迎回来</h2>
          <p>使用邮箱或手机号登录</p>
        </div>

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
              placeholder="请输入密码"
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
            <div class="captcha-row">
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
                class="captcha-image"
                :class="{ 'opacity-50': captchaLoading }"
                @click="refreshCaptcha"
              />
              <el-button
                v-else
                class="captcha-refresh"
                :loading="captchaLoading"
                @click="refreshCaptcha"
              >
                <el-icon><Refresh /></el-icon>
              </el-button>
            </div>
          </el-form-item>

          <div class="login-links">
            <el-link type="info" underline="never" @click="router.push('/reset-password')">
              忘记密码？
            </el-link>
          </div>

          <el-button type="primary" class="login-submit" :loading="loading" @click="handleLogin">
            登录
          </el-button>
        </el-form>

        <div class="signup-row">
          <span>还没有账号？</span>
          <button type="button" @click="router.push('/register')">立即注册</button>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  display: grid;
  min-height: 100vh;
  place-items: center;
  background:
    linear-gradient(180deg, rgba(248, 250, 252, 0.98), rgba(241, 245, 249, 0.94)),
    repeating-linear-gradient(90deg, rgba(15, 23, 42, 0.035) 0 1px, transparent 1px 104px);
  padding: 5rem 1.5rem;
}

.back-button {
  position: fixed;
  top: 1.5rem;
  left: 1.5rem;
  z-index: 2;
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  border: 1px solid #dbe3ee;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.9);
  color: #334155;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 700;
  padding: 0.55rem 0.8rem;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.06);
}

.login-shell {
  display: grid;
  grid-template-columns: minmax(0, 0.95fr) minmax(390px, 0.78fr);
  width: min(100%, 62rem);
  overflow: hidden;
  border: 1px solid #dbe3ee;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 28px 70px rgba(15, 23, 42, 0.14);
}

.login-context {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: 37rem;
  background: #0f172a;
  color: #e2e8f0;
  padding: 2.5rem;
}

.context-brand {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  color: #ffffff;
  font-weight: 850;
}

.login-context h1 {
  max-width: 10ch;
  margin: 2rem 0 1rem;
  color: #ffffff;
  font-size: 2.75rem;
  font-weight: 850;
  line-height: 1.08;
}

.login-context p {
  max-width: 30rem;
  margin: 0;
  color: #cbd5e1;
  line-height: 1.8;
}

.context-list {
  display: grid;
  gap: 0.75rem;
  margin-top: 2rem;
}

.context-list div {
  display: grid;
  grid-template-columns: 5.4rem minmax(0, 1fr);
  gap: 0.8rem;
  align-items: center;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.68);
  padding: 0.85rem 1rem;
}

.context-list strong {
  color: #5eead4;
  font-size: 0.78rem;
}

.context-list span {
  color: #e2e8f0;
  font-size: 0.9rem;
  font-weight: 700;
}

.login-card {
  padding: 2.25rem;
}

.login-card__header {
  margin-bottom: 1.7rem;
}

.login-card__header h2 {
  margin: 0;
  color: #0f172a;
  font-size: 1.75rem;
  font-weight: 850;
}

.login-card__header p {
  margin: 0.4rem 0 0;
  color: #64748b;
  font-size: 0.95rem;
}

.captcha-row {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 0.75rem;
}

.captcha-image,
.captcha-refresh {
  display: flex;
  width: 7.5rem;
  min-width: 7.5rem;
  height: 3rem;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border: 1px solid #dbe3ee;
  border-radius: 8px;
  background: #f8fafc;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    transform 0.2s ease;
}

.captcha-image:hover,
.captcha-refresh:hover {
  border-color: #94a3b8;
  transform: translateY(-1px);
}

.login-links {
  display: flex;
  justify-content: flex-end;
  margin: -0.2rem 0 1.4rem;
}

.login-submit {
  width: 100%;
  height: 3rem;
  border-radius: 8px;
  font-size: 1rem;
  font-weight: 800;
}

.signup-row {
  display: flex;
  justify-content: center;
  gap: 0.4rem;
  margin-top: 1.5rem;
  color: #64748b;
  font-size: 0.92rem;
}

.signup-row button {
  border: 0;
  background: transparent;
  color: #0f172a;
  cursor: pointer;
  font-weight: 850;
  padding: 0;
}

.signup-row button:hover {
  color: #0f766e;
}

@media (max-width: 860px) {
  .login-shell {
    grid-template-columns: 1fr;
  }

  .login-context {
    min-height: auto;
    padding: 2rem;
  }

  .login-context h1 {
    max-width: 16ch;
    font-size: 2.2rem;
  }
}

@media (max-width: 560px) {
  .login-page {
    padding: 5rem 1rem 2rem;
  }

  .back-button {
    left: 1rem;
  }

  .login-card {
    padding: 1.4rem;
  }

  .captcha-row {
    flex-wrap: wrap;
  }

  .captcha-image,
  .captcha-refresh {
    width: 100%;
  }
}
</style>

<script setup>
import { ref, reactive, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { resetPassword, sendCode } from '@/api/auth'
import AuthBrandBadge from '@/components/AuthBrandBadge.vue'
import { ElMessage } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import { buildPasswordRules } from '@/utils/passwordRules'

const router = useRouter()
const loading = ref(false)
const codeLoading = ref(false)
/** @type {import('vue').Ref<import('element-plus').FormInstance | null>} */
const formRef = ref(null)
const resendCooldown = ref(0)
let resendTimerId = null

const form = reactive({
  email: '',
  code: '',
  newPassword: '',
  confirmPassword: '',
})

const validatePass2 = (rule, value, callback) => {
  if (value === '') {
    callback(new Error('请再次输入新密码'))
  } else if (value !== form.newPassword) {
    callback(new Error('两次输入密码不一致!'))
  } else {
    callback()
  }
}

const rules = {
  email: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    { type: 'email', message: '请输入有效的邮箱地址', trigger: ['blur', 'change'] },
  ],
  code: [{ required: true, message: '请输入验证码', trigger: 'blur' }],
  newPassword: buildPasswordRules({ requiredMessage: '请输入新密码' }),
  confirmPassword: [{ required: true, validator: validatePass2, trigger: 'blur' }],
}

const clearResendCooldown = () => {
  if (resendTimerId !== null) {
    clearInterval(resendTimerId)
    resendTimerId = null
  }
  resendCooldown.value = 0
}

const startResendCooldown = (seconds = 60) => {
  clearResendCooldown()
  resendCooldown.value = seconds
  resendTimerId = window.setInterval(() => {
    if (resendCooldown.value <= 1) {
      clearResendCooldown()
      return
    }
    resendCooldown.value -= 1
  }, 1000)
}

onBeforeUnmount(() => {
  clearResendCooldown()
})

const handleSendCode = async () => {
  if (!formRef.value) {
    return
  }

  try {
    await formRef.value.validateField('email')
  } catch {
    return
  }

  codeLoading.value = true
  try {
    await sendCode({ email: form.email, purpose: 'reset_password' })
    ElMessage.success('验证码已发送到您的邮箱')
    startResendCooldown()
  } catch {
    // handled
  } finally {
    codeLoading.value = false
  }
}

const navigateToLoginAfterReset = async () => {
  try {
    await router.push('/login')
  } catch {
    ElMessage.warning('密码已重置，但未能跳转到登录页，请手动前往登录')
  }
}

const handleReset = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try {
        await resetPassword({
          email: form.email,
          code: form.code,
          new_password: form.newPassword,
          new_password_confirm: form.confirmPassword,
        })
        ElMessage.success('密码重置成功！请登录')
        await navigateToLoginAfterReset()
      } catch {
        // handled
      } finally {
        loading.value = false
      }
    }
  })
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
      class="w-full max-w-md bg-white/90 backdrop-blur-xl rounded-2xl border border-slate-100 shadow-premium overflow-hidden transition-all duration-300 hover:shadow-premium-hover"
    >
      <div class="px-8 pt-8 pb-4 text-center space-y-1">
        <div class="flex items-center justify-center mb-2">
          <AuthBrandBadge />
        </div>
        <h2 class="text-2xl font-bold text-slate-800 tracking-tight">重置密码</h2>
        <p class="text-slate-500 font-medium text-sm">验证云析智研账号邮箱以设置新密码</p>
      </div>

      <div class="px-8 pb-8">
        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-position="top"
          @keyup.enter="handleReset"
        >
          <el-form-item
            label="邮箱地址"
            prop="email"
            class="form-label-sm font-medium text-slate-700"
          >
            <el-input
              v-model="form.email"
              placeholder="name@company.com"
              class="h-12 el-input-rounded"
            />
          </el-form-item>

          <el-form-item label="验证码" prop="code" class="form-label-sm font-medium text-slate-700">
            <div class="flex gap-3 w-full">
              <el-input
                v-model="form.code"
                placeholder="6位验证码"
                maxlength="6"
                class="h-12 flex-1 el-input-rounded tracking-widest"
              />
              <el-button
                type="default"
                class="!h-12 !rounded-xl !px-5 !border-indigo-100 hover:!bg-indigo-50 hover:!text-indigo-600 transition-colors duration-200"
                :loading="codeLoading"
                :disabled="resendCooldown > 0"
                @click="handleSendCode"
              >
                {{ resendCooldown > 0 ? `${resendCooldown}s 后重发` : '获取验证码' }}
              </el-button>
            </div>
          </el-form-item>

          <el-form-item
            label="新密码"
            prop="newPassword"
            class="form-label-sm font-medium text-slate-700"
          >
            <el-input
              v-model="form.newPassword"
              type="password"
              placeholder="设置高强度新密码"
              show-password
              autocomplete="new-password"
              class="h-12 el-input-rounded"
            />
          </el-form-item>

          <el-form-item
            label="确认新密码"
            prop="confirmPassword"
            class="form-label-sm font-medium text-slate-700"
          >
            <el-input
              v-model="form.confirmPassword"
              type="password"
              placeholder="再次确认新密码"
              show-password
              autocomplete="new-password"
              class="h-12 el-input-rounded"
            />
          </el-form-item>

          <el-button
            type="primary"
            class="w-full !h-12 mt-4 !text-base !font-semibold !rounded-xl shadow-premium hover:-translate-y-0.5 hover:shadow-premium-hover transition-all duration-300"
            :loading="loading"
            @click="handleReset"
          >
            完成重置
          </el-button>
        </el-form>

        <p class="text-sm text-center text-slate-600 mt-8">
          想起来了？
          <a
            class="text-slate-900 hover:text-indigo-600 hover:underline font-bold underline-offset-4 cursor-pointer transition-all"
            @click="router.push('/login')"
          >
            返回登录
          </a>
        </p>
      </div>
    </div>
  </div>
</template>

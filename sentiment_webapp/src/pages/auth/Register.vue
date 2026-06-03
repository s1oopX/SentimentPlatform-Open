<script setup>
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import AuthBrandBadge from '@/components/AuthBrandBadge.vue'
import { sendCode as apiSendCode, register as apiRegister } from '@/api/auth'
import { extractErrorMessage } from '@/api/request'
import { ElMessage } from 'element-plus'
import {
  UserFilled,
  ArrowLeft,
  Camera,
  User,
  DataLine,
  CircleCheckFilled,
  Medal,
  TrendCharts,
  Lightning,
} from '@element-plus/icons-vue'
import { buildPasswordRules } from '@/utils/passwordRules'

const MAX_AVATAR_SIZE = 2 * 1024 * 1024
const AVATAR_ACCEPT = 'image/png,image/jpeg,image/gif,image/webp'

const router = useRouter()
const loading = ref(false)
const errorMessage = ref('')
const sendingCode = ref(false)
/** @type {import('vue').Ref<import('element-plus').FormInstance | null>} */
const formRef = ref(null)
const codeCountdown = ref(0)
/** @type {import('vue').Ref<number | null>} */
const countdownTimer = ref(null)
const form = reactive({
  email: '',
  password: '',
  confirmPassword: '',
  code: '',
  nickname: '',
  phone: '',
  role: 'user',
})
/** @type {import('vue').Ref<File | null>} */ const avatarFile = ref(null)
const avatarPreviewUrl = ref('')
/** @type {import('vue').Ref<import('vue').ComponentPublicInstance | null>} */
const avatarInputRef = ref(null)

const roleOptions = [
  { value: 'user', label: '普通用户' },
  { value: 'analyst', label: '分析师' },
]
const sendCodeButtonText = computed(() =>
  codeCountdown.value > 0 ? `${codeCountdown.value}s后重新发送` : '发送验证码'
)
const isSendCodeDisabled = computed(() => sendingCode.value || codeCountdown.value > 0)

const validatePass2 = (rule, value, callback) => {
  if (value === '') {
    callback(new Error('请再次输入密码'))
  } else if (value !== form.password) {
    callback(new Error('两次输入密码不一致!'))
  } else {
    callback()
  }
}

const validateCode = (rule, value, callback) => {
  if (!value?.trim()) {
    callback(new Error('请输入邮箱验证码'))
  } else {
    callback()
  }
}

const rules = {
  nickname: [{ required: true, message: '请输入昵称', trigger: 'blur' }],
  email: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    { type: 'email', message: '请输入有效的邮箱地址', trigger: ['blur', 'change'] },
  ],
  password: buildPasswordRules({ requiredMessage: '请输入密码' }),
  code: [{ required: true, validator: validateCode, trigger: 'blur' }],
  confirmPassword: [{ required: true, validator: validatePass2, trigger: 'blur' }],
}

const stopCountdown = () => {
  if (countdownTimer.value) {
    clearInterval(countdownTimer.value)
    countdownTimer.value = null
  }
}

const startCountdown = () => {
  stopCountdown()
  codeCountdown.value = 60
  countdownTimer.value = window.setInterval(() => {
    if (codeCountdown.value <= 1) {
      codeCountdown.value = 0
      stopCountdown()
      return
    }

    codeCountdown.value -= 1
  }, 1000)
}

const handleSendCode = async () => {
  if (!form.email) {
    ElMessage.warning('请先填写邮箱地址')
    return
  }

  if (isSendCodeDisabled.value) {
    return
  }

  // Validate email field before sending
  try {
    await formRef.value?.validateField('email')
  } catch {
    ElMessage.warning('请先输入有效的邮箱地址')
    return
  }

  sendingCode.value = true
  try {
    await apiSendCode({ email: form.email, purpose: 'register' })
    ElMessage.success('验证码已发送，请查收邮箱')
    startCountdown()
  } catch {
    // Error handled in interceptor
  } finally {
    sendingCode.value = false
  }
}

const handleAvatarChange = (uploadFile) => {
  const file = uploadFile?.raw
  if (!file) return
  if (file.size > MAX_AVATAR_SIZE) {
    ElMessage.warning('头像文件大小不能超过 2MB')
    return
  }
  if (!AVATAR_ACCEPT.split(',').includes(file.type)) {
    ElMessage.warning('仅支持 PNG、JPG、GIF、WebP 格式')
    return
  }
  if (avatarPreviewUrl.value) {
    URL.revokeObjectURL(avatarPreviewUrl.value)
  }
  avatarFile.value = file
  avatarPreviewUrl.value = URL.createObjectURL(file)
}

const buildRegisterFormData = () => {
  const payload = new FormData()
  payload.set('email', form.email)
  payload.set('password', form.password)
  payload.set('password_confirm', form.confirmPassword)
  payload.set('nickname', form.nickname.trim())
  payload.set('phone', form.phone.trim())
  payload.set('code', form.code.trim())
  payload.set('role', form.role)
  if (avatarFile.value) {
    payload.append('avatar', avatarFile.value)
  }

  return payload
}

const navigateToLoginAfterRegister = async () => {
  try {
    await router.push('/login')
  } catch {
    ElMessage.warning('注册成功，但未能跳转到登录页，请手动前往登录')
  }
}

const handleRegister = async () => {
  if (!formRef.value) return

  let valid = false
  await formRef.value.validate((result) => {
    valid = result
  })

  if (!valid) {
    return
  }

  loading.value = true
  errorMessage.value = ''
  try {
    await apiRegister(buildRegisterFormData())
    ElMessage.success('注册成功！请登录')
    await navigateToLoginAfterRegister()
  } catch (/** @type {any} */ err) {
    errorMessage.value = extractErrorMessage(err, '注册失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

onBeforeUnmount(() => {
  stopCountdown()
  if (avatarPreviewUrl.value) {
    URL.revokeObjectURL(avatarPreviewUrl.value)
  }
})
</script>

<template>
  <div
    class="min-h-screen flex items-center justify-center bg-gradient-to-b from-slate-50 to-white relative overflow-hidden py-12 px-4"
  >
    <!-- Decorative Orbs (Matching Landing Page) -->
    <div
      class="absolute top-[-10%] left-[-5%] w-[40%] h-[50%] rounded-full bg-blue-100/40 blur-3xl pointer-events-none"
    ></div>
    <div
      class="absolute bottom-[-10%] right-[-5%] w-[40%] h-[50%] rounded-full bg-indigo-100/40 blur-3xl pointer-events-none"
    ></div>

    <a
      class="fixed top-6 left-6 flex items-center gap-2 px-4 py-2 text-slate-600 hover:text-slate-900 hover:bg-white/80 rounded-lg backdrop-blur-sm transition-all duration-200 shadow-sm hover:shadow cursor-pointer z-10"
      @click="router.push('/')"
    >
      <el-icon><ArrowLeft /></el-icon>
      <span class="text-sm font-medium">返回首页</span>
    </a>

    <div
      class="w-full max-w-4xl bg-white rounded-xl border border-slate-200 shadow-lg overflow-hidden"
    >
      <div class="px-6 pt-6 pb-3 text-center space-y-1">
        <div class="flex items-center justify-center mb-1">
          <AuthBrandBadge />
        </div>
        <h2 class="text-xl font-bold text-slate-900">创建账号</h2>
        <p class="text-slate-500 text-sm">开始使用云析智研智能情感分析与洞察平台</p>
      </div>

      <div class="px-8 pb-6">
        <el-alert
          v-if="errorMessage"
          :title="errorMessage"
          type="error"
          show-icon
          :closable="true"
          class="mb-4"
          @close="errorMessage = ''"
        />

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-position="top"
          @keyup.enter="handleRegister"
        >
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 items-stretch">
            <section
              data-testid="register-base-section"
              class="register-section flex flex-col justify-between space-y-4 rounded-2xl border border-slate-100 bg-slate-50/50 p-6 shadow-sm"
            >
              <div class="flex items-center justify-between pb-2 border-b border-slate-200/60">
                <h3 class="text-base font-bold text-slate-800 tracking-tight">基础信息</h3>
                <span class="text-[10px] font-bold uppercase tracking-widest text-slate-400"
                  >Profile</span
                >
              </div>

              <div
                data-testid="register-base-fields"
                class="space-y-5 flex-1 flex flex-col pt-2 pb-1 justify-between"
              >
                <div class="space-y-5">
                  <!-- 头像上传区域 (紧凑立体版) -->
                  <div
                    class="relative group flex flex-col items-center justify-center gap-3 py-5 px-4 rounded-[1.25rem] border-2 border-dashed border-slate-200 bg-white hover:border-indigo-300 hover:bg-indigo-50/50 transition-all duration-300 cursor-pointer text-center"
                    @click="avatarInputRef?.$el?.querySelector('input')?.click()"
                  >
                    <div class="relative shrink-0">
                      <el-avatar
                        :size="56"
                        :src="avatarPreviewUrl || undefined"
                        class="ring-4 ring-slate-50 bg-slate-100 text-slate-400 group-hover:scale-105 transition-transform duration-300 shadow-sm"
                      >
                        <el-icon :size="24"><UserFilled /></el-icon>
                      </el-avatar>
                      <div
                        class="absolute inset-0 rounded-full bg-slate-900/50 backdrop-blur-[2px] flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all duration-200"
                      >
                        <el-icon :size="20" class="text-white"><Camera /></el-icon>
                      </div>
                    </div>
                    <div>
                      <h4
                        class="text-[13px] font-bold text-slate-700 mb-1 group-hover:text-indigo-600 transition-colors"
                      >
                        设置专属头像
                      </h4>
                      <p
                        class="text-[10px] text-slate-400 leading-normal font-medium tracking-wide"
                      >
                        支持 JPG / PNG / WEBP
                      </p>
                    </div>
                    <el-upload
                      ref="avatarInputRef"
                      :auto-upload="false"
                      :show-file-list="false"
                      :accept="AVATAR_ACCEPT"
                      :on-change="handleAvatarChange"
                      class="!absolute !opacity-0 !pointer-events-none"
                    />
                  </div>

                  <el-form-item
                    label="企业/个人昵称"
                    prop="nickname"
                    class="form-label-sm font-medium text-slate-700"
                  >
                    <el-input
                      v-model="form.nickname"
                      data-testid="register-nickname"
                      placeholder="为您起一个独特的昵称"
                      class="h-12 el-input-rounded"
                    >
                      <template #prefix>
                        <el-icon class="text-slate-400 text-lg"><User /></el-icon>
                      </template>
                    </el-input>
                  </el-form-item>

                  <el-form-item
                    label="选择身份角色"
                    prop="role"
                    class="form-label-sm font-medium text-slate-700"
                  >
                    <div class="grid grid-cols-2 gap-3 w-full">
                      <div
                        v-for="opt in roleOptions"
                        :key="opt.value"
                        class="relative flex items-center justify-center gap-2 h-12 rounded-xl border-2 cursor-pointer transition-all duration-200"
                        :class="
                          form.role === opt.value
                            ? 'border-indigo-500 bg-indigo-50 text-indigo-700 shadow-sm'
                            : 'border-slate-200 bg-white text-slate-600 hover:border-indigo-200 hover:bg-slate-50'
                        "
                        @click="form.role = opt.value"
                      >
                        <el-icon
                          :size="18"
                          class="transition-transform duration-300"
                          :class="{ 'scale-110': form.role === opt.value }"
                        >
                          <component :is="opt.value === 'analyst' ? DataLine : User" />
                        </el-icon>
                        <span class="text-sm font-bold tracking-wide">{{ opt.label }}</span>

                        <!-- Selected Indicator -->
                        <div
                          v-if="form.role === opt.value"
                          class="absolute -top-2 -right-2 flex items-center justify-center bg-white rounded-full text-indigo-500 animate-in zoom-in duration-200 shadow-sm"
                        >
                          <el-icon :size="18"><CircleCheckFilled /></el-icon>
                        </div>
                      </div>
                    </div>
                  </el-form-item>
                </div>

                <!-- 填补留白区：系统价值主张 / 权益卡片 -->
                <div class="mt-auto hidden sm:block pt-3">
                  <div
                    class="rounded-2xl bg-gradient-to-br from-indigo-50/80 to-blue-50/20 border border-indigo-100/50 p-4 relative overflow-hidden group hover:border-indigo-200/60 transition-colors duration-300"
                  >
                    <!-- 装饰光晕 -->
                    <div
                      class="absolute -right-6 -top-6 w-20 h-20 bg-indigo-400/10 rounded-full blur-2xl transition-all group-hover:bg-indigo-400/20"
                    ></div>
                    <div
                      class="absolute -left-6 -bottom-6 w-20 h-20 bg-blue-400/10 rounded-full blur-2xl transition-all group-hover:bg-blue-400/20"
                    ></div>

                    <h4
                      class="text-[12px] font-bold text-slate-800 mb-2.5 flex items-center gap-2 relative z-10"
                    >
                      <div
                        class="flex items-center justify-center w-5 h-5 rounded border border-indigo-100 bg-white text-indigo-600 shadow-sm text-xs"
                      >
                        <el-icon><Medal /></el-icon>
                      </div>
                      注册即享强大的洞察能力
                    </h4>

                    <ul class="space-y-2 text-[11px] text-slate-600 font-medium relative z-10">
                      <li class="flex items-start gap-1.5">
                        <el-icon class="text-indigo-500 mt-0.5 text-xs drop-shadow-sm"
                          ><TrendCharts
                        /></el-icon>
                        <span class="leading-relaxed group-hover:text-slate-700 transition-colors"
                          >全渠道舆情数据
                          <span class="text-indigo-600 font-bold">无死角实时追踪</span></span
                        >
                      </li>
                      <li class="flex items-start gap-1.5">
                        <el-icon class="text-indigo-500 mt-0.5 text-xs drop-shadow-sm"
                          ><Lightning
                        /></el-icon>
                        <span class="leading-relaxed group-hover:text-slate-700 transition-colors"
                          >接入开箱即用的
                          <span class="text-indigo-600 font-bold">高精度 NLP 模型</span></span
                        >
                      </li>
                      <li class="flex items-start gap-1.5">
                        <el-icon class="text-indigo-500 mt-0.5 text-xs drop-shadow-sm"
                          ><DataLine
                        /></el-icon>
                        <span class="leading-relaxed group-hover:text-slate-700 transition-colors"
                          >生成多维度大屏与
                          <span class="text-indigo-600 font-bold">全自动化研报</span></span
                        >
                      </li>
                    </ul>
                  </div>
                </div>
              </div>
            </section>

            <section
              data-testid="register-security-section"
              class="register-section flex flex-col rounded-2xl border border-slate-100 bg-white p-6 shadow-premium"
            >
              <div class="flex items-center justify-between pb-2 border-b border-slate-100 mb-4">
                <h3 class="text-base font-bold text-slate-800 tracking-tight">账号安全</h3>
                <span class="text-[10px] font-bold uppercase tracking-widest text-indigo-400/80"
                  >Security</span
                >
              </div>

              <div class="flex-1 flex flex-col pt-2">
                <el-form-item
                  label="邮箱地址"
                  prop="email"
                  class="form-label-sm font-medium text-slate-700"
                >
                  <el-input
                    v-model="form.email"
                    data-testid="register-email"
                    placeholder="name@company.com"
                    class="h-12 el-input-rounded"
                  />
                </el-form-item>

                <el-form-item
                  data-testid="register-code-group"
                  label="邮箱验证码"
                  prop="code"
                  class="form-label-sm font-medium text-slate-700"
                >
                  <div class="flex gap-3 w-full">
                    <el-input
                      v-model="form.code"
                      data-testid="register-code"
                      placeholder="6 位对应验证码"
                      maxlength="6"
                      autocomplete="one-time-code"
                      class="h-12 el-input-rounded flex-1 tracking-widest"
                      @keyup.enter.stop="handleSendCode"
                    />
                    <el-button
                      data-testid="register-send-code"
                      class="!h-12 shrink-0 !rounded-xl !border-indigo-100 hover:!bg-indigo-50 hover:!text-indigo-600 transition-colors"
                      :loading="sendingCode"
                      :disabled="isSendCodeDisabled"
                      @click="handleSendCode"
                    >
                      {{ sendCodeButtonText }}
                    </el-button>
                  </div>
                </el-form-item>

                <el-form-item
                  label="密码"
                  prop="password"
                  class="form-label-sm font-medium text-slate-700"
                >
                  <el-input
                    v-model="form.password"
                    data-testid="register-password"
                    type="password"
                    placeholder="设置高强度密码"
                    show-password
                    autocomplete="new-password"
                    class="h-12 el-input-rounded"
                  />
                </el-form-item>

                <el-form-item
                  label="确认密码"
                  prop="confirmPassword"
                  class="form-label-sm font-medium text-slate-700"
                >
                  <el-input
                    v-model="form.confirmPassword"
                    data-testid="register-confirm-password"
                    type="password"
                    placeholder="再次确认密码"
                    show-password
                    autocomplete="new-password"
                    class="h-12 el-input-rounded"
                  />
                </el-form-item>

                <el-form-item
                  label="手机号（可选）"
                  prop="phone"
                  class="form-label-sm font-medium text-slate-700"
                >
                  <el-input
                    v-model="form.phone"
                    data-testid="register-phone"
                    placeholder="绑定手机号码"
                    class="h-12 el-input-rounded"
                  />
                </el-form-item>

                <div class="pt-2">
                  <el-button
                    type="primary"
                    data-testid="register-submit"
                    class="w-full !h-12 !text-base !font-semibold !rounded-xl shadow-premium hover:-translate-y-0.5 hover:shadow-premium-hover transition-all duration-300"
                    :loading="loading"
                    @click="handleRegister"
                  >
                    立即创建账号
                  </el-button>
                </div>
              </div>
            </section>
          </div>

          <div class="relative w-full my-4">
            <div class="absolute inset-0 flex items-center">
              <div class="w-full border-t border-slate-200"></div>
            </div>
            <div class="relative flex justify-center text-xs">
              <span class="bg-white px-3 text-slate-500">或</span>
            </div>
          </div>

          <p class="text-sm text-center text-slate-600">
            已有账号？
            <a
              class="text-slate-900 hover:underline font-semibold underline-offset-4 cursor-pointer transition-all"
              @click="router.push('/login')"
            >
              立即登录
            </a>
          </p>
        </el-form>
      </div>
    </div>
  </div>
</template>

<style scoped></style>

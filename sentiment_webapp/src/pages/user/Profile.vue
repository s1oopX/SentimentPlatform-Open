<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  updateProfile as apiUpdateProfile,
  changePassword as apiChangePassword,
  deleteAccount as apiDeleteAccount,
} from '@/api/auth'
import { ElMessage, ElMessageBox } from 'element-plus'
import { User, Key, Select, WarningFilled, Delete, Upload } from '@element-plus/icons-vue'
import { buildPasswordRules } from '@/utils/passwordRules'
import { extractErrorMessage } from '@/api/request'

const authStore = useAuthStore()
const router = useRouter()
const user = computed(() => authStore.user)
const loading = ref(false)
const pwdLoading = ref(false)
const deleteLoading = ref(false)

const profileForm = reactive({
  nickname: '',
  phone: '',
  email: '',
})

/** @type {import('vue').Ref<import('element-plus').FormInstance | null>} */
const passwordFormRef = ref(null)
/** @type {import('vue').Ref<import('element-plus').FormInstance | null>} */
const deleteFormRef = ref(null)
const passwordForm = reactive({
  old_password: '',
  new_password: '',
  new_password_confirm: '',
})
const deleteForm = reactive({
  password: '',
  confirmation: '',
})

const validateNewPasswordDiffers = (_rule, value, callback) => {
  if (value && value === passwordForm.old_password) {
    callback(new Error('新密码不能与当前密码相同'))
    return
  }
  callback()
}

const validatePasswordConfirm = (_rule, value, callback) => {
  if (!value) {
    callback(new Error('请再次输入新密码'))
    return
  }
  if (value !== passwordForm.new_password) {
    callback(new Error('两次输入的新密码不一致'))
    return
  }
  callback()
}

const passwordRules = {
  old_password: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  new_password: [
    ...buildPasswordRules({ requiredMessage: '请输入新密码' }),
    { validator: validateNewPasswordDiffers, trigger: 'blur' },
  ],
  new_password_confirm: [{ required: true, validator: validatePasswordConfirm, trigger: 'blur' }],
}

const deleteRules = {
  password: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  confirmation: [
    {
      validator: (_rule, value, callback) => {
        if ((value || '').trim() !== '注销账号') {
          callback(new Error('请输入“注销账号”确认操作'))
          return
        }
        callback()
      },
      trigger: 'blur',
    },
  ],
}

watch(
  user,
  (u) => {
    if (!u) return
    profileForm.nickname = u.nickname || ''
    profileForm.phone = u.phone || ''
    profileForm.email = u.email || ''
  },
  { immediate: true }
)

const displayName = computed(
  () => user.value?.display_name || user.value?.nickname || user.value?.email || ''
)
const displayInitial = computed(() => displayName.value.charAt(0)?.toUpperCase() || '用')
const avatarUrl = computed(() => user.value?.avatar || '')
const avatarUploading = ref(false)
/** @type {import('vue').Ref<import('vue').ComponentPublicInstance | null>} */
const avatarInputRef = ref(null)

const AVATAR_ACCEPT = 'image/png,image/jpeg,image/gif,image/webp'

const handleAvatarChange = async (uploadFile) => {
  const file = uploadFile?.raw
  if (!file) return
  if (file.size > 2 * 1024 * 1024) {
    ElMessage.warning('头像文件大小不能超过 2MB')
    return
  }
  if (!AVATAR_ACCEPT.split(',').includes(file.type)) {
    ElMessage.warning('仅支持 PNG、JPG、GIF、WebP 格式')
    return
  }
  avatarUploading.value = true
  try {
    const formData = new FormData()
    formData.append('avatar', file)
    const res = await apiUpdateProfile(formData)
    authStore.user = res.data
    ElMessage.success('头像已更新')
  } catch (/** @type {any} */ err) {
    ElMessage.error(extractErrorMessage(err, '头像上传失败，请稍后重试'))
  } finally {
    avatarUploading.value = false
  }
}

const navigateTo = (path) => router.replace(path)

const handleUpdateProfile = async () => {
  loading.value = true
  try {
    const res = await apiUpdateProfile({
      nickname: profileForm.nickname,
      phone: profileForm.phone,
    })
    authStore.user = res.data
    ElMessage.success('个人资料已更新')
  } catch (/** @type {any} */ err) {
    ElMessage.error(extractErrorMessage(err, '个人资料更新失败，请稍后重试'))
  } finally {
    loading.value = false
  }
}

const handleUpdatePassword = async () => {
  if (!passwordFormRef.value) return
  const valid = await passwordFormRef.value.validate().catch(() => false)
  if (!valid) return

  pwdLoading.value = true
  try {
    await apiChangePassword({
      old_password: passwordForm.old_password,
      new_password: passwordForm.new_password,
      new_password_confirm: passwordForm.new_password_confirm,
    })
    passwordForm.old_password = ''
    passwordForm.new_password = ''
    passwordForm.new_password_confirm = ''
    passwordFormRef.value?.resetFields?.()
    await authStore.forceSessionReset({
      noticeLevel: 'success',
      noticeText: '密码已修改，请使用新密码登录',
      navigate: navigateTo,
    })
  } catch {
    // Error handled in interceptor
  } finally {
    pwdLoading.value = false
  }
}

const handleDeleteAccount = async () => {
  if (!deleteFormRef.value) return
  const valid = await deleteFormRef.value.validate().catch(() => false)
  if (!valid) return

  try {
    await ElMessageBox.confirm(
      '账号注销后将立即退出登录，历史数据会保留为匿名记录。确定继续吗？',
      '确认注销账号',
      {
        confirmButtonText: '确认注销',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger',
      }
    )
  } catch {
    return
  }

  deleteLoading.value = true
  try {
    await apiDeleteAccount({
      password: deleteForm.password,
      confirmation: deleteForm.confirmation,
    })
    authStore.resetLocalSession()
    ElMessage.success('账号已注销')
    await router.replace('/login')
  } catch (/** @type {any} */ err) {
    ElMessage.error(extractErrorMessage(err, '账号注销失败，请稍后重试'))
  } finally {
    deleteLoading.value = false
  }
}
</script>

<template>
  <div class="max-w-3xl mx-auto space-y-6">
    <!-- Profile Header -->
    <div
      class="rounded-xl border border-blue-100 bg-gradient-to-r from-blue-50/80 to-slate-50/80 p-6 shadow-sm"
    >
      <div class="flex items-center gap-5">
        <el-tooltip content="点击更换头像" placement="bottom">
          <div
            class="relative shrink-0 cursor-pointer"
            @click="avatarInputRef?.$el?.querySelector('input')?.click()"
          >
            <el-avatar
              :size="56"
              :src="avatarUrl || undefined"
              class="text-lg bg-blue-100 text-blue-700 font-bold shadow"
              >{{ displayInitial }}</el-avatar
            >
            <div
              class="absolute -bottom-0.5 -right-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-blue-600 ring-2 ring-white"
            >
              <el-icon :size="11" class="text-white"><Upload /></el-icon>
            </div>
            <el-upload
              ref="avatarInputRef"
              :auto-upload="false"
              :show-file-list="false"
              accept="image/png,image/jpeg,image/gif,image/webp"
              :on-change="handleAvatarChange"
              class="!absolute !opacity-0 !pointer-events-none"
            />
          </div>
        </el-tooltip>
        <div class="flex-1 min-w-0">
          <h1 class="text-lg font-bold text-slate-900 truncate">{{ displayName }}</h1>
          <p class="text-sm text-slate-500 mt-0.5 truncate">{{ user?.email }}</p>
        </div>
        <span
          class="shrink-0 rounded-lg bg-white/80 border border-blue-200 px-3 py-1 text-xs font-semibold text-blue-600"
        >
          {{ user?.role_display || user?.role || 'User' }}
        </span>
      </div>
    </div>

    <!-- Basic Info -->
    <div class="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      <div class="flex items-center gap-2 px-6 py-4 border-b border-slate-100">
        <el-icon class="text-blue-600"><User /></el-icon>
        <h3 class="font-semibold text-slate-900">基础资料</h3>
      </div>
      <div class="p-6">
        <el-form :model="profileForm" label-position="top">
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <el-form-item label="昵称">
              <el-input
                v-model="profileForm.nickname"
                placeholder="您的称呼"
                class="h-11 el-input-rounded"
              />
            </el-form-item>
            <el-form-item label="手机号">
              <el-input
                v-model="profileForm.phone"
                placeholder="绑定手机"
                class="h-11 el-input-rounded"
              />
            </el-form-item>
          </div>
          <el-form-item label="邮箱地址">
            <el-input v-model="profileForm.email" disabled class="h-11 el-input-rounded" />
            <p class="text-xs text-slate-400 mt-1">邮箱作为登录账号暂不可更改</p>
          </el-form-item>
          <div class="pt-2">
            <el-button
              type="primary"
              :loading="loading"
              class="!h-11 !rounded-xl !px-6 !font-semibold"
              @click="handleUpdateProfile"
            >
              <el-icon class="mr-1.5"><Select /></el-icon>
              保存修改
            </el-button>
          </div>
        </el-form>
      </div>
    </div>

    <!-- Change Password -->
    <div class="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      <div class="flex items-center gap-2 px-6 py-4 border-b border-slate-100">
        <el-icon class="text-amber-600"><Key /></el-icon>
        <h3 class="font-semibold text-slate-900">更改密码</h3>
      </div>
      <div class="p-6">
        <el-form
          ref="passwordFormRef"
          :model="passwordForm"
          :rules="passwordRules"
          label-position="top"
        >
          <el-form-item label="当前密码" prop="old_password">
            <el-input
              v-model="passwordForm.old_password"
              type="password"
              show-password
              placeholder="验证当前身份"
              autocomplete="current-password"
              class="h-11 el-input-rounded"
            />
          </el-form-item>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <el-form-item label="新密码" prop="new_password">
              <el-input
                v-model="passwordForm.new_password"
                type="password"
                show-password
                placeholder="至少 8 位，含字母/数字/符号至少两种"
                autocomplete="new-password"
                class="h-11 el-input-rounded"
              />
            </el-form-item>
            <el-form-item label="确认新密码" prop="new_password_confirm">
              <el-input
                v-model="passwordForm.new_password_confirm"
                type="password"
                show-password
                placeholder="再次输入新密码"
                autocomplete="new-password"
                class="h-11 el-input-rounded"
              />
            </el-form-item>
          </div>
          <div class="pt-2">
            <el-button
              type="primary"
              plain
              :loading="pwdLoading"
              class="!h-11 !rounded-xl !px-6 !font-semibold"
              @click="handleUpdatePassword"
            >
              更新密码
            </el-button>
          </div>
        </el-form>
      </div>
    </div>

    <!-- Danger Zone (管理员不显示注销) -->
    <div
      v-if="authStore.user?.role !== 'admin'"
      class="rounded-xl border border-red-200 bg-white shadow-sm overflow-hidden"
    >
      <div class="flex items-center gap-2 px-6 py-4 border-b border-red-100 bg-red-50/50">
        <el-icon class="text-red-500"><WarningFilled /></el-icon>
        <h3 class="font-semibold text-red-600">危险操作</h3>
      </div>
      <div class="p-6 space-y-4">
        <p class="text-sm leading-relaxed text-slate-600">
          注销后账号会被禁用并匿名化，当前会话立即退出。请输入当前密码，并输入「注销账号」确认。
        </p>
        <el-form ref="deleteFormRef" :model="deleteForm" :rules="deleteRules" label-position="top">
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <el-form-item label="当前密码" prop="password">
              <el-input
                v-model="deleteForm.password"
                type="password"
                show-password
                placeholder="验证当前身份"
                autocomplete="current-password"
                class="h-11 el-input-rounded"
              />
            </el-form-item>
            <el-form-item label="确认文本" prop="confirmation">
              <el-input
                v-model="deleteForm.confirmation"
                placeholder="请输入：注销账号"
                class="h-11 el-input-rounded"
              />
            </el-form-item>
          </div>
          <el-button
            type="danger"
            :loading="deleteLoading"
            class="!h-11 !rounded-xl !px-6 !font-semibold"
            @click="handleDeleteAccount"
          >
            <el-icon class="mr-1.5"><Delete /></el-icon>
            注销账号
          </el-button>
        </el-form>
      </div>
    </div>
  </div>
</template>

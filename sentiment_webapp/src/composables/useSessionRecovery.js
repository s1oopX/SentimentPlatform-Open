import { ElMessage, ElMessageBox } from 'element-plus'
import { showLogoutNotice } from '@/utils/notification'

let sessionRecoveryDialogOpen = false

export function getSessionRecoveryRedirect(to) {
  return {
    name: 'Login',
    query: { redirect: to.fullPath },
  }
}

export async function sendToLoginBranch(authStore, to, router) {
  try {
    const result = await authStore.logout()
    showLogoutNotice(result)
  } catch (/** @type {any} */ error) {
    ElMessage.error(error?.response?.data?.error || '服务端登出失败，请稍后重试')
    authStore.resetLocalSession?.()
  }
  try {
    await router.push(getSessionRecoveryRedirect(to))
  } catch {
    // Navigation failure is non-critical during session recovery
  }
}

export async function recoverProtectedSession(authStore, to, router) {
  if (sessionRecoveryDialogOpen) {
    return
  }

  sessionRecoveryDialogOpen = true

  try {
    while (authStore.token && !authStore.user && authStore.profileLoadFailed) {
      try {
        await ElMessageBox.confirm('会话未恢复，请重试或退出登录', '会话异常', {
          confirmButtonText: '重试',
          cancelButtonText: '退出登录',
          type: 'warning',
          distinguishCancelAndClose: true,
        })
      } catch (action) {
        if (action === 'cancel' || action === 'close') {
          await sendToLoginBranch(authStore, to, router)
        }
        return
      }

      authStore.clearProfileLoadFailed()
      await authStore.fetchProfile()

      if (authStore.user) {
        try {
          await router.replace(to.fullPath)
        } catch {
          // Navigation failure is non-critical during session recovery
        }
        return
      }

      if (!authStore.token || !authStore.profileLoadFailed) {
        await sendToLoginBranch(authStore, to, router)
        return
      }
    }
  } finally {
    sessionRecoveryDialogOpen = false
  }
}

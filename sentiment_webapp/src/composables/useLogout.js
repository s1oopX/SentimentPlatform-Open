import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { showLogoutNotice, showMessageByLevel } from '@/utils/notification'

/**
 * 共享登出流程：调用 auth store 的 logout，展示登出提示，可选跳转；
 * 失败时以 error 级别展示服务端返回的错误或默认提示。
 *
 * @param {object} [options]
 * @param {string | null} [options.redirectTo='/login']  登出成功后跳转的路径。传 null 时不跳转。
 */
export function useLogout({ redirectTo = '/login' } = {}) {
  const router = useRouter()
  const authStore = useAuthStore()

  const handleLogout = async () => {
    try {
      const result = await authStore.logout()
      showLogoutNotice(result)
      if (redirectTo) {
        await router.push(redirectTo)
      }
    } catch (/** @type {any} */ error) {
      showMessageByLevel('error', error?.response?.data?.error || '服务端登出失败，请稍后重试')
    }
  }

  return { handleLogout }
}

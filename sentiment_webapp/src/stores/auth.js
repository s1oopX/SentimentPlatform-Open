import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login as loginApi, logout as logoutApi, getProfile as getProfileApi } from '@/api/auth'
import { requestTokenRefresh } from '@/api/request'
import { showMessageByLevel } from '@/utils/notification'
import { clearSessionScopedDrafts } from '@/utils/draftStorage'
import {
  clearStoredTokenPair,
  getStoredToken,
  setStoredTokenPair,
  subscribeToTokenStorage,
} from '@/utils/tokenStorage'

/**
 * @typedef {object} AuthUser
 * @property {number} [id]
 * @property {string} [role]
 * @property {string} [display_name]
 * @property {string} [nickname]
 * @property {string} [email]
 * @property {string} [avatar]
 * @property {string} [phone]
 * @property {string} [role_display]
 */

/**
 * @typedef {object} SessionResetOptions
 * @property {'success' | 'warning' | 'info' | 'error'} [noticeLevel]
 * @property {string} [noticeText]
 * @property {(path: string) => Promise<unknown> | unknown} [navigate]
 * @property {string} [redirectTo]
 */

let applyStoredTokenSnapshot = null
let pendingSnapshot = null
let silentRefreshTimerId = null

const SILENT_REFRESH_LEEWAY_MS = 60_000
const SILENT_REFRESH_MIN_DELAY_MS = 5_000

const decodeBase64UrlJson = (value) => {
  if (!value || typeof globalThis.atob !== 'function') {
    return null
  }

  try {
    const base64 = value.replace(/-/g, '+').replace(/_/g, '/')
    const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, '=')
    return JSON.parse(globalThis.atob(padded))
  } catch {
    return null
  }
}

const getJwtExpiresAtMs = (accessToken) => {
  const payload = decodeBase64UrlJson(String(accessToken || '').split('.')[1])
  const exp = Number(payload?.exp)
  return Number.isFinite(exp) && exp > 0 ? exp * 1000 : null
}

const clearSilentRefreshTimer = () => {
  if (silentRefreshTimerId !== null) {
    clearTimeout(silentRefreshTimerId)
    silentRefreshTimerId = null
  }
}

subscribeToTokenStorage((snapshot) => {
  if (applyStoredTokenSnapshot) {
    applyStoredTokenSnapshot(snapshot)
  } else {
    pendingSnapshot = snapshot
  }
})

export const useAuthStore = defineStore('auth', () => {
  const token = ref(getStoredToken())
  /** @type {import('vue').Ref<AuthUser|null>} */ const user = ref(null)
  /** 有 token 但拉取资料失败（网络/5xx），非 401/403 */
  const profileLoadFailed = ref(false)
  /** @type {import('vue').Ref<number | null>} */ const profileFetchedAt = ref(null)

  applyStoredTokenSnapshot = ({ token: nextToken }) => {
    token.value = nextToken
    scheduleSilentRefresh()
  }

  if (pendingSnapshot) {
    applyStoredTokenSnapshot(pendingSnapshot)
    pendingSnapshot = null
  }

  const setToken = (newToken) => {
    setStoredTokenPair({ token: newToken || '' })
  }

  const setTokenPair = ({ token: newToken = '' } = {}) => {
    setStoredTokenPair({
      token: newToken || '',
    })
  }

  const clearToken = () => {
    clearStoredTokenPair()
  }

  const markProfileFetched = (timestamp = Date.now()) => {
    profileFetchedAt.value = timestamp
  }

  const clearProfileFetchedAt = () => {
    profileFetchedAt.value = null
  }

  const requestSilentRefresh = async () => {
    // Refresh token is in HttpOnly cookie — not stored locally.
    // Only check access token; the server validates the cookie.
    if (!token.value) {
      return false
    }

    try {
      await requestTokenRefresh()
      return true
    } catch {
      return false
    }
  }

  const scheduleSilentRefresh = () => {
    clearSilentRefreshTimer()

    // Refresh token is in HttpOnly cookie — not stored locally.
    // Only check access token existence; the refresh cookie is
    // validated server-side when the refresh request is made.
    if (!token.value) {
      return
    }

    const expiresAtMs = getJwtExpiresAtMs(token.value)
    if (!expiresAtMs) {
      return
    }

    const delayMs = expiresAtMs - Date.now() - SILENT_REFRESH_LEEWAY_MS
    silentRefreshTimerId = setTimeout(
      () => {
        silentRefreshTimerId = null
        void requestSilentRefresh()
      },
      Math.max(delayMs, SILENT_REFRESH_MIN_DELAY_MS)
    )
  }

  const shouldRefreshProfile = ({ force = false, maxAgeMs = 30_000 } = {}) => {
    if (!token.value) {
      return false
    }

    if (force) {
      return true
    }

    if (!user.value || profileFetchedAt.value == null) {
      return true
    }

    return Date.now() - profileFetchedAt.value > maxAgeMs
  }

  const resetLocalSession = () => {
    clearSilentRefreshTimer()
    clearToken()
    user.value = null
    profileLoadFailed.value = false
    clearProfileFetchedAt()
    clearSessionScopedDrafts()
  }

  /**
   * @param {SessionResetOptions} [options={}]
   */
  const forceSessionReset = async ({
    noticeLevel = 'success',
    noticeText = '',
    navigate,
    redirectTo = '/login',
  } = {}) => {
    resetLocalSession()

    showMessageByLevel(noticeLevel, noticeText)

    if (typeof navigate === 'function') {
      await navigate(redirectTo)
    }
  }

  const buildLogoutResult = (mode) => {
    if (mode === 'server') {
      return {
        mode,
        noticeLevel: 'success',
        noticeText: '已登出',
      }
    }

    if (mode === 'local-only') {
      return {
        mode,
        noticeLevel: 'warning',
        noticeText: '会话已失效，已清理本地登录状态',
      }
    }

    return {
      mode: 'forced-local',
      noticeLevel: 'info',
      noticeText: '服务端退出登录失败，已清理本地登录状态',
    }
  }

  const isLocalOnlyLogoutStatus = (error) => {
    const status = error?.response?.status
    return status === 400 || status === 401
  }

  const login = async (credentials) => {
    const res = await loginApi(credentials)
    const responseData = res?.data || {}
    const newToken = responseData.access_token || responseData.access || responseData.token || ''
    const newUser = responseData.user || null

    if (!newToken || !newUser) {
      clearToken()
      user.value = null
      clearProfileFetchedAt()
      throw new Error('Incomplete login response')
    }

    // Refresh token is set by backend via HttpOnly cookie — no need to store it
    setTokenPair({ token: newToken })
    user.value = newUser
    markProfileFetched()
    scheduleSilentRefresh()
  }

  const logout = async () => {
    // Refresh token is in HttpOnly cookie — backend reads it from there
    try {
      await logoutApi({})
      resetLocalSession()
      return buildLogoutResult('server')
    } catch (/** @type {any} */ error) {
      if (isLocalOnlyLogoutStatus(error)) {
        resetLocalSession()
        return buildLogoutResult('local-only')
      }

      resetLocalSession()
      return buildLogoutResult('forced-local')
    }
  }

  const fetchProfile = async () => {
    if (!token.value) return
    profileLoadFailed.value = false
    try {
      const res = await getProfileApi()
      user.value = res.data
      profileLoadFailed.value = false
      markProfileFetched()
    } catch (/** @type {any} */ error) {
      const status = error?.response?.status
      if (status === 401 || status === 403) {
        resetLocalSession()
      } else {
        user.value = null
        profileLoadFailed.value = true
        clearProfileFetchedAt()
      }
    }
  }

  const clearProfileLoadFailed = () => {
    profileLoadFailed.value = false
  }

  scheduleSilentRefresh()

  return {
    token,
    user,
    profileLoadFailed,
    profileFetchedAt,
    setToken,
    clearToken,
    resetLocalSession,
    forceSessionReset,
    clearProfileLoadFailed,
    shouldRefreshProfile,
    login,
    logout,
    fetchProfile,
    setTokenPair,
  }
})

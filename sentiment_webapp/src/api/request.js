import axios from 'axios'
import {
  getStoredToken,
  clearStoredTokenPair,
  setStoredTokenPair,
  subscribeToTokenStorage,
} from '@/utils/tokenStorage'

const PUBLIC_AUTH_ENDPOINTS = new Set([
  '/auth/login/',
  '/auth/register/',
  '/auth/send-code/',
  '/auth/reset-password/',
  '/auth/refresh/',
])
const LOGOUT_ENDPOINT = '/auth/logout/'
const DEFAULT_ERROR_MESSAGE = '请求失败，请稍后重试'
const SESSION_EXPIRED_MESSAGE = '登录状态已过期，请重新登录'
const NETWORK_ERROR_MESSAGE = '网络异常，请检查服务是否启动'
// Only used as base for new URL(relativePath, base) to extract pathname — never sent over network
const URL_FALLBACK_ORIGIN = 'http://localhost'
/** @type {(...args: any[]) => void} */ const noop = (..._args) => {}
let redirectingToLogin = false
/** @type {Promise<any>|null} */ let refreshPromise = null
/** @type {{ onSessionExpired: Function, onRequestError: Function }} */ let requestSideEffects = {
  onSessionExpired: noop,
  onRequestError: noop,
}

export const configureRequestSideEffects = ({
  onSessionExpired = noop,
  onRequestError = noop,
} = {}) => {
  requestSideEffects = {
    onSessionExpired,
    onRequestError,
  }
}

subscribeToTokenStorage(({ token }) => {
  if (token) {
    redirectingToLogin = false
  }
})

/** @param {any} payload @returns {string} */ const pickMessageFromPayload = (payload) => {
  if (!payload) {
    return ''
  }

  if (typeof payload === 'string') {
    return payload
  }

  if (Array.isArray(payload)) {
    return pickMessageFromPayload(payload[0])
  }

  if (typeof payload === 'object') {
    if (payload.detail || payload.message || payload.error) {
      return payload.detail || payload.message || payload.error
    }

    for (const value of Object.values(payload)) {
      /** @type {string} */ const nestedMessage = pickMessageFromPayload(value)
      if (nestedMessage) {
        return nestedMessage
      }
    }
  }

  return ''
}

/** @param {any} error @param {string} [fallback] */
export const extractErrorMessage = (error, fallback = DEFAULT_ERROR_MESSAGE) => {
  const message = pickMessageFromPayload(error?.response?.data)
  return message || fallback
}

const request = axios.create({
  baseURL: '/api',
  timeout: 10000,
  withCredentials: true,
})

/** @param {{ url?:string, baseURL?:string, method?:string, suppressErrorMessage?:boolean }} [config] */
const normalizeRequestPath = (config = {}) => {
  const rawUrl = config.url || ''
  if (!rawUrl) {
    return ''
  }

  let pathname
  try {
    pathname = new URL(rawUrl, URL_FALLBACK_ORIGIN).pathname
  } catch {
    pathname = rawUrl.split('?')[0].split('#')[0]
  }

  const baseURL = config.baseURL || request?.defaults?.baseURL || ''
  let basePath = ''
  if (baseURL) {
    try {
      basePath = new URL(baseURL, URL_FALLBACK_ORIGIN).pathname
    } catch {
      basePath = baseURL
    }
  }

  if (basePath && pathname.startsWith(basePath.endsWith('/') ? basePath : `${basePath}/`)) {
    pathname = pathname.slice(basePath.length) || '/'
  }

  if (!pathname.startsWith('/')) {
    pathname = `/${pathname}`
  }

  return pathname
}

/** @param {{ url?:string, baseURL?:string, method?:string, suppressErrorMessage?:boolean }} [config] */
const isPublicAuthRequest = (config = {}) => PUBLIC_AUTH_ENDPOINTS.has(normalizeRequestPath(config))

/** @param {{ url?:string, baseURL?:string, method?:string, suppressErrorMessage?:boolean }} [config] */
const isLogoutRequest = (config = {}) => {
  return (
    normalizeRequestPath(config) === LOGOUT_ENDPOINT &&
    (config.method || '').toLowerCase() === 'post'
  )
}

/** @param {{ url?:string, baseURL?:string, method?:string, suppressErrorMessage?:boolean }} [config] */
const shouldSuppressErrorMessage = (config = {}) => Boolean(config?.suppressErrorMessage)

/** @param {any} headers @param {string} token */
const withAuthorizationHeader = (headers, token) => {
  const nextHeaders =
    typeof axios?.AxiosHeaders?.from === 'function'
      ? axios.AxiosHeaders.from(headers || {})
      : headers && typeof headers === 'object'
        ? headers
        : {}

  if (typeof nextHeaders.set === 'function') {
    nextHeaders.set('Authorization', `Bearer ${token}`)
  } else {
    nextHeaders.Authorization = `Bearer ${token}`
  }

  return nextHeaders
}

const clearSessionTokens = () => {
  clearStoredTokenPair()
}

/** @param {{ message: string, error: any }} __0 */
const emitRequestError = ({ message, error }) => {
  requestSideEffects.onRequestError({ message, error })
}

/** @param {any} error */
const handleSessionExpired = (error) => {
  if (redirectingToLogin) {
    return Promise.reject(error)
  }

  redirectingToLogin = true
  clearSessionTokens()
  requestSideEffects.onSessionExpired({
    message: SESSION_EXPIRED_MESSAGE,
    error,
  })

  return Promise.reject(error)
}

export const requestTokenRefresh = async () => {
  if (refreshPromise) {
    return refreshPromise
  }

  // Refresh token is in HttpOnly cookie — no need to read from storage
  refreshPromise = axios
    .post(
      `${request.defaults.baseURL}/auth/refresh/`,
      {},
      {
        timeout: 10000,
        withCredentials: true,
      }
    )
    .then((res) => {
      const accessToken = res?.data?.access_token || res?.data?.access || res?.data?.token || ''
      // New refresh token is set by backend via Set-Cookie; not in response body
      if (!accessToken) {
        throw new Error('missing refreshed access token')
      }
      setStoredTokenPair({ token: accessToken })
      return {
        accessToken,
      }
    })
    .finally(() => {
      refreshPromise = null
    })

  return refreshPromise
}

// Request interceptor
request.interceptors.request.use(
  (config) => {
    const token = getStoredToken()
    if (token && !isPublicAuthRequest(config)) {
      config.headers = withAuthorizationHeader(config.headers, token)
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor
request.interceptors.response.use(
  (response) => {
    return response
  },
  async (error) => {
    if (error.response) {
      const status = error.response.status
      const originalRequest = error.config || {}
      const isPublicAuthEndpoint = isPublicAuthRequest(originalRequest)
      const isLogoutEndpoint = isLogoutRequest(originalRequest)
      if (status === 401 && !isPublicAuthEndpoint) {
        if (originalRequest._retry) {
          if (isLogoutEndpoint) {
            return Promise.reject(error)
          }
          return handleSessionExpired(error)
        }

        // NOTE: HttpOnly cookies cannot be read by JS, so we assume the refresh
        // cookie exists after login. If it doesn't (e.g. browser cleared cookies),
        // the refresh request will fail and the user is redirected to login —
        // one extra network round-trip, but no security impact.
        try {
          const refreshed = await requestTokenRefresh()
          originalRequest._retry = true
          originalRequest.headers = withAuthorizationHeader(
            originalRequest.headers,
            refreshed.accessToken
          )
          return request(originalRequest)
        } catch {
          if (isLogoutEndpoint) {
            return Promise.reject(error)
          }
          return handleSessionExpired(error)
        }
      } else if (status === 401) {
        return Promise.reject(error)
      } else if (!shouldSuppressErrorMessage(error.config)) {
        emitRequestError({
          message: extractErrorMessage(error),
          error,
        })
      }
    } else if (!shouldSuppressErrorMessage(error.config)) {
      emitRequestError({
        message: NETWORK_ERROR_MESSAGE,
        error,
      })
    }
    return Promise.reject(error)
  }
)

export default request

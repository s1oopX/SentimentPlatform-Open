import request from './request'

/**
 * @param {Record<string, any>} [payload={}]
 */
const normalizeTokenPayload = (payload = {}) => {
  /** @type {{ token: string, access_token: string }} */
  const normalized = {
    token: payload.token || payload.access || payload.access_token || '',
    access_token: payload.access_token || payload.access || payload.token || '',
  }

  return normalized
}

/** @param {object} data */
export function sendCode(data) {
  return request.post('/auth/send-code/', data)
}

export function getCaptcha() {
  return request.get('/auth/captcha/')
}

/** @param {object} data */
export function register(data) {
  const config = {}

  if (typeof FormData !== 'undefined' && data instanceof FormData) {
    config.headers = {
      'Content-Type': 'multipart/form-data',
    }
  }

  return request.post('/auth/register/', data, config)
}

/** @param {object} data */
export function login(data) {
  return request.post('/auth/login/', data).then((res) => ({
    ...res,
    data: {
      ...res.data,
      ...normalizeTokenPayload(res.data),
    },
  }))
}

export function getProfile() {
  return request.get('/auth/profile/', { suppressErrorMessage: true })
}

/** @param {object} data */
export function updateProfile(data) {
  return request.put('/auth/profile/', data, { suppressErrorMessage: true })
}

/** @param {object} data */
export function changePassword(data) {
  return request.post('/auth/change-password/', data, { suppressErrorMessage: true })
}

/** @param {object} data */
export function deleteAccount(data) {
  return request.delete('/auth/delete-account/', {
    data,
    suppressErrorMessage: true,
  })
}

/** @param {object} data */
export function resetPassword(data) {
  return request.post('/auth/reset-password/', data, { suppressErrorMessage: true })
}

/**
 * @param {Record<string, any>} [data={}]
 */
export function logout(data = {}) {
  return request.post('/auth/logout/', data, {
    suppressErrorMessage: true,
  })
}

/**
 * 登录账号支持邮箱或国内手机号二选一。
 *
 * - 邮箱：使用 RFC5322 简化正则
 * - 手机号：11 位，首位 1，次位 3-9（中国大陆当前常见段）
 *
 * 前端检测输入类型后，按对应键 (`email` / `phone`) 传给后端 `/auth/login/`。
 * 后端仍需要在一个端点上同时接受这两种键值。
 */

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const PHONE_REGEX = /^1[3-9]\d{9}$/

export const LOGIN_IDENTIFIER_TYPES = Object.freeze({
  EMAIL: 'email',
  PHONE: 'phone',
})

/**
 * @param {string} value
 * @returns {'email' | 'phone' | null}
 */
export function detectLoginIdentifierType(value) {
  const trimmed = String(value || '').trim()
  if (!trimmed) return null
  if (EMAIL_REGEX.test(trimmed)) return LOGIN_IDENTIFIER_TYPES.EMAIL
  if (PHONE_REGEX.test(trimmed)) return LOGIN_IDENTIFIER_TYPES.PHONE
  return null
}

/**
 * 将登录表单规范化为后端 payload。
 *
 * @param {{ identifier: string, password: string }} form
 * @returns {{ email?: string, phone?: string, password: string } | null}
 */
export function buildLoginPayload(form) {
  const trimmed = String(form?.identifier || '').trim()
  const type = detectLoginIdentifierType(trimmed)
  if (!type) return null

  const payload = { password: form.password }
  if (type === LOGIN_IDENTIFIER_TYPES.EMAIL) {
    payload.email = trimmed
  } else {
    payload.phone = trimmed
  }
  return payload
}

/**
 * el-form 使用的 validator。
 */
export const validateLoginIdentifier = (_rule, value, callback) => {
  if (!value) {
    callback(new Error('请输入邮箱或手机号'))
    return
  }
  if (!detectLoginIdentifierType(value)) {
    callback(new Error('请输入有效的邮箱或 11 位手机号'))
    return
  }
  callback()
}

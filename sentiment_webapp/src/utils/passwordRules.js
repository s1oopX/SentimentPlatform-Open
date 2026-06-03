/**
 * 密码强度策略：
 * - 长度至少 8 位
 * - 四类字符（大写、小写、数字、特殊）中至少出现 2 类
 *
 * 提供 Element Plus `el-form` 可直接使用的 rule 数组，以及独立的 validator
 * 便于在非 el-form 场景（如 store action、批量处理）复用。
 */

export const PASSWORD_MIN_LENGTH = 8
const REQUIRED_CHAR_CLASSES = 2

const CHAR_CLASS_PATTERNS = {
  lowercase: /[a-z]/,
  uppercase: /[A-Z]/,
  digit: /\d/,
  special: /[^A-Za-z0-9]/,
}

/**
 * @param {string} value
 * @returns {{ valid: boolean, reason: string }}
 */
export function validatePasswordStrength(value) {
  if (!value) {
    return { valid: false, reason: '请输入密码' }
  }

  if (value.length < PASSWORD_MIN_LENGTH) {
    return {
      valid: false,
      reason: `密码长度至少 ${PASSWORD_MIN_LENGTH} 位`,
    }
  }

  const classesPresent = Object.values(CHAR_CLASS_PATTERNS).filter((pattern) =>
    pattern.test(value)
  ).length

  if (classesPresent < REQUIRED_CHAR_CLASSES) {
    return {
      valid: false,
      reason: '密码需同时包含大小写字母、数字、特殊字符中的至少 2 种',
    }
  }

  return { valid: true, reason: '' }
}

/**
 * 构造 el-form 使用的 rule 数组。
 * @param {object} [options]
 * @param {boolean} [options.required=true]
 * @param {string} [options.requiredMessage]
 * @returns {Array<object>}
 */
export function buildPasswordRules({ required = true, requiredMessage = '请输入密码' } = {}) {
  const rules = []
  if (required) {
    rules.push({ required: true, message: requiredMessage, trigger: 'blur' })
  }
  rules.push({
    validator: (_rule, value, callback) => {
      if (!required && !value) {
        callback()
        return
      }
      const { valid, reason } = validatePasswordStrength(value)
      if (valid) {
        callback()
      } else {
        callback(new Error(reason))
      }
    },
    trigger: 'blur',
  })
  return rules
}

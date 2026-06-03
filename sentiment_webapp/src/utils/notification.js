import { ElMessage } from 'element-plus'

const SUPPORTED_LEVELS = new Set(['success', 'warning', 'info', 'error'])

export function showMessageByLevel(level, message) {
  if (!message) return
  const safeLevel = SUPPORTED_LEVELS.has(level) ? level : 'info'
  ElMessage[safeLevel](message)
}

export function showLogoutNotice(result) {
  if (!result?.noticeLevel || !result?.noticeText) return
  showMessageByLevel(result.noticeLevel, result.noticeText)
}

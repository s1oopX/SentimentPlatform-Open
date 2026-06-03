import { ElMessage } from 'element-plus'
import { reactive } from 'vue'
import { ElMessageBox } from 'element-plus'
import {
  activateTrainingRunModel,
  deleteTrainingRecord,
  retryTrainingRecordPostRun,
  retryTrainingRecord,
} from '@/api/admin'
import { getRunId } from './trainingConstants'

/**
 * @param {{ onReload: (opts?: object) => Promise<boolean>, errorMessage: import('vue').Ref<string> }} deps
 */
export function useTrainingActions({ onReload, errorMessage }) {
  const actionLoading = reactive({
    retry: false,
    retryPostRun: false,
    activate: false,
    delete: false,
  })

  const handleRetry = async (recordId) => {
    if (actionLoading.retry) return
    const runId = getRunId(recordId)
    actionLoading.retry = true
    try {
      await retryTrainingRecord(runId)
      ElMessage.success('训练任务重试请求已提交')
      const refreshed = await onReload({ preserveDetailRecordId: recordId })
      if (!refreshed) ElMessage.warning('刷新失败，页面可能陈旧')
    } catch (/** @type {any} */ err) {
      errorMessage.value = err?.response?.data?.error || '重试训练任务失败，请稍后重试'
      ElMessage.error(errorMessage.value)
    } finally {
      actionLoading.retry = false
    }
  }

  const handleRetryPostRun = async (recordId) => {
    if (actionLoading.retryPostRun) return
    const runId = getRunId(recordId)
    actionLoading.retryPostRun = true
    try {
      await retryTrainingRecordPostRun(runId)
      ElMessage.success('后处理重试已提交')
      const refreshed = await onReload({ preserveDetailRecordId: recordId })
      if (!refreshed) ElMessage.warning('刷新失败，页面可能陈旧')
    } catch (/** @type {any} */ err) {
      errorMessage.value = err?.response?.data?.error || '重试后处理失败，请稍后重试'
      ElMessage.error(errorMessage.value)
    } finally {
      actionLoading.retryPostRun = false
    }
  }

  const handleActivate = async (recordId) => {
    if (actionLoading.activate) return
    const runId = getRunId(recordId)
    try {
      await ElMessageBox.confirm(
        '激活后将切换线上情感分析模型，后续用户分析会使用该模型。',
        '确认激活模型',
        {
          confirmButtonText: '激活',
          cancelButtonText: '取消',
          type: 'warning',
        }
      )
    } catch {
      return
    }

    actionLoading.activate = true
    try {
      await activateTrainingRunModel(runId)
      ElMessage.success('模型已激活')
      const refreshed = await onReload({ preserveDetailRecordId: recordId })
      if (!refreshed) ElMessage.warning('刷新失败，页面可能陈旧')
    } catch (/** @type {any} */ err) {
      errorMessage.value = err?.response?.data?.error || '激活模型失败，请稍后重试'
      ElMessage.error(errorMessage.value)
    } finally {
      actionLoading.activate = false
    }
  }

  const handleDelete = async (record) => {
    if (actionLoading.delete) return
    const recordId = typeof record === 'string' ? record : record?.record_id
    if (!recordId) return
    const title = typeof record === 'string' ? recordId : record?.title || recordId

    try {
      const result = await ElMessageBox.prompt(
        `确定要删除训练记录“${title}”吗？请填写操作理由（1-200字）。`,
        '确认删除训练记录',
        {
          confirmButtonText: '删除',
          cancelButtonText: '取消',
          inputValue: '清理失败或演示训练记录',
          inputPlaceholder: '请输入操作理由',
          inputValidator: (value) => {
            const text = String(value || '').trim()
            return text.length > 0 && text.length <= 200
          },
          inputErrorMessage: '操作理由不能为空且不超过200字',
          type: 'warning',
        }
      )
      const reason = String(result?.value || '').trim()
      if (!reason) return

      actionLoading.delete = true
      try {
        await deleteTrainingRecord(recordId, { reason })
        ElMessage.success('训练记录已删除')
        const refreshed = await onReload({ preserveDetailRecordId: '' })
        if (!refreshed) ElMessage.warning('刷新失败，页面可能陈旧')
      } catch (/** @type {any} */ err) {
        errorMessage.value = err?.response?.data?.error || '删除训练记录失败，请稍后重试'
        ElMessage.error(errorMessage.value)
      } finally {
        actionLoading.delete = false
      }
    } catch {
      return
    }
  }

  return { actionLoading, handleRetry, handleRetryPostRun, handleActivate, handleDelete }
}

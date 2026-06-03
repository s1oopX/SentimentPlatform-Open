import { computed, onMounted, ref } from 'vue'
import { getTrainingComparison, getTrainingDashboard, getTrainingRecords } from '@/api/admin'
import {
  taskTypeOptions,
  modelFamilyOptions,
  searchTypeOptions,
  formatSourceType,
  formatExecutionMode,
  formatStatus,
  formatPostRunStatus,
  formatRuntimeType,
  formatMaybe,
  formatMetric,
} from './trainingConstants'
import { useTrainingForm } from './useTrainingForm'
import { useTrainingRecords } from './useTrainingRecords'
import { useTrainingDetail } from './useTrainingDetail'
import { useTrainingActions } from './useTrainingActions'

export const useTrainingCenter = () => {
  const loading = ref(false)
  const errorMessage = ref('')
  /** @type {import('vue').Ref<any>} */ const dashboard = ref(null)
  /** @type {import('vue').Ref<any[]>} */ const comparison = ref([])
  const comparisonChart = ref('')

  const metricCards = computed(() => {
    const totals = dashboard.value?.totals || {}
    return [
      { label: '总记录', value: totals.total_records ?? 0 },
      { label: '活跃记录', value: totals.active_records ?? 0 },
      { label: '达标记录', value: totals.meets_target_records ?? 0 },
    ]
  })

  const refreshTrainingListSummary = async () => {
    const [dashboardRes, recordsRes] = await Promise.all([
      getTrainingDashboard(),
      getTrainingRecords(recordsMod.getTrainingRecordParams()),
    ])
    dashboard.value = dashboardRes.data || null
    recordsMod.applyRecordsResponse(recordsRes.data)
  }

  const reloadTrainingCenterAfterMutation = async ({
    preserveDetailRecordId = '',
    page = recordsMod.recordsQuery.page,
    pageSize = recordsMod.recordsQuery.pageSize,
  } = {}) => {
    const previousDashboard = dashboard.value
    const previousComparison = comparison.value
    const previousRecords = recordsMod.records.value
    const previousRecordsTotal = recordsMod.recordsTotal.value
    const previousDetail = detailMod.detail.value
    const previousPage = recordsMod.recordsQuery.page
    const previousPageSize = recordsMod.recordsQuery.pageSize

    loading.value = true
    try {
      const [dashboardRes, comparisonRes, recordsRes] = await Promise.all([
        getTrainingDashboard(),
        getTrainingComparison(),
        getTrainingRecords(recordsMod.getTrainingRecordParams({ page, pageSize })),
      ])
      dashboard.value = dashboardRes.data || null
      comparison.value = comparisonRes.data?.rows || []
      comparisonChart.value = comparisonRes.data?.chart_base64 || ''
      recordsMod.applyRecordsResponse(recordsRes.data)
      recordsMod.recordsQuery.page = recordsRes.data?.page ?? page
      recordsMod.recordsQuery.pageSize = recordsRes.data?.page_size ?? pageSize

      const nextDetailRecordId =
        preserveDetailRecordId ||
        recordsMod.records.value?.[0]?.record_id ||
        dashboard.value?.recent_records?.[0]?.record_id

      if (nextDetailRecordId) {
        const nextDetail = await detailMod.loadDetail(nextDetailRecordId, { reportError: false })
        if (!nextDetail) throw new Error('detail refresh failed')
      } else {
        detailMod.detail.value = null
      }

      return true
    } catch {
      dashboard.value = previousDashboard
      comparison.value = previousComparison
      recordsMod.records.value = previousRecords
      recordsMod.recordsTotal.value = previousRecordsTotal
      detailMod.detail.value = previousDetail
      recordsMod.recordsQuery.page = previousPage
      recordsMod.recordsQuery.pageSize = previousPageSize
      return false
    } finally {
      loading.value = false
    }
  }

  const detailMod = useTrainingDetail({ errorMessage })
  const recordsMod = useTrainingRecords({
    loadDetail: detailMod.loadDetail,
    loading,
    errorMessage,
  })
  const formMod = useTrainingForm(
    (recordId, pageSize) =>
      reloadTrainingCenterAfterMutation({ preserveDetailRecordId: recordId, page: 1, pageSize }),
    recordsMod.recordsQuery
  )
  const actionsMod = useTrainingActions({
    onReload: reloadTrainingCenterAfterMutation,
    errorMessage,
  })

  const loadTrainingCenter = async ({ preserveDetailRecordId = '' } = {}) => {
    loading.value = true
    errorMessage.value = ''
    try {
      const [dashboardRes, comparisonRes, recordsRes] = await Promise.all([
        getTrainingDashboard(),
        getTrainingComparison(),
        getTrainingRecords(recordsMod.getTrainingRecordParams()),
      ])
      dashboard.value = dashboardRes.data || null
      comparison.value = comparisonRes.data?.rows || []
      comparisonChart.value = comparisonRes.data?.chart_base64 || ''
      recordsMod.applyRecordsResponse(recordsRes.data)

      const defaultRecordId =
        preserveDetailRecordId ||
        dashboard.value?.recent_records?.[0]?.record_id ||
        recordsMod.records.value?.[0]?.record_id
      if (defaultRecordId) {
        await detailMod.loadDetail(defaultRecordId)
      } else {
        detailMod.detail.value = null
      }
    } catch (/** @type {any} */ err) {
      dashboard.value = null
      comparison.value = []
      recordsMod.records.value = []
      detailMod.detail.value = null
      errorMessage.value = err?.response?.data?.error || '训练中心加载失败，请稍后重试'
    } finally {
      loading.value = false
    }
  }

  onMounted(loadTrainingCenter)

  return {
    loading,
    submitting: formMod.submitting,
    errorMessage,
    dashboard,
    comparison,
    comparisonChart,
    records: recordsMod.records,
    recordsTotal: recordsMod.recordsTotal,
    detail: detailMod.detail,
    logDialogVisible: detailMod.logDialogVisible,
    logLoading: detailMod.logLoading,
    logError: detailMod.logError,
    logContent: detailMod.logContent,
    actionLoading: actionsMod.actionLoading,
    recordsQuery: recordsMod.recordsQuery,
    form: formMod.form,
    taskTypeOptions,
    modelFamilyOptions,
    searchTypeOptions,
    candidateModelOptions: formMod.candidateModelOptions,
    showModelFamily: formMod.showModelFamily,
    showCandidateModels: formMod.showCandidateModels,
    showSearchType: formMod.showSearchType,
    showUseGpu: formMod.showUseGpu,
    metricCards,
    lossCurveDates: detailMod.lossCurveDates,
    lossCurveSeries: detailMod.lossCurveSeries,
    classicalCvMetricItems: detailMod.classicalCvMetricItems,
    canRetryCurrentDetail: detailMod.canRetryCurrentDetail,
    canRetryPostRunCurrentDetail: detailMod.canRetryPostRunCurrentDetail,
    canActivateCurrentDetail: detailMod.canActivateCurrentDetail,
    canDeleteCurrentDetail: detailMod.canDeleteCurrentDetail,
    hasCurrentDetailLogAvailable: detailMod.hasCurrentDetailLogAvailable,
    loadTrainingCenter,
    loadDetail: detailMod.loadDetail,
    openLogDialog: detailMod.openLogDialog,
    handleCreate: () => formMod.handleCreate(errorMessage, refreshTrainingListSummary),
    handleRetry: actionsMod.handleRetry,
    handleRetryPostRun: actionsMod.handleRetryPostRun,
    handleActivate: actionsMod.handleActivate,
    handleDelete: actionsMod.handleDelete,
    handleDownloadLog: detailMod.handleDownloadLog,
    handleRecordPageChange: recordsMod.handleRecordPageChange,
    handleRecordPageSizeChange: recordsMod.handleRecordPageSizeChange,
    formatSourceType,
    formatExecutionMode,
    formatStatus,
    formatSourceMeta: (record) => {
      if (!record) return ''
      const parts = [
        formatSourceType(record.source_type),
        formatExecutionMode(record.execution_mode),
        formatStatus(record.status),
      ].filter(Boolean)
      return parts.join(' / ')
    },
    formatPostRunStatus,
    formatRuntimeType,
    formatMaybe,
    formatMetric,
  }
}

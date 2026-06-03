import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { listReports as getReportList, generateReport, downloadReport } from '@/api/report'
import { getRuntimeCapabilities } from '@/api/analysis'
import { extractErrorMessage } from '@/api/request'
import { extractBlobErrorMessage } from '@/utils/blobReader'
import { downloadBlob } from '@/utils/download'
import { ElMessage } from 'element-plus'
import {
  FALLBACK_RUNTIME_CAPABILITIES,
  normalizeRuntimeCapabilities,
} from '@/utils/runtimeCapabilities'
import { parseContentDispositionFilename } from '@/utils/contentDisposition'

const downloadExtensionByFormat = {
  pdf: 'pdf',
  excel: 'xlsx',
  csv: 'csv',
}

/** @param {any} value */ const getFirstQueryValue = (value) => {
  return Array.isArray(value) ? value[0] : value
}

/** @param {string} value */ const parseDateParts = (value) => {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)

  if (!match) {
    return null
  }

  return {
    year: Number(match[1]),
    month: Number(match[2]),
    day: Number(match[3]),
  }
}

/** @param {Date} date */ const formatDateString = (date) => {
  const year = date.getFullYear()
  const month = `${date.getMonth() + 1}`.padStart(2, '0')
  const day = `${date.getDate()}`.padStart(2, '0')
  return `${year}-${month}-${day}`
}

/** @param {string} reportType @param {string} coreDate */
const resolveRangeStartDate = (reportType, coreDate) => {
  const parsedDate = parseDateParts(coreDate)

  if (!parsedDate) {
    return coreDate
  }

  if (reportType === 'weekly') {
    const weekDate = new Date(parsedDate.year, parsedDate.month - 1, parsedDate.day)
    const daysFromMonday = (weekDate.getDay() + 6) % 7
    weekDate.setDate(weekDate.getDate() - daysFromMonday)
    return formatDateString(weekDate)
  }

  if (reportType === 'monthly') {
    return `${parsedDate.year}-${`${parsedDate.month}`.padStart(2, '0')}-01`
  }

  return coreDate
}

const extractDownloadErrorMessage = (error) =>
  extractBlobErrorMessage(error, '下载失败，请稍后重试')

const getFallbackDownloadFilename = (report) => {
  const extension = downloadExtensionByFormat[report.report_format] || 'pdf'
  return `情感分析报告_${report.id}.${extension}`
}

const getFilenameFromContentDisposition = (contentDisposition) => {
  return parseContentDispositionFilename(contentDisposition, '')
}

const isReportInProgress = (status) => ['pending', 'pending_enqueue', 'processing'].includes(status)

export const useReportCenter = ({ authStore }) => {
  // ── Region: State ──

  const route = useRoute()
  const loading = ref(true)
  const generating = ref(false)
  const showGenerateForm = ref(false)
  const syncingReportDefaults = ref(false)
  const hasCustomizedReportDefaults = ref(false)
  /** @type {import('vue').Ref<any[]>} */ const reports = ref([])
  const total = ref(0)
  const errorMessage = ref('')
  const runtimeCapabilities = ref(FALLBACK_RUNTIME_CAPABILITIES)
  const showPrefillNotice = ref(false)
  const queryParams = reactive({
    page: 1,
    page_size: 10,
  })
  /** @type {{ report_type: any, report_format: any, start_date: string, end_date: string, category: string }} */
  const generateForm = reactive({
    report_type: runtimeCapabilities.value.report_defaults.report_type,
    report_format: runtimeCapabilities.value.report_defaults.report_format,
    start_date: '',
    end_date: '',
    category: '',
  })

  const canUseScopedReportFilters = computed(() =>
    ['admin', 'analyst'].includes(authStore.user?.role)
  )

  // ── Region: Report defaults & route prefill ──

  const applyReportDefaults = () => {
    if (hasCustomizedReportDefaults.value) {
      return
    }

    syncingReportDefaults.value = true
    generateForm.report_type = runtimeCapabilities.value.report_defaults.report_type
    generateForm.report_format = runtimeCapabilities.value.report_defaults.report_format
    syncingReportDefaults.value = false
  }

  const resetRoutePrefillFields = () => {
    generateForm.category = ''
    generateForm.start_date = ''
    generateForm.end_date = ''
  }

  const applyPrefillFromRoute = () => {
    resetRoutePrefillFields()

    if (getFirstQueryValue(route.query?.prefill_source) !== 'result_detail') {
      showPrefillNotice.value = false
      return
    }

    const category = getFirstQueryValue(route.query?.category)
    const startDate = getFirstQueryValue(route.query?.start_date)

    if (category !== undefined && category !== null) {
      generateForm.category = String(category)
    }
    if (startDate !== undefined && startDate !== null && startDate !== '') {
      generateForm.start_date = String(startDate)
    }

    showPrefillNotice.value = true
  }

  const loadRuntimeCapabilities = async () => {
    try {
      const res = await getRuntimeCapabilities()
      runtimeCapabilities.value = normalizeRuntimeCapabilities(res.data)
    } catch {
      runtimeCapabilities.value = FALLBACK_RUNTIME_CAPABILITIES
    }

    applyReportDefaults()
  }

  // ── Region: Report list & polling ──

  const POLL_INTERVAL_MS = 10_000
  /** @type {ReturnType<typeof setTimeout>|null} */ let pollTimerId = null

  const stopPolling = () => {
    if (pollTimerId !== null) {
      clearTimeout(pollTimerId)
      pollTimerId = null
    }
  }

  const schedulePollIfNeeded = () => {
    stopPolling()
    const hasInProgress = reports.value.some((report) => isReportInProgress(report?.status))
    if (!hasInProgress) return
    pollTimerId = setTimeout(() => {
      // Skip polling if component is gone / user already triggered a refresh.
      if (pollTimerId === null) return
      pollTimerId = null
      void fetchReports({ silent: true })
    }, POLL_INTERVAL_MS)
  }

  const fetchReports = async ({ silent = false } = {}) => {
    if (!silent) {
      loading.value = true
    }
    errorMessage.value = ''
    try {
      const res = await getReportList(queryParams)
      reports.value = res.data.results || res.data
      total.value = res.data.count || reports.value.length
      schedulePollIfNeeded()
      return true
    } catch {
      reports.value = []
      total.value = 0
      errorMessage.value = '报表列表加载失败，请稍后重试'
      stopPolling()
      return false
    } finally {
      if (!silent) {
        loading.value = false
      }
    }
  }

  const refreshReportsAfterGenerate = async () => {
    queryParams.page = 1
    const refreshed = await fetchReports()
    if (!refreshed) {
      ElMessage.warning('报表列表刷新失败，页面数据可能不是最新')
    }
  }

  const handlePageSizeChange = async () => {
    queryParams.page = 1
    await fetchReports()
  }

  const downloadBlobByReport = (blob, report, serverFilename = '') =>
    downloadBlob(blob, serverFilename || getFallbackDownloadFilename(report))

  // ── Region: Generate & download ──

  const buildGeneratePayload = (form) => {
    const payload = {
      report_type: form.report_type,
      report_format: form.report_format,
    }

    const startDate = form.start_date || ''

    if (startDate) {
      payload.start_date = resolveRangeStartDate(form.report_type, startDate)
      payload.end_date = startDate
    }

    if (canUseScopedReportFilters.value && form.category.trim()) {
      payload.category = form.category.trim()
    }

    return payload
  }

  const handleGenerate = async () => {
    generating.value = true
    try {
      await generateReport(buildGeneratePayload(generateForm))
      ElMessage.success('报表生成任务已提交')
      showGenerateForm.value = false
      await refreshReportsAfterGenerate()
    } catch (/** @type {any} */ err) {
      ElMessage.error(extractErrorMessage(err, '报表生成失败，请稍后重试'))
    } finally {
      generating.value = false
    }
  }

  const handleDownload = async (report) => {
    try {
      const response = await downloadReport(report.id)
      const blob = response.data
      const serverFilename = getFilenameFromContentDisposition(
        response?.headers?.['content-disposition']
      )
      downloadBlobByReport(blob, report, serverFilename)
    } catch (/** @type {any} */ err) {
      ElMessage.error(await extractDownloadErrorMessage(err))
    }
  }

  const getReportTagType = (status) => {
    if (status === 'completed') {
      return 'success'
    }
    if (status === 'failed') {
      return 'danger'
    }
    return 'info'
  }

  // ── Region: Display helpers ──

  const getVisibleReportStatusDisplay = (report) => {
    return report?.status_display || ''
  }

  const getReportFailureReason = (report) => {
    const enqueueError = (report?.last_enqueue_error || '').trim()
    if (enqueueError) {
      return enqueueError
    }
    return ''
  }

  const toggleGenerateForm = () => {
    showGenerateForm.value = !showGenerateForm.value
  }

  // ── Region: Lifecycle ──

  watch(
    () => route.query,
    () => {
      applyPrefillFromRoute()
    },
    { deep: true }
  )

  watch(
    () => [generateForm.report_type, generateForm.report_format],
    ([nextReportType, nextReportFormat], [prevReportType, prevReportFormat]) => {
      if (syncingReportDefaults.value) {
        return
      }

      if (nextReportType !== prevReportType || nextReportFormat !== prevReportFormat) {
        hasCustomizedReportDefaults.value = true
      }
    }
  )

  onMounted(async () => {
    applyPrefillFromRoute()
    await Promise.allSettled([loadRuntimeCapabilities(), fetchReports()])
  })

  onUnmounted(() => {
    stopPolling()
  })

  return {
    loading,
    generating,
    showGenerateForm,
    showPrefillNotice,
    reports,
    total,
    errorMessage,
    queryParams,
    generateForm,
    canUseScopedReportFilters,
    fetchReports,
    handlePageSizeChange,
    handleGenerate,
    handleDownload,
    toggleGenerateForm,
    getReportTagType,
    getVisibleReportStatusDisplay,
    getReportFailureReason,
    isReportInProgress,
  }
}

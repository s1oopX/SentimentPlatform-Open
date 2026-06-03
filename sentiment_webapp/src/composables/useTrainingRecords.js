import { reactive, ref } from 'vue'
import { getTrainingRecords } from '@/api/admin'

/**
 * @param {{ loadDetail: (id: string, opts?: object) => Promise<any>, loading: import('vue').Ref<boolean>, errorMessage: import('vue').Ref<string> }} deps
 */
export function useTrainingRecords({ loadDetail, loading, errorMessage }) {
  /** @type {import('vue').Ref<any[]>} */ const records = ref([])
  const recordsTotal = ref(0)
  const recordsQuery = reactive({ page: 1, pageSize: 20 })

  const applyRecordsResponse = (data) => {
    records.value = data?.items || []
    recordsTotal.value = data?.total_records ?? records.value.length
    recordsQuery.page = data?.page ?? recordsQuery.page
    recordsQuery.pageSize = data?.page_size ?? recordsQuery.pageSize
  }

  const createRecordBrowserSnapshot = () => ({
    records: records.value,
    recordsTotal: recordsTotal.value,
    detail: null,
    page: recordsQuery.page,
    pageSize: recordsQuery.pageSize,
  })

  const restoreRecordBrowserSnapshot = (snapshot) => {
    records.value = snapshot.records
    recordsTotal.value = snapshot.recordsTotal
    recordsQuery.page = snapshot.page
    recordsQuery.pageSize = snapshot.pageSize
  }

  const getTrainingRecordParams = ({
    page = recordsQuery.page,
    pageSize = recordsQuery.pageSize,
  } = {}) => ({ page, page_size: pageSize })

  const fetchTrainingRecordsPage = async ({
    page = recordsQuery.page,
    pageSize = recordsQuery.pageSize,
    preserveDetailRecordId = '',
  } = {}) => {
    const recordsRes = await getTrainingRecords(getTrainingRecordParams({ page, pageSize }))
    applyRecordsResponse(recordsRes.data)
    recordsQuery.page = recordsRes.data?.page ?? page
    recordsQuery.pageSize = recordsRes.data?.page_size ?? pageSize

    const nextDetailRecordId =
      preserveDetailRecordId &&
      records.value.some((item) => item.record_id === preserveDetailRecordId)
        ? preserveDetailRecordId
        : records.value?.[0]?.record_id

    if (nextDetailRecordId) {
      const nextDetail = await loadDetail(nextDetailRecordId)
      if (!nextDetail) throw new Error('detail load failed')
    }
  }

  const handleRecordPageChange = async (page) => {
    const previousState = createRecordBrowserSnapshot()
    loading.value = true
    errorMessage.value = ''
    try {
      await fetchTrainingRecordsPage({ page, pageSize: recordsQuery.pageSize })
    } catch (/** @type {any} */ err) {
      restoreRecordBrowserSnapshot(previousState)
      errorMessage.value =
        errorMessage.value || err?.response?.data?.error || '训练记录加载失败，请稍后重试'
    } finally {
      loading.value = false
    }
  }

  const handleRecordPageSizeChange = async (pageSize) => {
    const previousState = createRecordBrowserSnapshot()
    loading.value = true
    errorMessage.value = ''
    try {
      await fetchTrainingRecordsPage({ page: 1, pageSize })
    } catch (/** @type {any} */ err) {
      restoreRecordBrowserSnapshot(previousState)
      errorMessage.value =
        errorMessage.value || err?.response?.data?.error || '训练记录加载失败，请稍后重试'
    } finally {
      loading.value = false
    }
  }

  return {
    records,
    recordsTotal,
    recordsQuery,
    applyRecordsResponse,
    createRecordBrowserSnapshot,
    restoreRecordBrowserSnapshot,
    getTrainingRecordParams,
    fetchTrainingRecordsPage,
    handleRecordPageChange,
    handleRecordPageSizeChange,
  }
}

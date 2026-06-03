import request from './request'

export function getAdminDashboardStats() {
  return request.get('/admin/dashboard/stats/', { suppressErrorMessage: true })
}

/** @param {Record<string,any>} params */
export function getUsers(params) {
  return request.get('/admin/users/', { params, suppressErrorMessage: true })
}

/** @param {number|string} id @param {object} data */
export function updateUserStatus(id, data) {
  return request.put(`/admin/users/${id}/status/`, data, { suppressErrorMessage: true })
}

/** @param {number|string} id @param {object} data */
export function updateUserRole(id, data) {
  return request.patch(`/admin/users/${id}/`, data, { suppressErrorMessage: true })
}

/** @param {Record<string,any>} params */
export function getOperationLogs(params) {
  return request.get('/admin/logs/', { params, suppressErrorMessage: true })
}

/** @param {Record<string,any>} params */
export function getDatasets(params) {
  return request.get('/admin/datasets/', { params, suppressErrorMessage: true })
}

/** @param {object} data */
export function importDataset(data) {
  return request.post('/admin/datasets/import/', data, {
    headers: { 'Content-Type': 'multipart/form-data' },
    suppressErrorMessage: true,
  })
}

/** @param {Record<string,any>|number} params */
export function exportDataset(params) {
  const query = typeof params === 'number' ? { ids: String(params) } : params
  return request.get('/admin/datasets/export/', {
    params: query,
    responseType: 'blob',
    suppressErrorMessage: true,
  })
}

/** @param {Record<string,any>} params */
export function getModels(params) {
  return request.get('/admin/models/', { params, suppressErrorMessage: true, timeout: 60000 })
}

/** @param {number|string} id */
export function getModelLogs(id) {
  return request.get(`/admin/models/${id}/logs/`, { suppressErrorMessage: true, timeout: 60000 })
}

/** @param {number|string} id */
export function activateModel(id) {
  return request.post(
    `/admin/models/${id}/activate/`,
    {},
    { suppressErrorMessage: true, timeout: 60000 }
  )
}

export function getTrainingDashboard(params = {}) {
  return request.get('/admin/training/dashboard/', { params, suppressErrorMessage: true })
}

export function getTrainingComparison(params = {}) {
  return request.get('/admin/training/comparison/', { params, suppressErrorMessage: true })
}

/** @param {Record<string,any>} params */
export function getTrainingRecords(params) {
  return request.get('/admin/training/records/', { params, suppressErrorMessage: true })
}

/** @param {object} data */
export function createTrainingRecord(data) {
  return request.post('/admin/training/records/', data, { suppressErrorMessage: true })
}

/** @param {number|string} recordId */
export function getTrainingRecordDetail(recordId) {
  return request.get(`/admin/training/records/${recordId}/`, { suppressErrorMessage: true })
}

/** @param {number|string} recordId @param {object} data */
export function deleteTrainingRecord(recordId, data) {
  return request.delete(`/admin/training/records/${recordId}/`, {
    data,
    suppressErrorMessage: true,
  })
}

/** @param {number|string} runId */
export function retryTrainingRecord(runId) {
  return request.post(`/admin/training/records/${runId}/retry/`, {}, { suppressErrorMessage: true })
}

/** @param {number|string} runId */
export function retryTrainingRecordPostRun(runId) {
  return request.post(
    `/admin/training/records/${runId}/retry-post-run/`,
    {},
    { suppressErrorMessage: true }
  )
}

/** @param {number|string} runId */
export function getTrainingRunLog(runId) {
  return request.get(`/admin/training/records/${runId}/log/`, { suppressErrorMessage: true })
}

/** @param {number|string} runId */
export function downloadTrainingRunLog(runId) {
  return request.get(`/admin/training/records/${runId}/log/download/`, {
    responseType: 'blob',
    suppressErrorMessage: true,
  })
}

/** @param {number|string} runId */
export function activateTrainingRunModel(runId) {
  return request.post(
    `/admin/training/records/${runId}/activate-model/`,
    {},
    { suppressErrorMessage: true }
  )
}

export function triggerDatabaseBackup() {
  return request.post('/admin/backup/', {}, { suppressErrorMessage: true, timeout: 130000 })
}

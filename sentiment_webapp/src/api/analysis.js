import request from './request'

/** @param {object} data */
export function performSingleAnalysis(data) {
  return request.post('/analyze/single/', data, { suppressErrorMessage: true })
}

/** @param {object} data @param {Record<string,any>} [config] */
export function performBatchAnalysis(data, config = {}) {
  return request.post('/analyze/batch/', data, {
    ...config,
    headers: {
      'Content-Type': 'multipart/form-data',
      ...(config.headers || {}),
    },
    timeout: 120000,
    suppressErrorMessage: true,
  })
}

/** @param {string} [format] */
export function downloadBatchTemplate(format = 'xlsx') {
  return request.get('/analyze/batch/template/', {
    params: { format },
    responseType: 'blob',
    suppressErrorMessage: true,
  })
}

export function getBatchSchema() {
  return request.get('/analyze/batch/schema/', {
    suppressErrorMessage: true,
  })
}

export function getRuntimeCapabilities() {
  return request.get('/analyze/runtime-capabilities/', {
    suppressErrorMessage: true,
  })
}

/** @param {Record<string,any>} params */
export function getAnalysisHistory(params) {
  return request.get('/analyze/history/', { params, suppressErrorMessage: true })
}

/** @param {Record<string,any>} params */
export function getAnalysisHistorySummary(params = {}) {
  return request.get('/analyze/history/summary/', { params, suppressErrorMessage: true })
}

/** @param {number|string} id */
export function getAnalysisResultDetail(id) {
  return request.get(`/analyze/result/${id}/`, { suppressErrorMessage: true })
}

/** @param {Record<string,any>} params */
export function getAnalystOverview(params) {
  return request.get('/analyze/analyst/overview/', { params, suppressErrorMessage: true })
}

/** @param {Record<string,any>} params */
export function getAnalystComments(params) {
  return request.get('/analyze/analyst/comments/', { params, suppressErrorMessage: true })
}

/** @param {number|string} id @param {object} data */
export function updateAnalystComment(id, data) {
  return request.patch(`/analyze/analyst/comments/${id}/`, data, { suppressErrorMessage: true })
}

/** @param {number|string} id */
export function deleteAnalystComment(id) {
  return request.delete(`/analyze/analyst/comments/${id}/`, { suppressErrorMessage: true })
}

/** @param {Record<string,any>} params */
export function getAnalystReport(params) {
  return request.get('/analyze/analyst/report/', { params, suppressErrorMessage: true })
}

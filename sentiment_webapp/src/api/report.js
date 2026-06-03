import request from './request'

/** @param {Record<string,any>} params */
export function listReports(params) {
  return request.get('/report/list/', {
    params,
    suppressErrorMessage: true,
  })
}

/** @param {object} data */
export function generateReport(data) {
  return request.post('/report/generate/', data, { suppressErrorMessage: true })
}

/** @param {number|string} id */
export function downloadReport(id) {
  return request.get(`/report/download/${id}/`, {
    responseType: 'blob',
    suppressErrorMessage: true,
  })
}

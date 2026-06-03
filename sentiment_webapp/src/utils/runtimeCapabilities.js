export const FALLBACK_RUNTIME_CAPABILITIES = {
  max_upload_size_mb: 10,
  batch_analysis_supported_formats: ['.xlsx', '.txt'],
  dataset_import_supported_formats: ['.xlsx', '.txt'],
  report_defaults: {
    report_type: 'weekly',
    report_format: 'pdf',
  },
}

/**
 * @param {Record<string, any>} [payload={}]
 */
export function normalizeRuntimeCapabilities(payload = {}) {
  const batchFormats =
    payload.batch_analysis_supported_formats ??
    FALLBACK_RUNTIME_CAPABILITIES.batch_analysis_supported_formats
  const datasetFormats =
    payload.dataset_import_supported_formats ??
    FALLBACK_RUNTIME_CAPABILITIES.dataset_import_supported_formats

  return {
    max_upload_size_mb:
      payload.max_upload_size_mb ?? FALLBACK_RUNTIME_CAPABILITIES.max_upload_size_mb,
    batch_analysis_supported_formats: [...batchFormats],
    dataset_import_supported_formats: [...datasetFormats],
    report_defaults: {
      report_type:
        payload.report_defaults?.report_type ??
        FALLBACK_RUNTIME_CAPABILITIES.report_defaults.report_type,
      report_format:
        payload.report_defaults?.report_format ??
        FALLBACK_RUNTIME_CAPABILITIES.report_defaults.report_format,
    },
  }
}

/**
 * Batch upload row-count pre-check.
 * Reads the selected file client-side and returns the data-row count
 * for text uploads. Throws a user-friendly error string
 * when the count exceeds the limit.
 *
 * .xlsx  → validated server-side after upload to avoid shipping a large parser
 * .txt   → newline-split (blank trailing lines trimmed)
 */

const MAX_BATCH_ROWS = 1000

/**
 * @param {File} file
 * @returns {Promise<number>} data-row count
 */
export async function countFileRows(file) {
  const name = (file.name || '').toLowerCase()

  if (name.endsWith('.xlsx') || name.endsWith('.xls')) {
    return 0
  }

  if (name.endsWith('.txt') || name.endsWith('.csv')) {
    return countTextRows(file)
  }

  return 0
}

/**
 * @param {File} file
 * @returns {Promise<number>}
 */
async function countTextRows(file) {
  const text = await file.text()
  const lines = text.split(/\r?\n/).filter((line) => line.trim() !== '')
  return lines.length
}

/**
 * Validate that the file does not exceed the batch row limit.
 * @param {File} file
 * @returns {Promise<{ ok: boolean, count: number, message?: string }>}
 */
export async function validateBatchRowLimit(file) {
  const count = await countFileRows(file)

  if (count > MAX_BATCH_ROWS) {
    return {
      ok: false,
      count,
      message: `文件包含 ${count} 条数据，超出单次批量上限 ${MAX_BATCH_ROWS} 条，请拆分后重新上传`,
    }
  }

  return { ok: true, count }
}

export { MAX_BATCH_ROWS }

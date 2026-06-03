import { extractErrorMessage } from '@/api/request'

export function isBlobLike(value) {
  return (
    Boolean(value) &&
    (typeof value.text === 'function' ||
      typeof value.arrayBuffer === 'function' ||
      Object.prototype.toString.call(value) === '[object Blob]')
  )
}

export function shouldParseBlobError(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return false
  }
  return isBlobLike(value) || Object.keys(value).length === 0
}

export async function readBlobLikeText(value) {
  if (typeof value.text === 'function') {
    try {
      return await value.text()
    } catch {
      // Fall through to alternate readers.
    }
  }

  if (typeof FileReader !== 'undefined') {
    try {
      return await new Promise((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(reader.result)
        reader.onerror = () => reject(reader.error || new Error('blob read failed'))
        reader.readAsText(value)
      })
    } catch {
      // Fall through to alternate readers.
    }
  }

  if (typeof Response !== 'undefined') {
    try {
      return await new Response(value).text()
    } catch {
      // Fall through to arrayBuffer decoding.
    }
  }

  if (typeof value.arrayBuffer === 'function' && typeof TextDecoder !== 'undefined') {
    return new TextDecoder().decode(await value.arrayBuffer())
  }

  throw new Error('unable to read blob-like error payload')
}

export async function extractBlobErrorMessage(error, fallback) {
  const responseData = error?.response?.data

  if (!shouldParseBlobError(responseData)) {
    return extractErrorMessage(error, fallback)
  }

  try {
    const parsedData = JSON.parse(await readBlobLikeText(responseData))
    return extractErrorMessage(
      {
        ...error,
        response: {
          ...error.response,
          data: parsedData,
        },
      },
      fallback
    )
  } catch {
    return fallback
  }
}

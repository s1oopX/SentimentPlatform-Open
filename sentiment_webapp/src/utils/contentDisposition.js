/**
 * Parse filename from Content-Disposition header.
 * Supports both RFC 2616 (filename=...) and RFC 5987 (filename*=UTF-8''...).
 *
 * @param {string|null} header  The Content-Disposition header value.
 * @param {string} fallback     Fallback filename if parsing fails.
 * @returns {string}  The extracted filename or fallback.
 */
export function parseContentDispositionFilename(header, fallback) {
  if (!header || typeof header !== 'string') return fallback

  // RFC 5987: filename*=UTF-8''encoded%20name
  const utf8Match = header.match(/filename\*=UTF-8''([^;\s]+)/i)
  if (utf8Match) {
    try {
      return decodeURIComponent(utf8Match[1])
    } catch {
      // fall through to basic parsing
    }
  }

  // RFC 2616: filename="name" or filename=name
  const basicMatch = header.match(/filename="?([^";]+)"?/i)
  return basicMatch?.[1]?.trim() || fallback
}

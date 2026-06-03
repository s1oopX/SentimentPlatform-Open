/**
 * Highlight keywords in a text by wrapping them in <mark> tags.
 * Returns an HTML string – use with `v-html`.
 *
 * ⚠️ SECURITY: escapeHtml() MUST be called on the input text BEFORE
 * inserting any HTML tags. Removing the escapeHtml call would introduce
 * an XSS vulnerability via v-html. Do not refactor without preserving
 * this escape-first-then-mark pattern.
 *
 * @param {string} text The original text content.
 * @param {string[]} keywords Keywords to highlight (case-insensitive).
 * @returns {string} HTML string with keywords wrapped in <mark>.
 */
export function highlightKeywords(text, keywords) {
  if (!text || !keywords?.length) return escapeHtml(text ?? '')

  // Escape HTML first so user content is safe
  const escaped = escapeHtml(text)

  // Build a single regex matching any keyword (longest first to avoid partial overlap)
  const sorted = [...keywords].filter((k) => k && k.trim()).sort((a, b) => b.length - a.length)

  if (sorted.length === 0) return escaped

  const pattern = sorted.map(escapeRegExp).join('|')
  const regex = new RegExp(`(${pattern})`, 'gi')

  return escaped.replace(regex, '<mark class="bg-yellow-200 text-inherit rounded px-0.5">$1</mark>')
}

function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function escapeRegExp(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

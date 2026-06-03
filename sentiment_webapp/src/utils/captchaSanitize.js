import DOMPurify from 'dompurify'

/**
 * Sanitize captcha SVG response before rendering via v-html.
 * Uses DOMPurify to strip dangerous elements (script, foreignObject, event handlers, etc.)
 * while preserving safe SVG markup.
 *
 * @param {string} raw  The raw SVG string from the backend.
 * @returns {string}  The sanitized SVG, or empty string if invalid.
 */
export function sanitizeCaptchaSvg(raw) {
  if (typeof raw !== 'string') return ''
  const trimmed = raw.trim()
  if (!trimmed.startsWith('<svg') || !trimmed.endsWith('</svg>')) return ''
  return DOMPurify.sanitize(trimmed, {
    RETURN_TRUSTED_TYPE: false,
    ALLOWED_TAGS: [
      'svg',
      'path',
      'rect',
      'circle',
      'ellipse',
      'line',
      'polyline',
      'polygon',
      'text',
      'tspan',
      'g',
      'defs',
      'linearGradient',
      'radialGradient',
      'stop',
    ],
    ALLOWED_ATTR: [
      'xmlns',
      'viewBox',
      'width',
      'height',
      'x',
      'y',
      'cx',
      'cy',
      'r',
      'rx',
      'ry',
      'x1',
      'y1',
      'x2',
      'y2',
      'd',
      'points',
      'fill',
      'stroke',
      'stroke-width',
      'stroke-linecap',
      'stroke-linejoin',
      'opacity',
      'transform',
      'font-size',
      'font-family',
      'font-weight',
      'text-anchor',
      'dominant-baseline',
      'id',
      'offset',
      'stop-color',
      'stop-opacity',
      'preserveAspectRatio',
    ],
    FORBID_TAGS: ['script', 'foreignObject', 'iframe', 'embed', 'object', 'animate', 'set'],
    FORBID_ATTR: ['onload', 'onerror', 'onclick', 'onmouseover', 'onfocus', 'onblur'],
  })
}

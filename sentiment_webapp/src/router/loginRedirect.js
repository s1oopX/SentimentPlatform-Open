const trimTrailingSlash = (value) => value.replace(/\/+$/, '')
const unsafeUrlPattern = /^[a-zA-Z][a-zA-Z\d+\-.]*:/

const splitPathAndSuffix = (value) => {
  const queryIndex = value.indexOf('?')
  const hashIndex = value.indexOf('#')

  if (queryIndex === -1 && hashIndex === -1) {
    return { pathname: value, suffix: '' }
  }

  const cutIndex =
    queryIndex === -1 ? hashIndex : hashIndex === -1 ? queryIndex : Math.min(queryIndex, hashIndex)

  return {
    pathname: value.slice(0, cutIndex),
    suffix: value.slice(cutIndex),
  }
}

function normalizeBaseUrl(baseUrl = import.meta.env.BASE_URL || '/') {
  const raw = typeof baseUrl === 'string' ? baseUrl.trim() : ''
  if (!raw || raw === '/') {
    return '/'
  }

  if (raw.startsWith('//') || unsafeUrlPattern.test(raw)) {
    return '/'
  }

  const withLeadingSlash = raw.startsWith('/') ? raw : `/${raw}`
  return `${trimTrailingSlash(withLeadingSlash)}/`
}

function buildLoginPath(baseUrl = import.meta.env.BASE_URL || '/') {
  const normalizedBaseUrl = normalizeBaseUrl(baseUrl)
  if (normalizedBaseUrl === '/') {
    return '/login'
  }
  return `${trimTrailingSlash(normalizedBaseUrl)}/login`
}

function isLoginPath(pathname, baseUrl = import.meta.env.BASE_URL || '/') {
  return pathname === buildLoginPath(baseUrl)
}

function stripBaseUrlFromPathname(pathname, baseUrl = import.meta.env.BASE_URL || '/') {
  if (typeof pathname !== 'string') {
    return null
  }

  const normalizedPathname = pathname.trim()
  if (!normalizedPathname || !normalizedPathname.startsWith('/')) {
    return null
  }

  const normalizedBaseUrl = normalizeBaseUrl(baseUrl)
  const basePath = trimTrailingSlash(normalizedBaseUrl)

  if (basePath && basePath !== '/' && normalizedPathname === basePath) {
    return '/'
  }

  if (basePath && basePath !== '/' && normalizedPathname.startsWith(`${basePath}/`)) {
    return normalizedPathname.slice(basePath.length) || '/'
  }

  return normalizedPathname
}

function normalizeAppRelativeRedirect(value, baseUrl = import.meta.env.BASE_URL || '/') {
  if (typeof value !== 'string') {
    return null
  }

  const raw = value.trim()
  if (!raw || raw.startsWith('//') || unsafeUrlPattern.test(raw)) {
    return null
  }

  const { pathname, suffix } = splitPathAndSuffix(raw)
  const normalizedPathname = stripBaseUrlFromPathname(pathname, baseUrl)
  if (!normalizedPathname || normalizedPathname.startsWith('//')) {
    return null
  }

  return `${normalizedPathname}${suffix}`
}

export function normalizeLoginRedirectValue(value, baseUrl = import.meta.env.BASE_URL || '/') {
  const normalizedRedirect = normalizeAppRelativeRedirect(value, baseUrl)
  if (!normalizedRedirect) {
    return null
  }

  const { pathname } = splitPathAndSuffix(normalizedRedirect)
  if (pathname === '/login') {
    return null
  }

  return normalizedRedirect
}

export function buildLoginRedirectUrl({
  pathname,
  search = '',
  baseUrl = import.meta.env.BASE_URL || '/',
}) {
  const loginPath = buildLoginPath(baseUrl)
  if (isLoginPath(pathname, baseUrl)) {
    return loginPath
  }

  const redirect = normalizeAppRelativeRedirect(`${pathname || ''}${search || ''}`, baseUrl)
  if (!redirect) {
    return loginPath
  }

  return `${loginPath}?redirect=${encodeURIComponent(redirect)}`
}

export const normalizeText = (value) => String(value ?? '').trim()

export const normalizeDate = (value) => {
  const normalized = String(value ?? '').trim()
  return /^\d{4}-\d{2}-\d{2}$/.test(normalized) ? normalized : ''
}

export const readFiltersFromRoute = (route, keys) => {
  const query = route?.query || {}
  return keys.reduce((acc, key) => {
    const value = query[key]
    acc[key] = Array.isArray(value) ? String(value[0] ?? '') : String(value ?? '')
    return acc
  }, {})
}

export const buildRouteFilterSignature = (route, keys) =>
  JSON.stringify(readFiltersFromRoute(route, keys))

export const writeFiltersToRoute = async (router, route, filters) => {
  const nextQuery = { ...(route?.query || {}) }

  Object.entries(filters).forEach(([key, value]) => {
    const normalized = String(value ?? '').trim()
    if (normalized) {
      nextQuery[key] = normalized
      return
    }
    delete nextQuery[key]
  })

  await router.replace({ query: nextQuery })
}

export const buildDateRangeParams = (filters) => {
  const params = {}
  const startDate = normalizeDate(filters?.start_date)
  const endDate = normalizeDate(filters?.end_date)

  if (startDate) {
    params.start_date = startDate
  }
  if (endDate) {
    params.end_date = endDate
  }

  return params
}

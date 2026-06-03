import { onMounted, reactive, ref, watch } from 'vue'
import {
  buildRouteFilterSignature,
  readFiltersFromRoute,
  writeFiltersToRoute,
} from '@/utils/filterUtils'

/**
 * @param {object} options
 * @param {import('vue-router').Router} options.router
 * @param {import('vue-router').RouteLocationNormalizedLoaded} options.route
 * @param {string[]} options.filterKeys
 * @param {(filters: object) => object} options.buildParams
 * @param {(params: object) => Promise<any>} options.fetchFn
 * @param {(res: any) => void} [options.onFetched]
 */
/** @returns {any} */
export function useRouteFilterSync({ router, route, filterKeys, buildParams, fetchFn, onFetched }) {
  const pendingRouteSignatures = new Map()
  let fetchRequestId = 0

  const filters = reactive(
    filterKeys.reduce((acc, key) => {
      acc[key] = ''
      return acc
    }, {})
  )

  const loading = ref(false)
  const errorMessage = ref('')
  const appliedRouteSignature = ref('')

  const getRouteFilterSignature = () => buildRouteFilterSignature(route, filterKeys)

  const markPendingRouteSignature = (signature) => {
    pendingRouteSignatures.set(signature, (pendingRouteSignatures.get(signature) || 0) + 1)
  }

  const consumePendingRouteSignature = (signature) => {
    const count = pendingRouteSignatures.get(signature) || 0
    if (count <= 0) return false
    if (count === 1) {
      pendingRouteSignatures.delete(signature)
    } else {
      pendingRouteSignatures.set(signature, count - 1)
    }
    return true
  }

  const hydrateFiltersFromRoute = () => {
    const routeFilters = readFiltersFromRoute(route, filterKeys)
    Object.assign(filters, routeFilters)
  }

  const doFetch = async () => {
    const currentRequestId = ++fetchRequestId
    loading.value = true
    errorMessage.value = ''
    try {
      const res = await fetchFn(buildParams({ ...filters }))
      if (currentRequestId !== fetchRequestId) return
      if (onFetched) onFetched(res)
    } catch (/** @type {any} */ err) {
      if (currentRequestId !== fetchRequestId) return
      errorMessage.value = err?.response?.data?.error || '数据加载失败，请稍后重试'
    } finally {
      if (currentRequestId === fetchRequestId) {
        loading.value = false
      }
    }
  }

  const syncFiltersFromRoute = async ({ force = false } = {}) => {
    const nextSignature = getRouteFilterSignature()
    if (!force && nextSignature === appliedRouteSignature.value) return

    hydrateFiltersFromRoute()
    appliedRouteSignature.value = nextSignature
    await doFetch()
  }

  const applyFilters = async () => {
    const routeFilters = {}
    filterKeys.forEach((key) => {
      const value = String(filters[key] ?? '').trim()
      routeFilters[key] = value
    })

    const nextSignature = JSON.stringify(routeFilters)
    markPendingRouteSignature(nextSignature)
    await writeFiltersToRoute(router, route, routeFilters)
    hydrateFiltersFromRoute()
    appliedRouteSignature.value = nextSignature
    await doFetch()
    consumePendingRouteSignature(nextSignature)
  }

  const resetFilters = async () => {
    filterKeys.forEach((key) => {
      filters[key] = ''
    })
    await applyFilters()
  }

  onMounted(async () => {
    await syncFiltersFromRoute({ force: true })
  })

  watch(
    () => getRouteFilterSignature(),
    (nextSignature) => {
      if (consumePendingRouteSignature(nextSignature)) return
      syncFiltersFromRoute()
    }
  )

  return { filters, loading, errorMessage, applyFilters, resetFilters, fetchData: doFetch }
}

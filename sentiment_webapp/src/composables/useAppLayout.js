import { computed, ref, watch } from 'vue'
import { useMediaQuery } from '@vueuse/core'

/**
 * Shared layout shell state — sidebar, dark mode, page metadata.
 * Used by both UserLayout and AdminLayout.
 *
 * @param {import('vue-router').RouteLocationNormalizedLoaded} route
 */
export function useAppLayout(route) {
  const isLgViewport = useMediaQuery('(min-width: 768px)')
  const isWideViewport = useMediaQuery('(min-width: 1180px)')
  const sidebarOpen = ref(isWideViewport.value)

  const toggleSidebar = () => {
    sidebarOpen.value = !sidebarOpen.value
  }
  const closeSidebar = () => {
    sidebarOpen.value = false
  }

  watch([isLgViewport, isWideViewport], ([lg, wide]) => {
    sidebarOpen.value = lg && wide
  })

  const activeMenu = computed(() => route.path)
  const pageTitle = computed(() => String(route.meta?.title || ''))

  watch(
    () => route.path,
    () => {
      if (!isLgViewport.value) {
        sidebarOpen.value = false
      }
    }
  )

  return {
    sidebarOpen,
    toggleSidebar,
    closeSidebar,
    isLgViewport,
    isWideViewport,
    activeMenu,
    pageTitle,
  }
}

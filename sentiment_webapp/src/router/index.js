import { nextTick } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { getRouteRoles, resolveProtectedNavigation } from '@/router/access'
import { isResolvedAuthenticated } from '@/router/guardState'
import { recoverProtectedSession } from '@/composables/useSessionRecovery'

/** @type {import('vue-router').RouteRecordRaw[]} */
const routes = [
  // ─── 公开页面 ───
  {
    path: '/',
    name: 'Landing',
    component: () => import('@/pages/auth/Landing.vue'),
    meta: { requiresGuest: false },
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/pages/auth/Login.vue'),
    meta: { requiresGuest: true },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/pages/auth/Register.vue'),
    meta: { requiresGuest: true },
  },
  {
    path: '/reset-password',
    name: 'ResetPassword',
    component: () => import('@/pages/auth/ResetPassword.vue'),
    meta: { requiresGuest: true },
  },

  // ─── 普通用户 (/user/) ───
  {
    path: '/user',
    component: () => import('@/layouts/UserLayout.vue'),
    meta: { requiresAuth: true, roles: ['user'] },
    children: [
      {
        path: 'dashboard',
        name: 'UserDashboard',
        component: () => import('@/pages/user/Dashboard.vue'),
        meta: { title: '仪表盘' },
      },
      {
        path: 'analysis',
        name: 'SingleAnalysis',
        component: () => import('@/pages/user/SingleAnalysis.vue'),
        meta: { title: '单条分析' },
      },
      {
        path: 'analysis/batch',
        name: 'BatchAnalysis',
        component: () => import('@/pages/user/BatchAnalysis.vue'),
        meta: { title: '批量分析' },
      },
      {
        path: 'history',
        name: 'History',
        component: () => import('@/pages/user/History.vue'),
        meta: { keepAlive: true, title: '分析历史' },
      },
      {
        path: 'history/:id',
        name: 'ResultDetail',
        component: () => import('@/pages/user/ResultDetail.vue'),
        meta: { title: '分析详情' },
      },
      {
        path: 'reports',
        name: 'UserReportCenter',
        component: () => import('@/pages/user/ReportCenter.vue'),
        meta: { title: '报告中心' },
      },
      {
        path: 'profile',
        name: 'UserProfile',
        component: () => import('@/pages/user/Profile.vue'),
        meta: { title: '个人资料' },
      },
    ],
  },

  // ─── 分析师 (/analyst/) ───
  {
    path: '/analyst',
    component: () => import('@/layouts/AnalystLayout.vue'),
    meta: { requiresAuth: true, roles: ['analyst'] },
    children: [
      {
        path: 'overview',
        name: 'AnalystOverview',
        component: () => import('@/pages/analyst/AnalystOverview.vue'),
        meta: { title: '分析师工作台' },
      },
      {
        path: 'comments',
        name: 'CommentsList',
        component: () => import('@/pages/analyst/CommentsList.vue'),
        meta: { keepAlive: true, title: '评论审核' },
      },
      {
        path: 'reports',
        name: 'AnalystReports',
        component: () => import('@/pages/analyst/AnalystReport.vue'),
        meta: { title: '分析师报表' },
      },
      {
        path: 'profile',
        name: 'AnalystProfile',
        component: () => import('@/pages/user/Profile.vue'),
        meta: { title: '个人资料' },
      },
    ],
  },

  // ─── 管理员 (/admin/) ───
  {
    path: '/admin',
    component: () => import('@/layouts/AdminLayout.vue'),
    meta: { requiresAuth: true, roles: ['admin'] },
    children: [
      {
        path: 'dashboard',
        name: 'AdminDashboard',
        component: () => import('@/pages/admin/AdminDashboard.vue'),
        meta: { title: '控制台总览' },
      },
      {
        path: 'users',
        name: 'UserManage',
        component: () => import('@/pages/admin/UserManage.vue'),
        meta: { keepAlive: true, title: '用户管理' },
      },
      {
        path: 'datasets',
        name: 'DatasetManage',
        component: () => import('@/pages/admin/DatasetManage.vue'),
        meta: { title: '数据集管理' },
      },
      {
        path: 'models',
        name: 'ModelManage',
        component: () => import('@/pages/admin/ModelManage.vue'),
        meta: { title: '模型管理' },
      },
      {
        path: 'training',
        name: 'TrainingCenter',
        component: () => import('@/pages/admin/TrainingCenter.vue'),
        meta: { title: '训练中心' },
      },
      {
        path: 'logs',
        name: 'OperationLog',
        component: () => import('@/pages/admin/OperationLog.vue'),
        meta: { keepAlive: true, title: '操作日志' },
      },
      {
        path: 'api-docs',
        name: 'ApiDocs',
        component: () => import('@/pages/admin/ApiDocs.vue'),
        meta: { title: 'API 文档' },
      },
      {
        path: 'backup',
        name: 'DatabaseBackup',
        component: () => import('@/pages/admin/DatabaseBackup.vue'),
        meta: { title: '数据库备份' },
      },
      {
        path: 'profile',
        name: 'AdminProfile',
        component: () => import('@/pages/user/Profile.vue'),
        meta: { title: '个人资料' },
      },
    ],
  },

  // ─── 404 ───
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/pages/NotFound.vue'),
  },
]

const PROFILE_REFRESH_MAX_AGE_MS = 30_000
const ROUTE_CHUNK_RELOAD_MARKER_KEY = 'route-chunk-reload-target'
const ROUTE_CHUNK_ERROR_PATTERNS = [
  'failed to fetch dynamically imported module',
  'error loading dynamically imported module',
  'importing a module script failed',
]

const getRouteFullPath = (route) => {
  return route?.fullPath || route?.path || ''
}

const getCurrentFullPath = () => {
  if (typeof window === 'undefined') return ''
  return `${window.location.pathname}${window.location.search}${window.location.hash}`
}

const getStoredRouteReloadTarget = () => {
  try {
    return window.sessionStorage?.getItem(ROUTE_CHUNK_RELOAD_MARKER_KEY) || ''
  } catch {
    return ''
  }
}

const setStoredRouteReloadTarget = (target) => {
  try {
    window.sessionStorage?.setItem(ROUTE_CHUNK_RELOAD_MARKER_KEY, target)
  } catch {
    // If sessionStorage is unavailable, reloading once is still safer than a blank route.
  }
}

const clearStoredRouteReloadTarget = () => {
  try {
    window.sessionStorage?.removeItem(ROUTE_CHUNK_RELOAD_MARKER_KEY)
  } catch {
    // Ignore storage access errors.
  }
}

const isRouteChunkLoadError = (error) => {
  const message = String(error?.message || error || '').toLowerCase()
  return ROUTE_CHUNK_ERROR_PATTERNS.some((pattern) => message.includes(pattern))
}

const getPrivilegeSurface = (route) => {
  const path = route?.path || ''
  if (path.startsWith('/admin')) return 'admin'
  if (path.startsWith('/analyst')) return 'analyst'
  if (path.startsWith('/user')) return 'user'
  return null
}

const shouldForceProtectedProfileRefresh = (to, from) => {
  const toSurface = getPrivilegeSurface(to)
  if (!toSurface) return false
  const fromSurface = getPrivilegeSurface(from)
  // Don't force if coming from login/register (user was just set by login())
  if (!fromSurface && (from.path === '/login' || from.path === '/register')) return false
  return fromSurface !== toSurface
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

router.onError((error, to) => {
  if (typeof window === 'undefined' || !isRouteChunkLoadError(error)) {
    return
  }

  const target = getRouteFullPath(to) || getCurrentFullPath() || '/'
  if (getStoredRouteReloadTarget() === target) {
    return
  }

  setStoredRouteReloadTarget(target)
  window.location.assign(target)
})

router.afterEach((to) => {
  if (getStoredRouteReloadTarget() === getRouteFullPath(to)) {
    clearStoredRouteReloadTarget()
  }
})

router.beforeEach(async (to, from) => {
  const authStore = useAuthStore()

  const requiresAuth = to.matched.some((record) => record.meta.requiresAuth)
  if (requiresAuth && authStore.token) {
    const force = shouldForceProtectedProfileRefresh(to, from)
    if (authStore.shouldRefreshProfile({ force, maxAgeMs: PROFILE_REFRESH_MAX_AGE_MS })) {
      await authStore.fetchProfile()
    }
  }

  if (requiresAuth && authStore.token && !authStore.user && authStore.profileLoadFailed) {
    nextTick(() => {
      void recoverProtectedSession(authStore, to, router)
    })
    return false
  }

  return resolveProtectedNavigation({
    to,
    matchedRoles: getRouteRoles(to),
    isAuthenticated: isResolvedAuthenticated({
      token: authStore.token,
      user: authStore.user,
    }),
    user: authStore.user,
  })
})

export default router

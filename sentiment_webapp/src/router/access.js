const HOME_ROUTE_BY_ROLE = {
  user: { name: 'UserDashboard' },
  analyst: { name: 'AnalystOverview' },
  admin: { name: 'AdminDashboard' },
}

const DEFAULT_HOME_ROUTE = { name: 'UserDashboard' }

function normalizeRoles(roles) {
  return Array.isArray(roles) ? roles.filter(Boolean) : []
}

function intersectRoles(currentRoles, nextRoles) {
  const normalizedNextRoles = normalizeRoles(nextRoles)

  if (!currentRoles.length) {
    return normalizedNextRoles
  }

  if (!normalizedNextRoles.length) {
    return currentRoles
  }

  const nextRolesSet = new Set(normalizedNextRoles)
  return currentRoles.filter((role) => nextRolesSet.has(role))
}

export function getDefaultHomeRoute(user) {
  const role = user?.role
  return HOME_ROUTE_BY_ROLE[role] || DEFAULT_HOME_ROUTE
}

export function getDefaultUserSurfaceRoute(_user) {
  return { name: 'UserDashboard' }
}

function hasRequiredRole(user, roles = []) {
  const normalizedRoles = normalizeRoles(roles)

  if (!normalizedRoles.length) {
    return true
  }

  return normalizedRoles.includes(user?.role)
}

export function getRouteRoles(to) {
  const matchedRecords = Array.isArray(to?.matched) ? to.matched : []
  const effectiveRoles = matchedRecords.reduce(
    (currentRoles, record) => intersectRoles(currentRoles, record?.meta?.roles),
    []
  )

  if (effectiveRoles.length) {
    return effectiveRoles
  }

  return normalizeRoles(to?.meta?.roles)
}

export function resolveProtectedNavigation({ to, matchedRoles = [], isAuthenticated, user }) {
  const requiresAuth = to.matched.some((record) => record.meta.requiresAuth)
  const requiresGuest = to.matched.some((record) => record.meta.requiresGuest)
  const redirectPath = to.fullPath || '/'

  if (requiresAuth && !isAuthenticated) {
    return { name: 'Login', query: { redirect: redirectPath } }
  }

  if (requiresGuest && isAuthenticated) {
    return getDefaultHomeRoute(user)
  }

  const roles = matchedRoles.length ? matchedRoles : normalizeRoles(to.meta?.roles)
  if (roles.length && !hasRequiredRole(user, roles)) {
    return getDefaultHomeRoute(user)
  }

  return true
}

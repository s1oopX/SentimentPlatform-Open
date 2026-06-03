export function isResolvedAuthenticated({ token, user }) {
  return Boolean(token && user)
}

export function clearSessionScopedDrafts() {
  if (typeof window === 'undefined' || !window.localStorage) return
  try {
    const keys = []
    for (let i = 0; i < window.localStorage.length; i += 1) {
      const key = window.localStorage.key(i)
      if (key && key.startsWith('sentiment-')) {
        keys.push(key)
      }
    }
    keys.forEach((key) => window.localStorage.removeItem(key))
  } catch {
    // Ignore storage access errors (e.g., privacy mode).
  }
}

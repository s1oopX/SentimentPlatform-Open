export const hasCanvasSupport = () => {
  if (typeof document === 'undefined') {
    return false
  }
  const canvas = document.createElement('canvas')
  if (typeof canvas.getContext !== 'function') {
    return false
  }
  try {
    return !!canvas.getContext('2d')
  } catch {
    return false
  }
}

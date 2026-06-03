import { onActivated, ref } from 'vue'

/**
 * 在 keep-alive 页面激活时自动刷新数据，并在首次激活（紧随 onMounted 后）时跳过，避免重复请求。
 * @param {() => Promise<unknown> | unknown} refreshFn 页面的数据刷新函数
 */
export function useRefreshOnActivated(refreshFn) {
  const hasActivatedOnce = ref(false)

  onActivated(async () => {
    if (!hasActivatedOnce.value) {
      hasActivatedOnce.value = true
      return
    }
    await refreshFn()
  })
}

/** @param {any} queryParams @param {Function} fetchFn */
export function usePageSizeReset(queryParams, fetchFn) {
  const handlePageSizeChange = () => {
    queryParams.page = 1
    return fetchFn()
  }

  return { handlePageSizeChange }
}

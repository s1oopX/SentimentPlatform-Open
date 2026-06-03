import 'axios'

declare module 'axios' {
  interface AxiosRequestConfig<D = any> {
    _retry?: boolean
    suppressErrorMessage?: boolean
  }
}

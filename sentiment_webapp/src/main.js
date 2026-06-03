import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { ElMessage } from 'element-plus'
import App from './App.vue'
import router from './router'
import { configureRequestSideEffects } from './api/request'
import { buildLoginRedirectUrl } from './router/loginRedirect'
import './styles/index.css'
import 'element-plus/dist/index.css'

const app = createApp(App)

configureRequestSideEffects({
  onRequestError: ({ message }) => {
    if (message) {
      ElMessage.error(message)
    }
  },
  onSessionExpired: ({ message }) => {
    if (message) {
      ElMessage.error(message)
    }

    try {
      const pathname = window.location?.pathname || '/'
      const search = window.location?.search || ''
      window.location.replace(
        buildLoginRedirectUrl({
          pathname,
          search,
        })
      )
    } catch {
      // Ignore navigation errors (e.g. already on the target page).
    }
  },
})

app.use(createPinia())
app.use(router)

app.mount('#app')

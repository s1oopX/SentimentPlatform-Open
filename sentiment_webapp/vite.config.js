import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

// https://vite.dev/config/
export default defineConfig(() => {
  return {
    build: {
      chunkSizeWarningLimit: 1000,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (!id.includes('node_modules')) {
              return
            }
            if (id.includes('node_modules/echarts') || id.includes('node_modules/zrender')) {
              return 'vendor-echarts'
            }
            if (id.includes('node_modules/axios')) {
              return 'vendor-http'
            }
            if (
              id.includes('node_modules/vue') ||
              id.includes('node_modules/@vue') ||
              id.includes('node_modules/vue-router') ||
              id.includes('node_modules/pinia')
            ) {
              return 'vendor-vue'
            }
          },
        },
      },
    },
    plugins: [
      vue(),
      Components({
        dts: false,
        resolvers: [
          ElementPlusResolver({
            importStyle: false,
          }),
        ],
      }),
    ],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      proxy: {
        '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
        '/media': { target: 'http://127.0.0.1:8000', changeOrigin: true },
        '/redoc': { target: 'http://127.0.0.1:8000', changeOrigin: true },
        '/static': { target: 'http://127.0.0.1:8000', changeOrigin: true },
        '/swagger': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      },
    },
  }
})

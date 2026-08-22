import { fileURLToPath, URL } from 'node:url'

import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd())
  // 前端部署前缀（反代场景），如 /ops/，默认根路径
  const base = env.VITE_BASE ?? '/'
  // 无前缀（base === '/'）时 basePath 为空字符串
  const basePath = (base === '/' ? '' : base).replace(/\/+$/, '')

  return {
    plugins: [
      vue(),
      vueDevTools(),
    ],
    base,
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      port: 3000,
      proxy: {
        // 带前缀时同时代理 API，并剥掉前缀转发给后端
        [`${basePath}/api/pipelines`]: {
          target: 'http://127.0.0.1:8008',
          changeOrigin: true,
          rewrite: (path) => path.replace(`${basePath}/api/pipelines`, '/api/pipelines'),
        },
      },
    },
    build: {
      rollupOptions: {
        output: {
          // 按库分包，缩小入口 index.js，并利用浏览器缓存（rolldown 只支持函数形式）
          manualChunks(id) {
            if (!id.includes('node_modules')) return undefined
            if (id.includes('element-plus')) return 'element-plus'
            if (id.includes('logicflow')) return 'logicflow'
            if (id.includes('jsoneditor')) return 'jsoneditor'
            if (id.includes('katex') || id.includes('markdown-it')) return 'katex-md'
            return 'vendor'
          },
        },
      },
    },
  }
})

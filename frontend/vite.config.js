import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

const envHosts = (process.env.VITE_ALLOWED_HOSTS || process.env.ALLOWED_HOSTS || '')
  .split(',')
  .map(host => host.trim())
  .filter(Boolean)

const hostsFromUrls = [
  process.env.ZEABUR_WEB_URL,
  process.env.ZEABUR_URL,
  process.env.PUBLIC_URL,
  process.env.APP_URL
]
  .map(value => {
    if (!value) return null

    try {
      return new URL(value).hostname
    } catch {
      return value.replace(/^https?:\/\//, '').split('/')[0]
    }
  })
  .filter(Boolean)

const allowedHosts = [
  'report.nexorasocial.net',
  '.zeabur.app',
  '.zeabur.com',
  ...envHosts,
  ...hostsFromUrls
]

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
      '@locales': path.resolve(__dirname, '../locales')
    }
  },
  server: {
    host: '0.0.0.0',
    port: 3000,
    open: false,
    allowedHosts: [...new Set(allowedHosts)],
    proxy: {
      '/api': {
        target: 'http://localhost:5001',
        changeOrigin: true,
        secure: false
      }
    }
  }
})

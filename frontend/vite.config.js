import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

const envHosts = (process.env.VITE_ALLOWED_HOSTS || process.env.ALLOWED_HOSTS || '')
  .split(',')
  .map(host => host.trim())
  .filter(Boolean)

const hostsFromUrls = [
  process.env.PUBLIC_URL,
  process.env.APP_URL,
  process.env.SITE_URL
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

// Only the dev server (`npm run dev`) checks this list; production serves the built
// frontend from Flask (see Dockerfile), so no host allow-listing is needed there.
const allowedHosts = [
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

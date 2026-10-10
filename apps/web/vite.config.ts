import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// 127.0.0.1, not localhost: on Windows "localhost" can resolve to IPv6 (::1) while uvicorn listens on IPv4.
const API_ORIGIN = process.env.API_ORIGIN ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@contracts': fileURLToPath(new URL('../../contracts', import.meta.url)),
    },
  },
  server: {
    port: 3000,
    strictPort: true,
    host: true, // reachable from phones on the LAN
    allowedHosts: true, // Caddy forwards the laptop's LAN address as the Host header
    proxy: { '/api': { target: API_ORIGIN, changeOrigin: false } },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    testTimeout: 20000,
    hookTimeout: 20000,
  },
})

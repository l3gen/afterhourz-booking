import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In AWS the site and API share one CloudFront domain (/api/* -> ALB), so the browser
// always calls relative /api paths. Locally, Vite proxies /api to the FastAPI dev server.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://localhost:8000' } },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.js'],
    globals: true,
  },
})

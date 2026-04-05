import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
// Production: FastAPI serves the built SPA under `/app/` (see `sraosha/api/spa.py`).
// Development: use `/` so `vite` works at http://localhost:5173/ without the base-path warning.
export default defineConfig(({ mode }) => ({
  base: mode === 'production' ? '/app/' : '/',
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/openapi.json': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/docs': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/redoc': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
}))

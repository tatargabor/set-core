import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// The dashboard API the dev server proxies to. Configurable because the installed
// `set-web` service holds the code it STARTED with, so developing against a route
// that service does not have yet needs a second server on another port — and the
// alternative is restarting a service other people's sessions are using.
//
//   SET_API_PORT=7451 pnpm dev
const API_PORT = process.env.SET_API_PORT || '7400'
const API_TARGET = `http://localhost:${API_PORT}`

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api/manager': {
        target: process.env.SET_MANAGER_URL || 'http://localhost:3112',
        rewrite: (path: string) => path.replace(/^\/api\/manager/, '/api'),
      },
      '/api': API_TARGET,
      '/ws': {
        target: API_TARGET,
        ws: true,
      },
    },
  },
})

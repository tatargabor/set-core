import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api/manager': {
        target: 'http://localhost:3112',
        rewrite: (path: string) => path.replace(/^\/api\/manager/, '/api'),
      },
      '/api': 'http://localhost:7400',
      '/ws': {
        target: 'http://localhost:7400',
        ws: true,
      },
    },
  },
})

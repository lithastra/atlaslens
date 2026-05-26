import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/auth': 'http://localhost:8000',
      '/events': 'http://localhost:8000',
      '/aggregations': 'http://localhost:8000',
      '/items': 'http://localhost:8000',
      '/exports': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/sync-status': 'http://localhost:8000',
    },
  },
})

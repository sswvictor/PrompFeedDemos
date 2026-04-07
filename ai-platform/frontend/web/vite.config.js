import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const apiTarget = process.env.VITE_API_TARGET || 'http://127.0.0.1:8002'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@shared': path.resolve(__dirname, '../shared'),
    },
  },
  server: {
    port: parseInt(process.env.PORT || '5174'),
    fs: {
      allow: [path.resolve(__dirname, '..')],
    },
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
        secure: apiTarget.startsWith('https://'),
      },
    },
  },
})
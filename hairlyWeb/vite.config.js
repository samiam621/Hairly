import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      //assumes FastAPI is running on port 8000
      '/api': 'http://127.0.0.1:8000'
    }
  }
})

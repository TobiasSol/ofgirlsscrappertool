import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    allowedHosts: true, // WICHTIG für Replit!
    // Der Proxy leitet alle /api Anfragen an dein Python Backend weiter
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000', // Python läuft auf Port 8000
        changeOrigin: true,
        secure: false,
      }
    }
  }
})
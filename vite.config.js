import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true, // Fail if port is busy
    // Deaktiviere HMR über Netzwerk (verhindert lokale Netzwerk-Suche)
    hmr: {
      clientPort: 5173
    },
    allowedHosts: true // Erlaubt alle Hosts (wichtig für Replit)
  },
  build: {
    // Stelle sicher, dass keine Development-Features im Build sind
    minify: 'esbuild',
    sourcemap: false
  }
})

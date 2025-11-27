import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// E2E-specific Vite configuration
// Uses unique ports to avoid conflicts with dev servers
export default defineConfig({
  plugins: [react()],
  server: {
    port: 13001,  // Unique port for E2E frontend (unlikely to conflict)
  },
  define: {
    'import.meta.env.VITE_E2E_TESTING': JSON.stringify('true'),
  },
})

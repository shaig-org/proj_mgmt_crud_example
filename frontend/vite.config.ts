import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
// Per-worktree port wiring (see docs/tasks/per-worktree-ports/plan.md §3.7):
// - FRONTEND_PORT (non-VITE_-prefixed, server-side only) controls `server.port`.
// - BACKEND_URL (non-VITE_-prefixed, server-side only) is the proxy target for
//   `/api`, `/health`, `/auth` so the browser always talks to the dev server
//   on the frontend port and benefits from same-origin.
// - `define` injects an empty `VITE_BACKEND_URL` into the client bundle so
//   `src/services/api.ts` falls back to relative paths (proxied by Vite).
// Defaults preserve the historical 3000 / http://localhost:8000 behavior when
// `.env.local` is absent.
export default defineConfig(({ mode }) => {
  // Default envDir is the project root (frontend/) — exactly what we want so
  // `frontend/.env.local` (written by devtools/setup-worktree-ports.sh) is
  // auto-loaded. Empty prefix lets us read non-VITE_-prefixed vars.
  const env = { ...loadEnv(mode, process.cwd(), ''), ...process.env }

  const FRONTEND_PORT_RAW = Number(env.FRONTEND_PORT)
  const FRONTEND_PORT = Number.isFinite(FRONTEND_PORT_RAW) && FRONTEND_PORT_RAW > 0
    ? FRONTEND_PORT_RAW
    : 3000

  const BACKEND_URL = env.BACKEND_URL && env.BACKEND_URL.length > 0
    ? env.BACKEND_URL
    : 'http://localhost:8000'

  return {
    plugins: [react()],
    server: {
      port: FRONTEND_PORT,
      proxy: {
        '/api': { target: BACKEND_URL, changeOrigin: false },
        '/health': { target: BACKEND_URL, changeOrigin: false },
        '/auth': { target: BACKEND_URL, changeOrigin: false },
      },
    },
    define: {
      // Empty string → api.ts falls back to the relative path (same-origin, proxied).
      'import.meta.env.VITE_BACKEND_URL': JSON.stringify(''),
    },
  }
})

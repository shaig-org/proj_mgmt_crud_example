// @vitest-environment node
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import path from 'node:path'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'

// Tests for `frontend/vite.config.ts` per plan §4.4. The default export is a
// function `({ mode }) => config`. We invoke it directly with `mode: 'development'`
// and assert on the resolved config object.
//
// Important: the factory calls `loadEnv(mode, process.cwd(), '')` which reads
// `.env.local` from `process.cwd()`. To keep these tests hermetic we:
//   - save/restore `process.env.FRONTEND_PORT` / `process.env.BACKEND_URL`
//   - change `process.cwd()` to a fresh tmp dir with no .env files so loadEnv
//     returns only what's in `process.env`.

type ViteConfigFactory = (ctx: { mode: string; command: 'serve' | 'build' }) => unknown

interface ResolvedConfig {
  server: {
    port: number
    proxy: Record<string, { target: string; changeOrigin: boolean }>
  }
  define: Record<string, string>
}

async function loadConfig(): Promise<ResolvedConfig> {
  // resetModules forces re-execution of the config module so env-var changes
  // (done before calling this helper) take effect.
  vi.resetModules()
  const mod = (await import('../../vite.config')) as { default: ViteConfigFactory }
  const factory = mod.default
  const cfg = factory({ mode: 'development', command: 'serve' }) as ResolvedConfig
  return cfg
}

const ORIGINAL_CWD = process.cwd()
let sandboxDir: string | undefined

beforeEach(() => {
  delete process.env.FRONTEND_PORT
  delete process.env.BACKEND_URL
  sandboxDir = mkdtempSync(path.join(tmpdir(), 'vite-config-test-'))
  process.chdir(sandboxDir)
})

afterEach(() => {
  process.chdir(ORIGINAL_CWD)
  if (sandboxDir) {
    rmSync(sandboxDir, { recursive: true, force: true })
    sandboxDir = undefined
  }
  delete process.env.FRONTEND_PORT
  delete process.env.BACKEND_URL
})

describe('vite.config.ts — server.port', () => {
  it('test_vite_config_frontend_port_defaults_to_3000_when_env_unset', async () => {
    const cfg = await loadConfig()
    expect(cfg.server.port).toBe(3000)
  })

  it('test_vite_config_frontend_port_reads_env', async () => {
    process.env.FRONTEND_PORT = '3010'
    const cfg = await loadConfig()
    expect(cfg.server.port).toBe(3010)
  })

  it('test_vite_config_frontend_port_falls_back_on_non_numeric_env', async () => {
    process.env.FRONTEND_PORT = 'abc'
    const cfg = await loadConfig()
    expect(cfg.server.port).toBe(3000)
  })

  it('test_vite_config_frontend_port_falls_back_on_zero_env', async () => {
    process.env.FRONTEND_PORT = '0'
    const cfg = await loadConfig()
    expect(cfg.server.port).toBe(3000)
  })
})

describe('vite.config.ts — server.proxy', () => {
  it('test_vite_config_proxy_default_backend_url_is_localhost_8000', async () => {
    const cfg = await loadConfig()
    expect(cfg.server.proxy['/api'].target).toBe('http://localhost:8000')
    expect(cfg.server.proxy['/health'].target).toBe('http://localhost:8000')
    expect(cfg.server.proxy['/auth'].target).toBe('http://localhost:8000')
  })

  it('test_vite_config_proxy_reads_backend_url_env', async () => {
    process.env.BACKEND_URL = 'http://localhost:8010'
    const cfg = await loadConfig()
    expect(cfg.server.proxy['/api'].target).toBe('http://localhost:8010')
    expect(cfg.server.proxy['/health'].target).toBe('http://localhost:8010')
    expect(cfg.server.proxy['/auth'].target).toBe('http://localhost:8010')
  })

  it('test_vite_config_proxy_routes_cover_api_health_auth', async () => {
    const cfg = await loadConfig()
    expect(Object.keys(cfg.server.proxy).sort()).toEqual(['/api', '/auth', '/health'])
  })
})

describe('vite.config.ts — define', () => {
  it('test_vite_config_define_sets_vite_backend_url_to_empty_string_literal', async () => {
    const cfg = await loadConfig()
    // JSON.stringify('') === '""' — the literal client-side value will be ''.
    expect(cfg.define['import.meta.env.VITE_BACKEND_URL']).toBe('""')
  })
})

import { describe, it, expect, vi, beforeEach } from 'vitest'

// Tests for `resolveBaseUrl` in frontend/src/services/api.ts, covering the
// precedence documented in docs/tasks/per-worktree-ports/plan.md §4.3:
//   1. VITE_E2E_TESTING='true' wins unconditionally → http://localhost:18000
//   2. VITE_BACKEND_URL (non-empty string) → that exact URL
//   3. both unset or VITE_BACKEND_URL empty string → '' (relative/same-origin)

async function loadResolver() {
  // Re-import the module fresh each test so the module-top-level `resolveBaseUrl`
  // re-reads whatever env we just stubbed.
  vi.resetModules()
  const mod = await import('../../../src/services/api')
  return mod
}

describe('resolveBaseUrl precedence', () => {
  beforeEach(() => {
    vi.unstubAllEnvs()
  })

  it('test_resolve_base_url_returns_e2e_port_when_vite_e2e_testing_true', async () => {
    vi.stubEnv('VITE_E2E_TESTING', 'true')
    const { resolveBaseUrl } = await loadResolver()
    expect(resolveBaseUrl()).toBe('http://localhost:18000')

    // Also true when VITE_BACKEND_URL happens to be set — E2E still wins.
    vi.stubEnv('VITE_BACKEND_URL', 'http://other.test:1234')
    expect(resolveBaseUrl()).toBe('http://localhost:18000')
  })

  it('test_resolve_base_url_returns_vite_backend_url_when_set_and_e2e_unset', async () => {
    vi.stubEnv('VITE_E2E_TESTING', '')
    vi.stubEnv('VITE_BACKEND_URL', 'http://example.test:9000')
    const { resolveBaseUrl } = await loadResolver()
    expect(resolveBaseUrl()).toBe('http://example.test:9000')
  })

  it('test_resolve_base_url_returns_empty_string_when_both_unset', async () => {
    // No stubs at all — both vars undefined.
    const { resolveBaseUrl } = await loadResolver()
    expect(resolveBaseUrl()).toBe('')
  })

  it('test_resolve_base_url_returns_empty_string_when_backend_url_is_empty_string', async () => {
    // This is the exact case Vite's `define: { 'import.meta.env.VITE_BACKEND_URL': '""' }`
    // produces in the dev bundle: VITE_BACKEND_URL is defined as the literal empty string.
    vi.stubEnv('VITE_E2E_TESTING', '')
    vi.stubEnv('VITE_BACKEND_URL', '')
    const { resolveBaseUrl } = await loadResolver()
    expect(resolveBaseUrl()).toBe('')
  })

  it('test_resolve_base_url_precedence_e2e_wins_over_backend_url', async () => {
    vi.stubEnv('VITE_E2E_TESTING', 'true')
    vi.stubEnv('VITE_BACKEND_URL', 'http://x:1')
    const { resolveBaseUrl } = await loadResolver()
    expect(resolveBaseUrl()).toBe('http://localhost:18000')
  })
})

describe('API client baseURL reflects resolveBaseUrl', () => {
  beforeEach(() => {
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  it('test_api_client_issues_relative_paths_when_base_url_empty', async () => {
    const { API_BASE_URL } = await loadResolver()
    expect(API_BASE_URL).toBe('')
  })

  it('test_api_client_prefixes_base_url_when_e2e_testing_true', async () => {
    vi.stubEnv('VITE_E2E_TESTING', 'true')
    const { API_BASE_URL } = await loadResolver()
    expect(API_BASE_URL).toBe('http://localhost:18000')
  })

  it('test_api_client_prefixes_base_url_when_backend_url_configured', async () => {
    vi.stubEnv('VITE_E2E_TESTING', '')
    vi.stubEnv('VITE_BACKEND_URL', 'http://example.test:9000')
    const { API_BASE_URL } = await loadResolver()
    expect(API_BASE_URL).toBe('http://example.test:9000')
  })
})

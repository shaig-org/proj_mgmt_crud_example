import { afterEach, beforeEach, vi } from 'vitest'

// Reset `import.meta.env` stubs between tests so each test starts from a clean
// state (see plan §5.2). `vi.stubEnv` mutates `import.meta.env`; without the
// teardown calls below, a test that sets VITE_E2E_TESTING would leak into the
// next one.
beforeEach(() => {
  vi.unstubAllEnvs()
})

afterEach(() => {
  vi.unstubAllEnvs()
  vi.restoreAllMocks()
})

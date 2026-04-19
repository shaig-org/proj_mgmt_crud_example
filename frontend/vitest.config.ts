import { defineConfig } from 'vitest/config'

// Per docs/tasks/per-worktree-ports/plan.md §5.2: minimal Vitest setup for the
// frontend. jsdom for DOM APIs; globals: true so tests can use describe/it/expect
// without imports; setup file resets import.meta.env between tests.
export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['tests/unit/**/*.test.ts', 'tests/unit/**/*.test.tsx'],
    setupFiles: ['tests/unit/setup.ts'],
  },
})

import { defineConfig, devices } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const TMP_REPO = path.resolve(here, 'tests/.tmp-repo');
const DASHBOARD_PORT = 5279;

export default defineConfig({
  testDir: 'tests/smoke',
  timeout: 30_000,
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: `http://127.0.0.1:${DASHBOARD_PORT}`,
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: devices['Desktop Chrome'],
    },
  ],
  webServer: {
    command: `npx vite --host 127.0.0.1 --port ${DASHBOARD_PORT} --strictPort`,
    port: DASHBOARD_PORT,
    reuseExistingServer: false,
    cwd: here,
    timeout: 60_000,
    env: {
      DEV_DASHBOARD_REPO_ROOT: TMP_REPO,
    },
  },
});

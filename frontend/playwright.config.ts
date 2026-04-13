import { defineConfig, devices } from '@playwright/test';

/**
 * See https://playwright.dev/docs/test-configuration.
 */
export default defineConfig({
  testDir: './e2e',
  /* Global setup and teardown */
  globalSetup: './e2e/global-setup.ts',
  globalTeardown: './e2e/global-teardown.ts',
  /* Run tests in files in parallel */
  fullyParallel: true,
  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: !!process.env.CI,
  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,
  /* Opt out of parallel tests on CI. */
  workers: process.env.CI ? 2 : 4,
  /* Reporter to use. See https://playwright.dev/docs/test-reporters */
  reporter: 'html',

  /* Shared settings for all the projects below. See https://playwright.dev/docs/api/class-testoptions. */
  use: {
    /* Base URL to use in actions like `await page.goto('/')`. */
    baseURL: 'http://localhost:13001',  // E2E frontend port

    /* Collect trace when retrying the failed test. See https://playwright.dev/docs/trace-viewer */
    trace: 'on-first-retry',
  },

  /* Configure projects for major browsers */
  projects: [
    {
      name: 'chromium',
      testDir: './e2e',
      testIgnore: ['**/scenarios/**'],
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'scenarios',
      testDir: './e2e/scenarios',
      outputDir: './evidence/.playwright-output',
      use: {
        ...devices['Desktop Chrome'],
        // Bumped to 1600x900 (from Desktop Chrome's default 1280x720) so
        // GIFs/videos/screenshots have enough pixels to zoom into in the
        // lightbox. Motion GIFs scale to 640px wide; screenshots are full-
        // page and render crisp at 1600.
        viewport: { width: 1600, height: 900 },
        video: { mode: 'on', size: { width: 1600, height: 900 } },
        // Trace is started and stopped manually inside the scenarioTest
        // fixture so we can flush trace.zip to a stable path before
        // Playwright's async reporter phase.
        trace: 'off',
        screenshot: 'off',
      },
    },
  ],

  /* Run your local dev server before starting the tests */
  webServer: [
    {
      command: 'cd ../backend && E2E_TESTING=true uv run uvicorn project_management_crud_example.app:app --port 18000',
      url: 'http://localhost:18000/health',
      reuseExistingServer: !process.env.CI,
      timeout: 120 * 1000,
      env: {
        E2E_TESTING: 'true',
        JWT_SECRET_KEY: 'e2e-test-secret-key-for-playwright-testing-only',
      },
    },
    {
      command: 'npm run dev:e2e',
      url: 'http://localhost:13001',
      reuseExistingServer: !process.env.CI,
      timeout: 120 * 1000,
    },
  ],
});

/**
 * Global teardown for E2E tests.
 *
 * Runs once after all tests to:
 * 1. Report final database statistics
 * 2. Optionally clear the database (in CI)
 * 3. Log test run summary
 */

import { chromium } from '@playwright/test';
import { TEST_CONFIG } from './utils/test-config';

async function globalTeardown() {
  console.log('\n🏁 Starting E2E test global teardown...');

  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    // 1. Get final database statistics
    console.log('✓ Fetching final database statistics...');
    const statsResponse = await page.request.get(`${TEST_CONFIG.API_BASE_URL}/e2e/stats`);

    if (statsResponse.ok()) {
      const stats = await statsResponse.json();
      console.log('✓ Final database stats:', stats);

      // Warn if there's a lot of leftover data
      const totalRecords =
        stats.total_users +
        stats.total_organizations +
        stats.total_projects +
        stats.total_epics +
        stats.total_tickets;

      if (totalRecords > 100) {
        console.warn(
          `⚠️  Warning: ${totalRecords} test records remaining in database. Consider improving test cleanup.`
        );
      }
    }

    // 2. Clear database in CI mode
    if (process.env.CI) {
      console.log('✓ CI mode detected - clearing E2E database...');
      const clearResponse = await page.request.delete(`${TEST_CONFIG.API_BASE_URL}/e2e/clear-all`);
      if (clearResponse.ok()) {
        console.log('✓ E2E database cleared');
      }
    } else {
      console.log('✓ Local mode - preserving database for debugging');
    }

    console.log('✅ Global teardown complete\n');
  } catch (error) {
    console.error('⚠️  Global teardown encountered error (non-fatal):', error);
    // Don't throw - teardown errors shouldn't fail the test run
  } finally {
    await context.close();
    await browser.close();
  }
}

export default globalTeardown;

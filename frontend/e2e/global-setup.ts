/**
 * Global setup for E2E tests.
 *
 * Runs once before all tests to:
 * 1. Verify backend and frontend servers are running
 * 2. Clear the E2E test database
 * 3. Ensure clean slate for test run
 */

import { chromium } from '@playwright/test';
import { TEST_CONFIG } from './utils/test-config';

async function globalSetup() {
  console.log('🚀 Starting E2E test global setup...');

  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    // 1. Check backend health
    console.log(`✓ Checking backend health at ${TEST_CONFIG.API_BASE_URL}/health...`);
    const healthResponse = await page.request.get(`${TEST_CONFIG.API_BASE_URL}/health`);
    if (!healthResponse.ok()) {
      throw new Error(`Backend health check failed: ${healthResponse.status()}`);
    }
    console.log('✓ Backend is healthy');

    // 2. Check frontend is accessible
    console.log(`✓ Checking frontend at ${TEST_CONFIG.FRONTEND_BASE_URL}...`);
    await page.goto(TEST_CONFIG.FRONTEND_BASE_URL, {
      waitUntil: 'networkidle',
      timeout: 30000,
    });
    console.log('✓ Frontend is accessible');

    // 3. Clear E2E test database
    console.log('✓ Clearing E2E test database...');
    const clearResponse = await page.request.delete(`${TEST_CONFIG.API_BASE_URL}/e2e/clear-all`);
    if (!clearResponse.ok()) {
      throw new Error(`Failed to clear E2E database: ${clearResponse.status()}`);
    }
    console.log('✓ E2E database cleared');

    // 4. Verify database is empty (except super admin)
    const statsResponse = await page.request.get(`${TEST_CONFIG.API_BASE_URL}/e2e/stats`);
    if (statsResponse.ok()) {
      const stats = await statsResponse.json();
      console.log('✓ Database stats after cleanup:', stats);
    }

    console.log('✅ Global setup complete - ready to run tests\n');
  } catch (error) {
    console.error('❌ Global setup failed:', error);
    throw error;
  } finally {
    await context.close();
    await browser.close();
  }
}

export default globalSetup;

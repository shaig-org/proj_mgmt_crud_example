/**
 * Test configuration and utilities for E2E testing.
 *
 * This module provides worker-specific test data naming to ensure parallel test isolation.
 */

import { Page } from '@playwright/test';

// Test data prefixes
export const TEST_CONFIG = {
  TEST_PROJECT_PREFIX: 'E2E-Test-',
  TEST_ORG_PREFIX: 'E2E-Org-',
  TEST_USER_PREFIX: 'E2E-User-',
  TEST_EPIC_PREFIX: 'E2E-Epic-',
  TEST_TICKET_PREFIX: 'E2E-Ticket-',
  API_BASE_URL: 'http://localhost:18000',
  FRONTEND_BASE_URL: 'http://localhost:13001',
};

/**
 * Generate a worker-specific unique test organization name for parallel execution.
 * Uses multiple entropy sources to ensure uniqueness across parallel workers.
 *
 * @param baseName - Human-readable base name for the organization
 * @returns Unique organization name including worker ID and entropy
 * @example generateTestOrgName('Acme-Corp') => 'E2E-Org-W0-P1a2b3-Acme-Corp-1735689123456-1735689123456123-abc123xy'
 */
export function generateTestOrgName(baseName: string): string {
  const workerId = process.env.TEST_WORKER_INDEX || '0';
  const timestamp = Date.now();
  const random = Math.random().toString(36).substring(2, 10);
  const processId = process.pid.toString(36);
  const nanoTime = performance.now().toString().replace('.', '');

  return `${TEST_CONFIG.TEST_ORG_PREFIX}W${workerId}-P${processId}-${baseName}-${timestamp}-${nanoTime}-${random}`;
}

/**
 * Generate a worker-specific unique test project name for parallel execution.
 *
 * @param baseName - Human-readable base name for the project
 * @returns Unique project name including worker ID and entropy
 * @example generateTestProjectName('WebApp') => 'E2E-Test-W0-P1a2b3-WebApp-1735689123456-1735689123456123-abc123xy'
 */
export function generateTestProjectName(baseName: string): string {
  const workerId = process.env.TEST_WORKER_INDEX || '0';
  const timestamp = Date.now();
  const random = Math.random().toString(36).substring(2, 10);
  const processId = process.pid.toString(36);
  const nanoTime = performance.now().toString().replace('.', '');

  return `${TEST_CONFIG.TEST_PROJECT_PREFIX}W${workerId}-P${processId}-${baseName}-${timestamp}-${nanoTime}-${random}`;
}

/**
 * Generate a worker-specific unique test username for parallel execution.
 *
 * IMPORTANT: usernames are constrained to 50 chars by the backend
 * (UserData.username `max_length=50`), so this generator is deliberately
 * compact. We use:
 *   - "u"   (1)
 *   - workerId (1-2)
 *   - "-" + baseName (1 + base.length, must be <= ~20)
 *   - "-" + 12 base36 random chars (13)
 * That's ~17 + baseName.length, well under the 50-char cap for any base
 * up to 30 chars. (The bigger generators we use for orgs/projects/etc. all
 * fit the 255-char cap on their respective fields, but tripped this one.)
 *
 * Worker-uniqueness comes from the workerId prefix; cross-run uniqueness
 * comes from 12 base36 random chars (≈ 4×10^18 keyspace, collision-safe).
 *
 * @param baseName - Human-readable base name; keep <= 20 chars.
 * @example generateTestUserName('pm') => 'u0-pm-k3xp7q9w2vlm'
 */
export function generateTestUserName(baseName: string): string {
  const workerId = process.env.TEST_WORKER_INDEX || '0';
  const random = Math.random().toString(36).substring(2, 14).padEnd(12, '0');
  return `u${workerId}-${baseName}-${random}`;
}

/**
 * Generate a worker-specific unique test epic title for parallel execution.
 *
 * @param baseTitle - Human-readable base title for the epic
 * @returns Unique epic title including worker ID and entropy
 */
export function generateTestEpicTitle(baseTitle: string): string {
  const workerId = process.env.TEST_WORKER_INDEX || '0';
  const timestamp = Date.now();
  const random = Math.random().toString(36).substring(2, 10);
  const processId = process.pid.toString(36);
  const nanoTime = performance.now().toString().replace('.', '');

  return `${TEST_CONFIG.TEST_EPIC_PREFIX}W${workerId}-P${processId}-${baseTitle}-${timestamp}-${nanoTime}-${random}`;
}

/**
 * Generate a worker-specific unique test ticket title for parallel execution.
 *
 * @param baseTitle - Human-readable base title for the ticket
 * @returns Unique ticket title including worker ID and entropy
 */
export function generateTestTicketTitle(baseTitle: string): string {
  const workerId = process.env.TEST_WORKER_INDEX || '0';
  const timestamp = Date.now();
  const random = Math.random().toString(36).substring(2, 10);
  const processId = process.pid.toString(36);
  const nanoTime = performance.now().toString().replace('.', '');

  return `${TEST_CONFIG.TEST_TICKET_PREFIX}W${workerId}-P${processId}-${baseTitle}-${timestamp}-${nanoTime}-${random}`;
}

/**
 * Wait for network to become idle (no requests in progress).
 * Useful for ensuring API calls have completed before checking UI state.
 */
export async function waitForNetworkIdle(page: Page, timeout = 5000): Promise<void> {
  await page.waitForLoadState('networkidle', { timeout });
}

/**
 * Wait for content to stabilize (no DOM mutations for a period).
 * Useful for ensuring UI has finished rendering dynamic content.
 */
export async function waitForContentStable(page: Page, timeout = 2000): Promise<void> {
  await page.waitForLoadState('domcontentloaded', { timeout });
  // Additional small wait for any final renders
  await page.waitForTimeout(100);
}

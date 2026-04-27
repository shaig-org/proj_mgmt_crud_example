import { test, expect } from '@playwright/test';
import { loginViaApi } from './utils/auth';

test.describe('Create Project Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Seed auth state via API (one bcrypt per worker, cached) — no UI login.
    await loginViaApi(page, 'admin', 'SuperAdmin123!');
    await page.goto('/projects');
  });

  test('should show New Project button', async ({ page }) => {
    // Should see Projects heading
    await expect(page.getByRole('heading', { name: 'Projects' })).toBeVisible();

    // Should see New Project button
    await expect(page.getByRole('button', { name: 'New Project' })).toBeVisible();
  });

  test('should open create project modal', async ({ page }) => {
    // Click "New Project" button
    await page.getByRole('button', { name: 'New Project' }).click();

    // Modal should appear
    await expect(page.getByRole('heading', { name: 'Create New Project' })).toBeVisible();

    // Should see form fields
    await expect(page.getByLabel('Project Name *')).toBeVisible();
    await expect(page.getByLabel('Description')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Cancel' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Create Project' })).toBeVisible();
  });

  test('can cancel project creation', async ({ page }) => {
    // Click "New Project" button
    await page.getByRole('button', { name: 'New Project' }).click();

    // Fill in some data
    await page.getByLabel('Project Name *').fill('Project I Will Cancel');
    await page.getByLabel('Description').fill('This should not be created');

    // Click Cancel button
    await page.getByRole('button', { name: 'Cancel' }).click();

    // Modal should close
    await expect(page.getByRole('heading', { name: 'Create New Project' })).not.toBeVisible();
  });

  test('can close modal by clicking X button', async ({ page }) => {
    // Click "New Project" button
    await page.getByRole('button', { name: 'New Project' }).click();

    // Fill in some data
    await page.getByLabel('Project Name *').fill('Another Cancelled Project');

    // Click X button
    await page.getByRole('button', { name: 'Close' }).click();

    // Modal should close
    await expect(page.getByRole('heading', { name: 'Create New Project' })).not.toBeVisible();
  });
});

// The "project manager can create a project successfully" happy-path flow
// is covered by create-project.scenario.spec.ts. Modal chrome/cancel
// tests above are retained.

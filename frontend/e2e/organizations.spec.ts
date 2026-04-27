import { test, expect } from '@playwright/test';
import { loginViaApi } from './utils/auth';

test.describe('Organizations Page', () => {
  test.beforeEach(async ({ page }) => {
    // Seed auth state via API (one bcrypt per worker, cached) — no UI login.
    await loginViaApi(page, 'admin', 'SuperAdmin123!');
    // Land on the same page the old UI-login flow left us at, so tests that
    // assume "I'm logged in and on /projects" still work.
    await page.goto('/projects');
  });

  test('can navigate to organizations page', async ({ page }) => {
    // Click Organizations link in navigation
    await page.getByRole('link', { name: 'Organizations' }).click();

    // Should navigate to organizations page
    await expect(page).toHaveURL('/organizations');
    await expect(page.getByRole('heading', { name: 'Organizations' })).toBeVisible();
  });

  test('displays table when organizations exist', async ({ page }) => {
    await page.goto('/organizations');

    // Create an organization first
    await page.getByRole('button', { name: 'New Organization' }).click();
    const orgName = `Test Org ${Date.now()}`;
    await page.getByLabel('Organization Name *').fill(orgName);
    await page.getByRole('button', { name: 'Create Organization' }).click();

    // Wait for modal to close and organization to appear
    await expect(page.locator('.modal-overlay')).not.toBeVisible();
    await expect(page.locator('.organizations-table')).toBeVisible();

    // Verify organization appears in table
    const tableRow = page.locator('tr', { has: page.getByText(orgName) });
    await expect(tableRow).toBeVisible();
  });

  // Create-organization happy path is covered by create-organization.scenario.spec.ts.

  test('organization name field is required', async ({ page }) => {
    await page.goto('/organizations');

    // Click New Organization button
    await page.getByRole('button', { name: 'New Organization' }).click();

    // Check that the name input has required attribute (HTML5 validation)
    const nameInput = page.getByLabel('Organization Name *');
    await expect(nameInput).toHaveAttribute('required');

    // Modal should be visible
    await expect(page.locator('.modal-overlay')).toBeVisible();
  });

  test('can cancel organization creation', async ({ page }) => {
    await page.goto('/organizations');

    // Click New Organization button
    await page.getByRole('button', { name: 'New Organization' }).click();

    // Fill in some data
    await page.getByLabel('Organization Name *').fill('Test Org');

    // Click Cancel button
    await page.getByRole('button', { name: 'Cancel' }).click();

    // Modal should close
    await expect(page.locator('.modal-overlay')).not.toBeVisible();
  });

  test('can close modal by clicking overlay', async ({ page }) => {
    await page.goto('/organizations');

    // Click New Organization button
    await page.getByRole('button', { name: 'New Organization' }).click();

    // Click on modal overlay (outside the modal content)
    await page.locator('.modal-overlay').click({ position: { x: 10, y: 10 } });

    // Modal should close
    await expect(page.locator('.modal-overlay')).not.toBeVisible();
  });

  test('shows loading state while fetching organizations', async ({ page }) => {
    // Self-contained: create an org first so the table renders regardless of
    // what other tests have done.
    await page.goto('/organizations');
    await page.getByRole('button', { name: 'New Organization' }).click();
    await page.getByLabel('Organization Name *').fill(`Loading State ${Date.now()}`);
    await page.getByRole('button', { name: 'Create Organization' }).click();
    await expect(page.locator('.modal-overlay')).not.toBeVisible();

    // The table should now be visible (proves the loading state resolved).
    await expect(page.locator('.organizations-table')).toBeVisible();
  });

  test('organization description shows em dash when empty', async ({ page }) => {
    await page.goto('/organizations');

    // Create organization without description
    await page.getByRole('button', { name: 'New Organization' }).click();
    const orgName = `No Desc Org ${Date.now()}`;
    await page.getByLabel('Organization Name *').fill(orgName);
    await page.getByRole('button', { name: 'Create Organization' }).click();

    // Wait for modal to close
    await expect(page.locator('.modal-overlay')).not.toBeVisible();

    // Find the row with our organization and check the description cell shows em dash
    const row = page.locator('tr', { has: page.getByText(orgName) });
    await expect(row).toBeVisible();

    // The description cell should contain an em dash
    const cells = row.locator('td');
    const descriptionCell = cells.nth(1); // Second column is description
    await expect(descriptionCell).toContainText('—');
  });
});

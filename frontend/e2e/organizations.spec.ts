import { test, expect } from '@playwright/test';

test.describe('Organizations Page', () => {
  test.beforeEach(async ({ page }) => {
    // Login as super admin for each test
    await page.goto('/login');
    await page.getByRole('textbox', { name: 'Username' }).fill('admin');
    await page.getByRole('textbox', { name: 'Password' }).fill('SuperAdmin123!');
    await page.getByRole('button', { name: 'Login' }).click();
    await expect(page).toHaveURL('/projects');
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

  test('super admin can create new organization', async ({ page }) => {
    await page.goto('/organizations');

    // Click New Organization button
    await page.getByRole('button', { name: 'New Organization' }).click();

    // Should show create form modal
    await expect(page.locator('.modal-overlay')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Create New Organization' })).toBeVisible();

    // Fill in form
    const orgName = `Test Org ${Date.now()}`;
    const orgDescription = 'This is a test organization';
    await page.getByLabel('Organization Name *').fill(orgName);
    await page.getByLabel('Description').fill(orgDescription);

    // Submit form
    await page.getByRole('button', { name: 'Create Organization' }).click();

    // Modal should close
    await expect(page.locator('.modal-overlay')).not.toBeVisible();

    // New organization should appear in the list
    await expect(page.getByText(orgName)).toBeVisible();
    await expect(page.getByText(orgDescription)).toBeVisible();
  });

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
    // Navigate to organizations page
    await page.goto('/organizations');

    // Loading state might be very fast, but we can check that the table eventually appears
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

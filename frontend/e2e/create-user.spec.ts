import { test, expect } from '@playwright/test';
import { loginViaApi } from './utils/auth';

test.describe('Create User Flow - UI Elements', () => {
  test.beforeEach(async ({ page }) => {
    // Seed auth state via API (one bcrypt per worker, cached) — no UI login.
    await loginViaApi(page, 'admin', 'SuperAdmin123!');
    await page.goto('/projects');
  });

  test('can navigate to users page', async ({ page }) => {
    // Navigate to users page
    await page.goto('/users');

    // Should see Users heading
    await expect(page.getByRole('heading', { name: 'Users' })).toBeVisible();

    // Should see New User button
    await expect(page.getByRole('button', { name: 'New User' })).toBeVisible();
  });

  test('should open create user modal with all fields', async ({ page }) => {
    await page.goto('/users');

    // Click "New User" button
    await page.getByRole('button', { name: 'New User' }).click();

    // Modal should appear
    await expect(page.getByRole('heading', { name: 'Create New User' })).toBeVisible();

    // Should see all form fields
    await expect(page.getByLabel('Username *')).toBeVisible();
    await expect(page.getByLabel('Email *')).toBeVisible();
    await expect(page.getByLabel('Full Name *')).toBeVisible();
    await expect(page.getByLabel('Organization *')).toBeVisible();
    await expect(page.getByLabel('Role *')).toBeVisible();

    // Should see action buttons
    await expect(page.getByRole('button', { name: 'Cancel' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Create User' })).toBeVisible();
  });

  test('should have role dropdown with all options', async ({ page }) => {
    await page.goto('/users');

    // Click "New User" button
    await page.getByRole('button', { name: 'New User' }).click();

    // Check role dropdown has all options
    const roleSelect = page.getByLabel('Role *');
    await expect(roleSelect).toBeVisible();

    // Get all options
    const options = await roleSelect.locator('option').allTextContents();
    expect(options).toContain('Read Access');
    expect(options).toContain('Write Access');
    expect(options).toContain('Project Manager');
    expect(options).toContain('Admin');
  });

  test('can cancel user creation', async ({ page }) => {
    await page.goto('/users');

    // Click "New User" button
    await page.getByRole('button', { name: 'New User' }).click();

    // Fill in some data
    await page.getByLabel('Username *').fill('testuser');
    await page.getByLabel('Email *').fill('test@example.com');
    await page.getByLabel('Full Name *').fill('Test User');

    // Click Cancel button
    await page.getByRole('button', { name: 'Cancel' }).click();

    // Modal should close
    await expect(page.getByRole('heading', { name: 'Create New User' })).not.toBeVisible();
  });

  test('can close modal by clicking X button', async ({ page }) => {
    await page.goto('/users');

    // Click "New User" button
    await page.getByRole('button', { name: 'New User' }).click();

    // Fill in some data
    await page.getByLabel('Username *').fill('testuser');

    // Click X button
    await page.getByRole('button', { name: 'Close' }).click();

    // Modal should close
    await expect(page.getByRole('heading', { name: 'Create New User' })).not.toBeVisible();
  });
});

// Happy-path create-user flow (fill form → success modal → user appears in
// list) is covered by create-user-with-role.scenario.spec.ts. The remaining
// UI-element tests in this file cover modal chrome and cancel behavior.

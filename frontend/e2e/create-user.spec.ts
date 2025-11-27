import { test, expect } from '@playwright/test';
import { TEST_CONFIG } from './utils/test-config';

test.describe('Create User Flow - UI Elements', () => {
  test.beforeEach(async ({ page }) => {
    // Login via UI as super admin
    await page.goto('/login');
    await page.getByRole('textbox', { name: 'Username' }).fill('admin');
    await page.getByRole('textbox', { name: 'Password' }).fill('SuperAdmin123!');
    await page.getByRole('button', { name: 'Login' }).click();

    // Wait for redirect to projects page
    await expect(page).toHaveURL('/projects');
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

test.describe('Create User Flow - Complete Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Login via UI first
    await page.goto('/login');
    await page.getByRole('textbox', { name: 'Username' }).fill('admin');
    await page.getByRole('textbox', { name: 'Password' }).fill('SuperAdmin123!');
    await page.getByRole('button', { name: 'Login' }).click();
    await expect(page).toHaveURL('/projects');

    // Wait for logout button to be visible (confirms auth state is fully loaded)
    await expect(page.getByRole('button', { name: 'Logout' })).toBeVisible();

    // Get a fresh token via API login (page.request needs its own auth context)
    const loginResponse = await page.request.post(`${TEST_CONFIG.API_BASE_URL}/auth/login`, {
      headers: {
        'Content-Type': 'application/json',
      },
      data: {
        username: 'admin',
        password: 'SuperAdmin123!',
      },
    });

    if (!loginResponse.ok()) {
      const errorText = await loginResponse.text();
      throw new Error(`Failed to login via API: ${loginResponse.status()} - ${errorText}`);
    }

    const loginData = await loginResponse.json();
    const token = loginData.access_token;

    if (!token) {
      throw new Error(`No access_token in login response. Response: ${JSON.stringify(loginData)}`);
    }

    // Create an organization via API
    const orgResponse = await page.request.post(`${TEST_CONFIG.API_BASE_URL}/api/organizations`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
      data: {
        name: `Test Org ${Date.now()}`,
        description: 'E2E test organization',
      },
    });

    // Verify organization was created
    if (!orgResponse.ok()) {
      const errorText = await orgResponse.text();
      throw new Error(`Failed to create organization: ${orgResponse.status()} - ${errorText}`);
    }
  });

  test('can create a new user successfully', async ({ page }) => {
    // Navigate to users page and wait for page to fully load
    await page.goto('/users', { waitUntil: 'networkidle' });
    await expect(page.getByRole('heading', { name: 'Users' })).toBeVisible();

    // Wait a moment for async data loading to complete
    await page.waitForTimeout(500);

    // Click "New User" button
    await page.getByRole('button', { name: 'New User' }).click();

    // Wait for modal to appear
    await expect(page.getByRole('heading', { name: 'Create New User' })).toBeVisible();

    // Fill in the form
    const timestamp = Date.now();
    await page.getByLabel('Username *').fill(`testuser${timestamp}`);
    await page.getByLabel('Email *').fill(`testuser${timestamp}@example.com`);
    await page.getByLabel('Full Name *').fill('Test User');

    // Select first available organization (wait for it to appear)
    const orgSelect = page.getByLabel('Organization *');
    const firstOrgOption = orgSelect.locator('option').nth(0);
    // Wait until the first option is NOT "No organizations available"
    await expect(async () => {
      const optionText = await firstOrgOption.textContent();
      if (optionText === 'No organizations available') {
        throw new Error('Organizations not loaded yet');
      }
    }).toPass({ timeout: 10000 });

    await orgSelect.selectOption({ index: 0 });

    // Select role
    await page.getByLabel('Role *').selectOption('write_access');

    // Submit form
    await page.getByRole('button', { name: 'Create User' }).click();

    // Should see success modal
    await expect(page.getByRole('heading', { name: 'User Created Successfully' })).toBeVisible();

    // Should see the generated password
    await expect(page.getByText(/Generated Password/)).toBeVisible();

    // Should see user details in success modal
    const successModal = page.locator('.modal-overlay').filter({ has: page.getByRole('heading', { name: 'User Created Successfully' }) });
    await expect(successModal.getByText(`testuser${timestamp}`, { exact: true }).first()).toBeVisible();
    await expect(successModal.getByText(`testuser${timestamp}@example.com`).first()).toBeVisible();
    await expect(successModal.getByText('Test User').first()).toBeVisible();

    // Close success modal (click the primary button, not the X)
    await successModal.locator('button.primary-button', { hasText: 'Close' }).click();

    // Should be back on users list
    await expect(page.getByRole('heading', { name: 'Users' })).toBeVisible();

    // New user should appear in the users table
    const usersTable = page.locator('.users-table');
    await expect(usersTable.getByText(`testuser${timestamp}`).first()).toBeVisible();
  });
});

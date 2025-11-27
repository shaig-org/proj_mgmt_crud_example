import { test, expect } from '@playwright/test';
import { TEST_CONFIG } from './utils/test-config';

test.describe('Create Project Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Login as super admin
    await page.goto('/login');
    await page.getByRole('textbox', { name: 'Username' }).fill('admin');
    await page.getByRole('textbox', { name: 'Password' }).fill('SuperAdmin123!');
    await page.getByRole('button', { name: 'Login' }).click();

    // Wait for redirect to projects page
    await expect(page).toHaveURL('/projects');
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

test.describe('Create Project Flow - Complete Flow with Regular User', () => {
  let regularUsername: string;
  let regularPassword: string;

  test.beforeEach(async ({ page }) => {
    // Login as super admin first
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
      headers: { Authorization: `Bearer ${token}` },
      data: {
        name: `Test Org ${Date.now()}`,
        description: 'E2E test organization for project creation',
      },
    });

    if (!orgResponse.ok()) {
      const errorText = await orgResponse.text();
      throw new Error(`Failed to create organization: ${orgResponse.status()} - ${errorText}`);
    }

    const org = await orgResponse.json();

    // Create a user with project_manager role via API
    const timestamp = Date.now();
    regularUsername = `projectmanager${timestamp}`;

    const userResponse = await page.request.post(
      `${TEST_CONFIG.API_BASE_URL}/api/users?organization_id=${org.id}&role=project_manager`,
      {
        headers: { Authorization: `Bearer ${token}` },
        data: {
          username: regularUsername,
          email: `${regularUsername}@example.com`,
          full_name: 'Project Manager User',
        },
      }
    );

    if (!userResponse.ok()) {
      const errorText = await userResponse.text();
      throw new Error(`Failed to create user: ${userResponse.status()} - ${errorText}`);
    }

    const userData = await userResponse.json();
    regularPassword = userData.generated_password;

    if (!regularPassword) {
      throw new Error(
        `Failed to get generated password from API response. Response: ${JSON.stringify(userData)}`
      );
    }

    // Logout super admin
    await page.getByRole('button', { name: 'Logout' }).click();
    await expect(page).toHaveURL('/login');
  });

  test('project manager can create a project successfully', async ({ page }) => {
    // Login as the regular user
    await page.getByRole('textbox', { name: 'Username' }).fill(regularUsername);
    await page.getByRole('textbox', { name: 'Password' }).fill(regularPassword);
    await page.getByRole('button', { name: 'Login' }).click();
    await expect(page).toHaveURL('/projects');

    // Should see Projects page
    await expect(page.getByRole('heading', { name: 'Projects' })).toBeVisible();

    // Click "New Project" button
    await page.getByRole('button', { name: 'New Project' }).click();

    // Wait for modal to appear
    await expect(page.getByRole('heading', { name: 'Create New Project' })).toBeVisible();

    // Fill in the form
    const timestamp = Date.now();
    const projectName = `Test Project ${timestamp}`;
    const projectDescription = 'E2E test project created by regular user';

    await page.getByLabel('Project Name *').fill(projectName);
    await page.getByLabel('Description').fill(projectDescription);

    // Submit form
    await page.getByRole('button', { name: 'Create Project' }).click();

    // Modal should close
    await expect(page.getByRole('heading', { name: 'Create New Project' })).not.toBeVisible();

    // New project should appear in the projects list
    await expect(page.getByText(projectName)).toBeVisible();
    await expect(page.getByText(projectDescription)).toBeVisible();
  });
});

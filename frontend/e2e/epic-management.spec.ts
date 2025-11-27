import { test, expect } from '@playwright/test';
import { TEST_CONFIG } from './utils/test-config';

test.describe('Epic Management', () => {
  let projectId: string;

  test.beforeEach(async ({ page }) => {
    // Login as super admin
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
        description: 'E2E test organization',
      },
    });

    if (!orgResponse.ok()) {
      const errorText = await orgResponse.text();
      throw new Error(`Failed to create organization: ${orgResponse.status()} - ${errorText}`);
    }

    const org = await orgResponse.json();

    // Create a user with project_manager role
    const timestamp = Date.now();
    const username = `pm${timestamp}`;

    const userResponse = await page.request.post(
      `${TEST_CONFIG.API_BASE_URL}/api/users?organization_id=${org.id}&role=project_manager`,
      {
        headers: { Authorization: `Bearer ${token}` },
        data: {
          username,
          email: `${username}@example.com`,
          full_name: 'PM User',
        },
      }
    );

    if (!userResponse.ok()) {
      const errorText = await userResponse.text();
      throw new Error(`Failed to create user: ${userResponse.status()} - ${errorText}`);
    }

    const userData = await userResponse.json();
    const password = userData.generated_password;

    if (!password) {
      throw new Error(
        `Failed to get generated password from API response. Response: ${JSON.stringify(userData)}`
      );
    }

    // Logout super admin
    await page.getByRole('button', { name: 'Logout' }).click();
    await expect(page).toHaveURL('/login');

    // Login as project manager
    await page.getByRole('textbox', { name: 'Username' }).fill(username);
    await page.getByRole('textbox', { name: 'Password' }).fill(password);
    await page.getByRole('button', { name: 'Login' }).click();
    await expect(page).toHaveURL('/projects');

    // Create a project
    await page.getByRole('button', { name: 'New Project' }).click();
    const projectName = `Test Project ${Date.now()}`;
    await page.getByLabel('Project Name *').fill(projectName);
    await page.getByLabel('Description').fill('Test project description');
    await page.getByRole('button', { name: 'Create Project' }).click();

    // Wait for modal to close and project to appear
    await expect(page.getByRole('heading', { name: 'Create New Project' })).not.toBeVisible();
    await expect(page.getByText(projectName)).toBeVisible();

    // Extract project ID from the link
    const projectLink = page.locator('.project-link').filter({ hasText: projectName });
    const href = await projectLink.getAttribute('href');
    projectId = href?.split('/').pop() || '';

    // Navigate to project details
    await projectLink.click();
    await expect(page).toHaveURL(`/projects/${projectId}`);
  });

  test('can create a new epic from project details page', async ({ page }) => {
    // Should see Epics section with New Epic button
    await expect(page.getByRole('heading', { name: 'Epics' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'New Epic' })).toBeVisible();

    // Should show placeholder when no epics exist
    await expect(page.getByText('No epics yet. Create one to get started.')).toBeVisible();

    // Click New Epic button
    await page.getByRole('button', { name: 'New Epic' }).click();

    // Should see create epic modal
    await expect(page.getByRole('heading', { name: 'Create New Epic' })).toBeVisible();

    // Fill in epic details
    const epicName = `Test Epic ${Date.now()}`;
    await page.getByLabel('Epic Name *').fill(epicName);
    await page.getByLabel('Description').fill('Test epic description');

    // Submit form
    await page.getByRole('button', { name: 'Create Epic' }).click();

    // Modal should close
    await expect(page.getByRole('heading', { name: 'Create New Epic' })).not.toBeVisible();

    // Epic should appear in the table
    await expect(page.getByText(epicName)).toBeVisible();
    await expect(page.getByText('Test epic description')).toBeVisible();

    // Placeholder should not be visible
    await expect(page.getByText('No epics yet. Create one to get started.')).not.toBeVisible();
  });

  test('can create multiple epics', async ({ page }) => {
    // Create first epic
    await page.getByRole('button', { name: 'New Epic' }).click();
    const epicName1 = `Epic One ${Date.now()}`;
    await page.getByLabel('Epic Name *').fill(epicName1);
    await page.getByRole('button', { name: 'Create Epic' }).click();
    await expect(page.getByText(epicName1)).toBeVisible();

    // Create second epic
    await page.getByRole('button', { name: 'New Epic' }).click();
    const epicName2 = `Epic Two ${Date.now()}`;
    await page.getByLabel('Epic Name *').fill(epicName2);
    await page.getByLabel('Description').fill('Second epic');
    await page.getByRole('button', { name: 'Create Epic' }).click();
    await expect(page.getByText(epicName2)).toBeVisible();

    // Both epics should be visible
    await expect(page.getByText(epicName1)).toBeVisible();
    await expect(page.getByText(epicName2)).toBeVisible();
    await expect(page.getByText('Second epic')).toBeVisible();
  });

  test('epic name is required', async ({ page }) => {
    // Click New Epic button
    await page.getByRole('button', { name: 'New Epic' }).click();

    // Try to submit without name
    await page.getByRole('button', { name: 'Create Epic' }).click();

    // Modal should still be visible (HTML5 validation prevents submission)
    await expect(page.getByRole('heading', { name: 'Create New Epic' })).toBeVisible();
  });

  test('can cancel epic creation', async ({ page }) => {
    // Click New Epic button
    await page.getByRole('button', { name: 'New Epic' }).click();
    await expect(page.getByRole('heading', { name: 'Create New Epic' })).toBeVisible();

    // Fill in some data
    await page.getByLabel('Epic Name *').fill('Test Epic');

    // Click Cancel
    await page.getByRole('button', { name: 'Cancel' }).click();

    // Modal should close
    await expect(page.getByRole('heading', { name: 'Create New Epic' })).not.toBeVisible();

    // No epic should be created
    await expect(page.getByText('No epics yet. Create one to get started.')).toBeVisible();
  });

  test('can close epic creation modal by clicking overlay', async ({ page }) => {
    // Click New Epic button
    await page.getByRole('button', { name: 'New Epic' }).click();
    await expect(page.getByRole('heading', { name: 'Create New Epic' })).toBeVisible();

    // Click on the overlay (outside the modal)
    await page.locator('.modal-overlay').click({ position: { x: 5, y: 5 } });

    // Modal should close
    await expect(page.getByRole('heading', { name: 'Create New Epic' })).not.toBeVisible();
  });

  test('epic description is optional', async ({ page }) => {
    // Create epic without description
    await page.getByRole('button', { name: 'New Epic' }).click();
    const epicName = `Epic No Description ${Date.now()}`;
    await page.getByLabel('Epic Name *').fill(epicName);
    await page.getByRole('button', { name: 'Create Epic' }).click();

    // Epic should be created and show em dash for empty description
    await expect(page.getByText(epicName)).toBeVisible();

    // Check that the epic row exists and contains the em dash
    const epicRow = page.locator('tr').filter({ hasText: epicName });
    await expect(epicRow).toBeVisible();
    await expect(epicRow.locator('td').nth(1)).toHaveText('—');
  });

  test('displays epic creation timestamp', async ({ page }) => {
    // Create epic
    await page.getByRole('button', { name: 'New Epic' }).click();
    const epicName = `Timestamped Epic ${Date.now()}`;
    await page.getByLabel('Epic Name *').fill(epicName);
    await page.getByRole('button', { name: 'Create Epic' }).click();

    // Should show creation date
    const epicRow = page.locator('tr').filter({ hasText: epicName });
    const dateCell = epicRow.locator('td').nth(2);

    // Should contain a date (we can't predict exact format, but it should exist)
    const dateText = await dateCell.textContent();
    expect(dateText).toBeTruthy();
    expect(dateText?.length).toBeGreaterThan(0);
  });
});

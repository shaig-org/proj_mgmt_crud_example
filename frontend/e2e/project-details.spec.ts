import { test, expect } from '@playwright/test';
import { TEST_CONFIG } from './utils/test-config';

test.describe('Project Details Page', () => {
  let projectId: string;
  let projectName: string;

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
    projectName = `Test Project ${Date.now()}`;
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
  });

  test('can navigate to project details by clicking project name', async ({ page }) => {
    // Click on the project name
    await page.locator('.project-link').filter({ hasText: projectName }).click();

    // Should navigate to project details page
    await expect(page).toHaveURL(`/projects/${projectId}`);

    // Should see project name as heading
    await expect(page.getByRole('heading', { name: projectName })).toBeVisible();
  });

  test('project details page shows all project information', async ({ page }) => {
    // Navigate to project details
    await page.goto(`/projects/${projectId}`);

    // Should see back link
    await expect(page.getByRole('link', { name: '← Back to Projects' })).toBeVisible();

    // Should see project name
    await expect(page.getByRole('heading', { name: projectName })).toBeVisible();

    // Should see Project Information section
    await expect(page.getByRole('heading', { name: 'Project Information' })).toBeVisible();

    // Should see description
    await expect(page.getByText('Test project description')).toBeVisible();

    // Should see status badge
    await expect(page.locator('.status-badge')).toBeVisible();

    // Should see timestamps
    await expect(page.locator('dt').filter({ hasText: 'Created' })).toBeVisible();
    await expect(page.locator('dt').filter({ hasText: 'Last Updated' })).toBeVisible();

    // Should see placeholder sections
    await expect(page.getByRole('heading', { name: 'Epics' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Tickets' })).toBeVisible();
  });

  test('back link navigates to projects list', async ({ page }) => {
    // Navigate to project details
    await page.goto(`/projects/${projectId}`);

    // Click back link
    await page.getByRole('link', { name: '← Back to Projects' }).click();

    // Should navigate back to projects list
    await expect(page).toHaveURL('/projects');
    await expect(page.getByRole('heading', { name: 'Projects' })).toBeVisible();
  });

  test('invalid project ID shows error', async ({ page }) => {
    // Navigate to non-existent project
    await page.goto('/projects/invalid-project-id-12345');

    // Should show error message (404 error from API)
    await expect(page.getByText(/Request failed with status code 404|Failed to load project|Project not found/)).toBeVisible();

    // Should see back link
    await expect(page.getByRole('link', { name: '← Back to Projects' })).toBeVisible();
  });
});

import { test, expect } from '@playwright/test';
import {
  TEST_CONFIG,
  generateTestOrgName,
  generateTestProjectName,
  generateTestUserName,
} from './utils/test-config';
import { loginViaApi } from './utils/auth';

test.describe('Project Details Page', () => {
  let projectId: string;
  let projectName: string;

  test.beforeEach(async ({ page }) => {
    // Admin login (cached per worker — one bcrypt total) to provision data.
    const adminToken = await loginViaApi(page, 'admin', 'SuperAdmin123!');

    // Create an organization via API. Worker-namespaced name to avoid
    // collisions with concurrent workers (Date.now() alone is NOT enough).
    const orgResponse = await page.request.post(`${TEST_CONFIG.API_BASE_URL}/api/organizations`, {
      headers: { Authorization: `Bearer ${adminToken}` },
      data: {
        name: generateTestOrgName('ProjDetails'),
        description: 'E2E test organization',
      },
    });
    if (!orgResponse.ok()) {
      throw new Error(`Failed to create organization: ${orgResponse.status()} - ${await orgResponse.text()}`);
    }
    const org = await orgResponse.json();

    // Create a project_manager user via API. Worker-namespaced name.
    const pmUsername = generateTestUserName('pm');
    const userResponse = await page.request.post(
      `${TEST_CONFIG.API_BASE_URL}/api/users?organization_id=${org.id}&role=project_manager`,
      {
        headers: { Authorization: `Bearer ${adminToken}` },
        data: {
          username: pmUsername,
          email: `${pmUsername}@example.com`,
          full_name: 'PM User',
        },
      }
    );
    if (!userResponse.ok()) {
      throw new Error(`Failed to create user: ${userResponse.status()} - ${await userResponse.text()}`);
    }
    const { generated_password: pmPassword } = await userResponse.json();
    if (!pmPassword) {
      throw new Error('No generated_password in user response');
    }

    // Re-seed auth state as the PM user (also cached per worker per username).
    const pmToken = await loginViaApi(page, pmUsername, pmPassword);

    // Create a project for this test via API. Worker-namespaced name.
    projectName = generateTestProjectName('ProjDetails');
    const projectResponse = await page.request.post(`${TEST_CONFIG.API_BASE_URL}/api/projects`, {
      headers: { Authorization: `Bearer ${pmToken}` },
      data: {
        name: projectName,
        description: 'Test project description',
      },
    });
    if (!projectResponse.ok()) {
      throw new Error(`Failed to create project: ${projectResponse.status()} - ${await projectResponse.text()}`);
    }
    const project = await projectResponse.json();
    projectId = project.id;

    // Land on /projects so tests that click the project link from the list still work.
    await page.goto('/projects');
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

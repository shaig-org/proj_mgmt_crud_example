import { test, expect } from '@playwright/test';
import {
  TEST_CONFIG,
  generateTestOrgName,
  generateTestProjectName,
  generateTestUserName,
} from './utils/test-config';
import { loginViaApi } from './utils/auth';

test.describe('Epic Management', () => {
  let projectId: string;

  test.beforeEach(async ({ page }) => {
    // Admin login (cached per worker — one bcrypt total) to provision data.
    const adminToken = await loginViaApi(page, 'admin', 'SuperAdmin123!');

    // Create an organization via API. Worker-namespaced name to avoid
    // collisions with concurrent workers (Date.now() alone is NOT enough).
    const orgResponse = await page.request.post(`${TEST_CONFIG.API_BASE_URL}/api/organizations`, {
      headers: { Authorization: `Bearer ${adminToken}` },
      data: {
        name: generateTestOrgName('EpicMgmt'),
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
    const projectResponse = await page.request.post(`${TEST_CONFIG.API_BASE_URL}/api/projects`, {
      headers: { Authorization: `Bearer ${pmToken}` },
      data: {
        name: generateTestProjectName('EpicMgmt'),
        description: 'Test project description',
      },
    });
    if (!projectResponse.ok()) {
      throw new Error(`Failed to create project: ${projectResponse.status()} - ${await projectResponse.text()}`);
    }
    const project = await projectResponse.json();
    projectId = project.id;

    // Navigate to project details.
    await page.goto(`/projects/${projectId}`);
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

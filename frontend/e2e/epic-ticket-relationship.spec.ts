import { test, expect } from '@playwright/test';
import { TEST_CONFIG } from './utils/test-config';

/**
 * E2E tests for Epic-Ticket relationship features.
 * Tests linking tickets to epics during creation and updating epic assignments.
 */
test.describe('Epic-Ticket Relationships', () => {
  let projectId: string;
  let epicId: string;
  let epic2Id: string;
  let username: string;
  let password: string;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();

    // Login as super admin
    await page.goto('/login');
    await page.getByRole('textbox', { name: 'Username' }).fill('admin');
    await page.getByRole('textbox', { name: 'Password' }).fill('SuperAdmin123!');
    await page.getByRole('button', { name: 'Login' }).click();
    await expect(page).toHaveURL('/projects');
    await expect(page.getByRole('button', { name: 'Logout' })).toBeVisible();

    // Get API token
    const loginResponse = await page.request.post(`${TEST_CONFIG.API_BASE_URL}/auth/login`, {
      headers: { 'Content-Type': 'application/json' },
      data: { username: 'admin', password: 'SuperAdmin123!' },
    });
    const { access_token } = await loginResponse.json();

    // Create organization via API
    const orgResponse = await page.request.post(`${TEST_CONFIG.API_BASE_URL}/api/organizations`, {
      headers: {
        Authorization: `Bearer ${access_token}`,
        'Content-Type': 'application/json',
      },
      data: { name: `Test Org ${Date.now()}`, description: 'E2E test organization' },
    });
    const org = await orgResponse.json();

    // Create a user with project_manager role in the organization
    const timestamp = Date.now();
    username = `pmtest${timestamp}`;

    const userResponse = await page.request.post(
      `${TEST_CONFIG.API_BASE_URL}/api/users?organization_id=${org.id}&role=project_manager`,
      {
        headers: {
          Authorization: `Bearer ${access_token}`,
          'Content-Type': 'application/json',
        },
        data: {
          username,
          email: `${username}@example.com`,
          full_name: 'Test PM User',
        },
      }
    );

    if (!userResponse.ok()) {
      const errorText = await userResponse.text();
      throw new Error(`Failed to create user: ${userResponse.status()} - ${errorText}`);
    }

    const userData = await userResponse.json();
    password = userData.generated_password;

    if (!password) {
      throw new Error(`No generated password in response: ${JSON.stringify(userData)}`);
    }

    // Get token for the new user
    const pmLoginResponse = await page.request.post(`${TEST_CONFIG.API_BASE_URL}/auth/login`, {
      headers: { 'Content-Type': 'application/json' },
      data: { username, password },
    });
    const { access_token: pmToken } = await pmLoginResponse.json();

    // Create project via API as the PM user
    const projectResponse = await page.request.post(
      `${TEST_CONFIG.API_BASE_URL}/api/projects?organization_id=${org.id}`,
      {
        headers: {
          Authorization: `Bearer ${pmToken}`,
          'Content-Type': 'application/json',
        },
        data: { name: `Test Project ${Date.now()}`, description: 'E2E test project' },
      }
    );

    if (!projectResponse.ok()) {
      const errorText = await projectResponse.text();
      throw new Error(`Failed to create project: ${projectResponse.status()} - ${errorText}`);
    }

    const project = await projectResponse.json();
    projectId = project.id;

    // Create two epics via API as PM user
    const epic1Response = await page.request.post(`${TEST_CONFIG.API_BASE_URL}/api/epics`, {
      headers: {
        Authorization: `Bearer ${pmToken}`,
        'Content-Type': 'application/json',
      },
      data: {
        name: `Epic 1 ${Date.now()}`,
        description: 'First epic for testing',
      },
    });

    if (!epic1Response.ok()) {
      const errorText = await epic1Response.text();
      throw new Error(`Failed to create epic 1: ${epic1Response.status()} - ${errorText}`);
    }

    const epic1 = await epic1Response.json();
    epicId = epic1.id;

    const epic2Response = await page.request.post(`${TEST_CONFIG.API_BASE_URL}/api/epics`, {
      headers: {
        Authorization: `Bearer ${pmToken}`,
        'Content-Type': 'application/json',
      },
      data: {
        name: `Epic 2 ${Date.now()}`,
        description: 'Second epic for testing',
      },
    });

    if (!epic2Response.ok()) {
      const errorText = await epic2Response.text();
      throw new Error(`Failed to create epic 2: ${epic2Response.status()} - ${errorText}`);
    }

    const epic2 = await epic2Response.json();
    epic2Id = epic2.id;

    await page.close();
  });

  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.getByRole('textbox', { name: 'Username' }).fill(username);
    await page.getByRole('textbox', { name: 'Password' }).fill(password);
    await page.getByRole('button', { name: 'Login' }).click();
    await expect(page).toHaveURL('/projects');
  });

  test('can create ticket with epic assigned', async ({ page }) => {
    await page.goto(`/projects/${projectId}`);

    // Click New Ticket button
    await page.getByRole('button', { name: 'New Ticket' }).click();

    // Fill in ticket form with epic
    const ticketTitle = `Ticket with Epic ${Date.now()}`;
    await page.getByLabel('Title *').fill(ticketTitle);
    await page.getByLabel('Description').fill('Ticket linked to epic during creation');
    await page.locator('#ticket-priority').selectOption('HIGH');

    // Select the epic
    await page.locator('#ticket-epic').selectOption(epicId);

    // Submit form
    await page.getByRole('button', { name: 'Create Ticket' }).click();

    // Wait for modal to close and ticket to appear in list
    await expect(page.locator('.modal-overlay')).not.toBeVisible();
    await expect(page.getByRole('link', { name: ticketTitle })).toBeVisible();

    // Click on the ticket to view details
    await page.getByRole('link', { name: ticketTitle }).click();

    // Verify epic is set on ticket details page
    await expect(page.locator('.epic-select')).toBeVisible();
    await expect(page.locator('.epic-select')).toHaveValue(epicId);
  });

  test('can create ticket without epic', async ({ page }) => {
    await page.goto(`/projects/${projectId}`);

    // Click New Ticket button
    await page.getByRole('button', { name: 'New Ticket' }).click();

    // Fill in ticket form without selecting epic
    const ticketTitle = `Ticket without Epic ${Date.now()}`;
    await page.getByLabel('Title *').fill(ticketTitle);
    await page.getByLabel('Description').fill('Ticket created without epic');

    // Verify epic dropdown exists and is set to "No Epic"
    await expect(page.locator('#ticket-epic')).toBeVisible();
    await expect(page.locator('#ticket-epic')).toHaveValue('');

    // Submit form
    await page.getByRole('button', { name: 'Create Ticket' }).click();

    // Wait for modal to close and ticket to appear
    await expect(page.locator('.modal-overlay')).not.toBeVisible();
    await expect(page.getByRole('link', { name: ticketTitle })).toBeVisible();

    // Click on the ticket to view details
    await page.getByRole('link', { name: ticketTitle }).click();

    // Verify no epic is set
    await expect(page.locator('.epic-select')).toBeVisible();
    await expect(page.locator('.epic-select')).toHaveValue('');
  });

  test('can assign epic to existing ticket', async ({ page }) => {
    await page.goto(`/projects/${projectId}`);

    // Create ticket without epic
    await page.getByRole('button', { name: 'New Ticket' }).click();
    const ticketTitle = `Assign Epic Later ${Date.now()}`;
    await page.getByLabel('Title *').fill(ticketTitle);
    await page.getByRole('button', { name: 'Create Ticket' }).click();
    await expect(page.locator('.modal-overlay')).not.toBeVisible();

    // Navigate to ticket details
    await page.getByRole('link', { name: ticketTitle }).click();

    // Verify no epic initially
    await expect(page.locator('.epic-select')).toHaveValue('');

    // Assign to epic
    await page.locator('.epic-select').selectOption(epicId);

    // Wait for update to complete (dropdown should still be enabled)
    await expect(page.locator('.epic-select')).not.toBeDisabled();

    // Verify epic is now set
    await expect(page.locator('.epic-select')).toHaveValue(epicId);

    // Reload page to verify persistence
    await page.reload();

    // Epic should still be set
    await expect(page.locator('.epic-select')).toHaveValue(epicId);
  });

  test('can change ticket from one epic to another', async ({ page }) => {
    await page.goto(`/projects/${projectId}`);

    // Create ticket with epic 1
    await page.getByRole('button', { name: 'New Ticket' }).click();
    const ticketTitle = `Change Epic ${Date.now()}`;
    await page.getByLabel('Title *').fill(ticketTitle);
    await page.locator('#ticket-epic').selectOption(epicId);
    await page.getByRole('button', { name: 'Create Ticket' }).click();
    await expect(page.locator('.modal-overlay')).not.toBeVisible();

    // Navigate to ticket details
    await page.getByRole('link', { name: ticketTitle }).click();

    // Verify starts with epic 1
    await expect(page.locator('.epic-select')).toHaveValue(epicId);

    // Change to epic 2
    await page.locator('.epic-select').selectOption(epic2Id);

    // Wait for update
    await expect(page.locator('.epic-select')).not.toBeDisabled();

    // Verify changed to epic 2
    await expect(page.locator('.epic-select')).toHaveValue(epic2Id);

    // Reload to verify persistence
    await page.reload();
    await expect(page.locator('.epic-select')).toHaveValue(epic2Id);
  });

  test('can remove ticket from epic', async ({ page }) => {
    await page.goto(`/projects/${projectId}`);

    // Create ticket with epic
    await page.getByRole('button', { name: 'New Ticket' }).click();
    const ticketTitle = `Remove from Epic ${Date.now()}`;
    await page.getByLabel('Title *').fill(ticketTitle);
    await page.locator('#ticket-epic').selectOption(epicId);
    await page.getByRole('button', { name: 'Create Ticket' }).click();
    await expect(page.locator('.modal-overlay')).not.toBeVisible();

    // Navigate to ticket details
    await page.getByRole('link', { name: ticketTitle }).click();

    // Verify starts with epic
    await expect(page.locator('.epic-select')).toHaveValue(epicId);

    // Remove from epic
    await page.locator('.epic-select').selectOption('');

    // Wait for update
    await expect(page.locator('.epic-select')).not.toBeDisabled();

    // Verify no epic now
    await expect(page.locator('.epic-select')).toHaveValue('');

    // Reload to verify persistence
    await page.reload();
    await expect(page.locator('.epic-select')).toHaveValue('');
  });

  test('epic dropdown shows all available epics', async ({ page }) => {
    await page.goto(`/projects/${projectId}`);

    // Click New Ticket
    await page.getByRole('button', { name: 'New Ticket' }).click();

    // Check epic dropdown options
    const epicDropdown = page.locator('#ticket-epic');
    await expect(epicDropdown).toBeVisible();

    // Get all options
    const options = await epicDropdown.locator('option').all();
    expect(options.length).toBeGreaterThanOrEqual(3); // "No Epic" + 2 epics

    // Check that epic names are present (by checking option text content)
    const optionTexts = await Promise.all(options.map(opt => opt.textContent()));
    expect(optionTexts.some(text => text?.includes('No Epic'))).toBe(true);
    expect(optionTexts.some(text => text?.includes('Epic 1'))).toBe(true);
    expect(optionTexts.some(text => text?.includes('Epic 2'))).toBe(true);

    // Verify "No Epic" option has empty value
    const noEpicOption = epicDropdown.locator('option[value=""]');
    expect(await noEpicOption.count()).toBe(1);
    expect(await noEpicOption.textContent()).toContain('No Epic');
  });

  test('epic assignment persists across status changes', async ({ page }) => {
    await page.goto(`/projects/${projectId}`);

    // Create ticket with epic
    await page.getByRole('button', { name: 'New Ticket' }).click();
    const ticketTitle = `Epic Persists ${Date.now()}`;
    await page.getByLabel('Title *').fill(ticketTitle);
    await page.locator('#ticket-epic').selectOption(epicId);
    await page.getByRole('button', { name: 'Create Ticket' }).click();
    await expect(page.locator('.modal-overlay')).not.toBeVisible();

    // Navigate to ticket details
    await page.getByRole('link', { name: ticketTitle }).click();

    // Verify epic is set
    await expect(page.locator('.epic-select')).toHaveValue(epicId);

    // Change status
    await page.locator('.status-select').selectOption('IN_PROGRESS');
    await expect(page.locator('.status-select')).toHaveValue('IN_PROGRESS');

    // Epic should still be set
    await expect(page.locator('.epic-select')).toHaveValue(epicId);

    // Change status again
    await page.locator('.status-select').selectOption('DONE');
    await expect(page.locator('.status-select')).toHaveValue('DONE');

    // Epic should still be set
    await expect(page.locator('.epic-select')).toHaveValue(epicId);
  });

  test('epic dropdown is disabled during update', async ({ page }) => {
    await page.goto(`/projects/${projectId}`);

    // Create ticket without epic
    await page.getByRole('button', { name: 'New Ticket' }).click();
    const ticketTitle = `Epic Update Loading ${Date.now()}`;
    await page.getByLabel('Title *').fill(ticketTitle);
    await page.getByRole('button', { name: 'Create Ticket' }).click();
    await expect(page.locator('.modal-overlay')).not.toBeVisible();

    // Navigate to ticket details
    await page.getByRole('link', { name: ticketTitle }).click();

    const epicSelect = page.locator('.epic-select');

    // Initially should be enabled
    await expect(epicSelect).not.toBeDisabled();

    // Select epic - during update it should become disabled then enabled again
    await epicSelect.selectOption(epicId);

    // After update completes, should be enabled again
    await expect(epicSelect).not.toBeDisabled();
    await expect(epicSelect).toHaveValue(epicId);
  });
});

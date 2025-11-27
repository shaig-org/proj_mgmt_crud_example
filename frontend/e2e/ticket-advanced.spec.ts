import { test, expect } from '@playwright/test';
import { TEST_CONFIG } from './utils/test-config';

test.describe('Ticket Advanced Features', () => {
  // Configure this test suite to run serially so beforeAll works correctly
  test.describe.configure({ mode: 'serial' });

  let projectId: string;
  let username: string;
  let password: string;

  // Use beforeAll to create shared test data once
  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();

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
    username = `pm${timestamp}`;

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
    password = userData.generated_password;

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
    await page.locator('#project-name').fill(projectName);
    await page.locator('#project-description').fill('Test project description');
    await page.getByRole('button', { name: 'Create Project' }).click();

    // Wait for modal to close and project to appear
    await expect(page.getByRole('heading', { name: 'Create New Project' })).not.toBeVisible();
    await expect(page.getByText(projectName)).toBeVisible();

    // Extract project ID from the link
    const projectLink = page.locator('.project-link').filter({ hasText: projectName });
    const href = await projectLink.getAttribute('href');
    projectId = href?.split('/').pop() || '';

    await page.close();
  });

  // Before each test, login and navigate to the project
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.getByRole('textbox', { name: 'Username' }).fill(username);
    await page.getByRole('textbox', { name: 'Password' }).fill(password);
    await page.getByRole('button', { name: 'Login' }).click();
    await expect(page).toHaveURL('/projects');

    // Navigate to project details
    await page.goto(`/projects/${projectId}`);
    await expect(page).toHaveURL(`/projects/${projectId}`);
  });

  test('can assign ticket to user when creating', async ({ page }) => {
    // Click New Ticket button
    await page.getByRole('button', { name: 'New Ticket' }).click();

    // Create ticket with assignee
    const ticketTitle = `Assigned Ticket ${Date.now()}`;
    await page.locator('#ticket-title').fill(ticketTitle);
    await page.locator('#ticket-description').fill('This ticket is assigned');
    // Select the option containing "PM User"
    const options = await page.locator('#ticket-assignee option').allTextContents();
    const pmUserOption = options.find(opt => opt.includes('PM User'));
    if (pmUserOption) {
      await page.locator('#ticket-assignee').selectOption({ label: pmUserOption });
    }

    await page.getByRole('button', { name: 'Create Ticket' }).click();

    // Ticket should show the assignee
    await expect(page.getByText(ticketTitle)).toBeVisible();
    const ticketRow = page.locator('tr').filter({ hasText: ticketTitle });
    await expect(ticketRow.locator('td').nth(3)).toContainText('PM User');
  });

  test('can create unassigned ticket', async ({ page }) => {
    // Create ticket without assignee
    await page.getByRole('button', { name: 'New Ticket' }).click();
    const ticketTitle = `Unassigned Ticket ${Date.now()}`;
    await page.locator('#ticket-title').fill(ticketTitle);
    await page.getByRole('button', { name: 'Create Ticket' }).click();

    // Ticket should show "Unassigned"
    await expect(page.getByText(ticketTitle)).toBeVisible();
    const ticketRow = page.locator('tr').filter({ hasText: ticketTitle });
    await expect(ticketRow.locator('td').nth(3)).toContainText('Unassigned');
  });

  test('can update ticket status in details page', async ({ page }) => {
    // Create a ticket
    await page.getByRole('button', { name: 'New Ticket' }).click();
    const ticketTitle = `Status Update Ticket ${Date.now()}`;
    await page.locator('#ticket-title').fill(ticketTitle);
    await page.getByRole('button', { name: 'Create Ticket' }).click();
    await expect(page.getByText(ticketTitle)).toBeVisible();

    // Navigate to ticket details
    await page.locator('.ticket-link').filter({ hasText: ticketTitle }).click();

    // Initial status should be TODO
    const statusSelect = page.locator('.status-select');
    await expect(statusSelect).toHaveValue('TODO');
    await expect(statusSelect).not.toBeDisabled();

    // Change status to IN_PROGRESS
    await statusSelect.selectOption('IN_PROGRESS');

    // Wait for the update to complete (select will be re-enabled and value persisted)
    await expect(statusSelect).not.toBeDisabled();
    await expect(statusSelect).toHaveValue('IN_PROGRESS');

    // Go back to project and verify status changed
    await page.getByRole('link', { name: '← Back to Project' }).click();
    const ticketRow = page.locator('tr').filter({ hasText: ticketTitle });
    await expect(ticketRow).toContainText('IN_PROGRESS');
  });

  test('can update ticket assignee in details page', async ({ page }) => {
    // Create an unassigned ticket
    await page.getByRole('button', { name: 'New Ticket' }).click();
    const ticketTitle = `Assignee Update Ticket ${Date.now()}`;
    await page.locator('#ticket-title').fill(ticketTitle);
    await page.getByRole('button', { name: 'Create Ticket' }).click();
    await expect(page.getByText(ticketTitle)).toBeVisible();

    // Navigate to ticket details
    await page.locator('.ticket-link').filter({ hasText: ticketTitle }).click();

    // Initially unassigned
    const assigneeSelect = page.locator('.assignee-select');
    await expect(assigneeSelect).toHaveValue('');
    await expect(assigneeSelect).not.toBeDisabled();

    // Assign to PM User
    const assigneeOptions = await assigneeSelect.locator('option').allTextContents();
    const pmUserAssigneeOption = assigneeOptions.find(opt => opt.includes('PM User'));
    if (pmUserAssigneeOption) {
      await assigneeSelect.selectOption({ label: pmUserAssigneeOption });
    }

    // Wait for the update to complete (select will be re-enabled)
    await expect(assigneeSelect).not.toBeDisabled();
    const selectedValue = await assigneeSelect.inputValue();
    expect(selectedValue).not.toBe('');

    // Go back to project and verify assignee changed
    await page.getByRole('link', { name: '← Back to Project' }).click();
    const ticketRow = page.locator('tr').filter({ hasText: ticketTitle });
    await expect(ticketRow).toContainText('PM User');
  });

});

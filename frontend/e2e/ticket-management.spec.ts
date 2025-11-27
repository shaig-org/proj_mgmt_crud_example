import { test, expect } from '@playwright/test';
import { TEST_CONFIG } from './utils/test-config';

test.describe('Ticket Management', () => {
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
    console.log(`Logging in as ${username} with password: ${password}`);
    await page.getByRole('textbox', { name: 'Username' }).fill(username);
    await page.getByRole('textbox', { name: 'Password' }).fill(password);
    await page.getByRole('button', { name: 'Login' }).click();

    // Check for error message or successful login
    try {
      await expect(page).toHaveURL('/projects', { timeout: 2000 });
    } catch {
      // Login failed, check for error message
      const errorMessage = await page.locator('.error-message').textContent().catch(() => 'No error message found');
      throw new Error(`Login failed. Error message: ${errorMessage}. Username: ${username}, Password: ${password}`);
    }

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

    // Navigate to project details
    await projectLink.click();
    await expect(page).toHaveURL(`/projects/${projectId}`);
  });

  test('can create a new ticket from project details page', async ({ page }) => {
    // Should see Tickets section with New Ticket button
    await expect(page.getByRole('heading', { name: 'Tickets' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'New Ticket' })).toBeVisible();

    // Should show placeholder when no tickets exist
    await expect(page.getByText('No tickets yet. Create one to get started.')).toBeVisible();

    // Click New Ticket button
    await page.getByRole('button', { name: 'New Ticket' }).click();

    // Should see create ticket modal
    await expect(page.getByRole('heading', { name: 'Create New Ticket' })).toBeVisible();

    // Fill in ticket details using more specific selectors
    const ticketTitle = `Test Ticket ${Date.now()}`;
    await page.locator('#ticket-title').fill(ticketTitle);
    await page.locator('#ticket-description').fill('Test ticket description');
    await page.locator('#ticket-priority').selectOption('MEDIUM');

    // Submit form
    await page.getByRole('button', { name: 'Create Ticket' }).click();

    // Modal should close
    await expect(page.getByRole('heading', { name: 'Create New Ticket' })).not.toBeVisible();

    // Ticket should appear in the table
    await expect(page.getByText(ticketTitle)).toBeVisible();
    await expect(page.locator('.priority-badge').filter({ hasText: 'MEDIUM' })).toBeVisible();

    // Placeholder should not be visible
    await expect(page.getByText('No tickets yet. Create one to get started.')).not.toBeVisible();
  });

  test('can create multiple tickets', async ({ page }) => {
    // Create first ticket
    await page.getByRole('button', { name: 'New Ticket' }).click();
    const ticketTitle1 = `Ticket One ${Date.now()}`;
    await page.locator('#ticket-title').fill(ticketTitle1);
    await page.locator('#ticket-priority').selectOption('LOW');
    await page.getByRole('button', { name: 'Create Ticket' }).click();
    await expect(page.getByText(ticketTitle1)).toBeVisible();

    // Create second ticket
    await page.getByRole('button', { name: 'New Ticket' }).click();
    const ticketTitle2 = `Ticket Two ${Date.now()}`;
    await page.locator('#ticket-title').fill(ticketTitle2);
    await page.locator('#ticket-description').fill('Second ticket');
    await page.locator('#ticket-priority').selectOption('CRITICAL');
    await page.getByRole('button', { name: 'Create Ticket' }).click();
    await expect(page.getByText(ticketTitle2)).toBeVisible();

    // Both tickets should be visible
    await expect(page.getByText(ticketTitle1)).toBeVisible();
    await expect(page.getByText(ticketTitle2)).toBeVisible();
    await expect(page.locator('.priority-badge').filter({ hasText: 'LOW' })).toBeVisible();
    await expect(page.locator('.priority-badge').filter({ hasText: 'CRITICAL' })).toBeVisible();
  });

  test('ticket title is required', async ({ page }) => {
    // Click New Ticket button
    await page.getByRole('button', { name: 'New Ticket' }).click();

    // Try to submit without title
    await page.getByRole('button', { name: 'Create Ticket' }).click();

    // Modal should still be visible (HTML5 validation prevents submission)
    await expect(page.getByRole('heading', { name: 'Create New Ticket' })).toBeVisible();
  });

  test('can cancel ticket creation', async ({ page }) => {
    // Click New Ticket button
    await page.getByRole('button', { name: 'New Ticket' }).click();
    await expect(page.getByRole('heading', { name: 'Create New Ticket' })).toBeVisible();

    // Fill in some data
    await page.locator('#ticket-title').fill('Test Ticket');

    // Click Cancel
    await page.getByRole('button', { name: 'Cancel' }).click();

    // Modal should close
    await expect(page.getByRole('heading', { name: 'Create New Ticket' })).not.toBeVisible();

    // No ticket should be created
    await expect(page.getByText('No tickets yet. Create one to get started.')).toBeVisible();
  });

  test('can close ticket creation modal by clicking overlay', async ({ page }) => {
    // Click New Ticket button
    await page.getByRole('button', { name: 'New Ticket' }).click();
    await expect(page.getByRole('heading', { name: 'Create New Ticket' })).toBeVisible();

    // Click on the overlay (outside the modal)
    await page.locator('.modal-overlay').click({ position: { x: 5, y: 5 } });

    // Modal should close
    await expect(page.getByRole('heading', { name: 'Create New Ticket' })).not.toBeVisible();
  });

  test('ticket priority is optional', async ({ page }) => {
    // Create ticket without priority
    await page.getByRole('button', { name: 'New Ticket' }).click();
    const ticketTitle = `Ticket No Priority ${Date.now()}`;
    await page.locator('#ticket-title').fill(ticketTitle);
    await page.locator('#ticket-description').fill('No priority');
    await page.getByRole('button', { name: 'Create Ticket' }).click();

    // Ticket should be created and show em dash for empty priority
    await expect(page.getByText(ticketTitle)).toBeVisible();

    // Check that the ticket row exists and contains the em dash
    const ticketRow = page.locator('tr').filter({ hasText: ticketTitle });
    await expect(ticketRow).toBeVisible();
    // Priority column should show em dash
    const priorityCell = ticketRow.locator('td').nth(2);
    await expect(priorityCell).toHaveText('—');
  });

  test('can navigate to ticket details by clicking ticket title', async ({ page }) => {
    // Create a ticket first
    await page.getByRole('button', { name: 'New Ticket' }).click();
    const ticketTitle = `Navigable Ticket ${Date.now()}`;
    await page.locator('#ticket-title').fill(ticketTitle);
    await page.locator('#ticket-description').fill('Test description for navigation');
    await page.locator('#ticket-priority').selectOption('HIGH');
    await page.getByRole('button', { name: 'Create Ticket' }).click();
    await expect(page.getByText(ticketTitle)).toBeVisible();

    // Click on the ticket title
    await page.locator('.ticket-link').filter({ hasText: ticketTitle }).click();

    // Should navigate to ticket details page
    await expect(page.url()).toMatch(/\/tickets\/[a-zA-Z0-9-]+$/);

    // Should see ticket title as heading
    await expect(page.getByRole('heading', { name: ticketTitle })).toBeVisible();

    // Should see ticket information
    await expect(page.getByText('Test description for navigation')).toBeVisible();
    await expect(page.locator('.priority-badge').filter({ hasText: 'HIGH' })).toBeVisible();
  });

  test('ticket details page shows all ticket information', async ({ page }) => {
    // Create a ticket
    await page.getByRole('button', { name: 'New Ticket' }).click();
    const ticketTitle = `Detailed Ticket ${Date.now()}`;
    await page.locator('#ticket-title').fill(ticketTitle);
    await page.locator('#ticket-description').fill('Comprehensive test description');
    await page.locator('#ticket-priority').selectOption('MEDIUM');
    await page.getByRole('button', { name: 'Create Ticket' }).click();
    await expect(page.getByText(ticketTitle)).toBeVisible();

    // Navigate to ticket details
    await page.locator('.ticket-link').filter({ hasText: ticketTitle }).click();

    // Should see back link
    await expect(page.getByRole('link', { name: '← Back to Project' })).toBeVisible();

    // Should see ticket title
    await expect(page.getByRole('heading', { name: ticketTitle })).toBeVisible();

    // Should see Ticket Information section
    await expect(page.getByRole('heading', { name: 'Ticket Information' })).toBeVisible();

    // Should see description
    await expect(page.getByText('Comprehensive test description')).toBeVisible();

    // Should see status select dropdown
    await expect(page.locator('.status-select')).toBeVisible();
    await expect(page.locator('.status-select')).toHaveValue('TODO');

    // Should see priority badge
    await expect(page.locator('.priority-badge').filter({ hasText: 'MEDIUM' })).toBeVisible();

    // Should see timestamps
    await expect(page.locator('dt').filter({ hasText: 'Created' })).toBeVisible();
    await expect(page.locator('dt').filter({ hasText: 'Last Updated' })).toBeVisible();
  });

  test('back link navigates to project details', async ({ page }) => {
    // Create a ticket
    await page.getByRole('button', { name: 'New Ticket' }).click();
    const ticketTitle = `Back Link Ticket ${Date.now()}`;
    await page.locator('#ticket-title').fill(ticketTitle);
    await page.getByRole('button', { name: 'Create Ticket' }).click();
    await expect(page.getByText(ticketTitle)).toBeVisible();

    // Navigate to ticket details
    await page.locator('.ticket-link').filter({ hasText: ticketTitle }).click();

    // Click back link
    await page.getByRole('link', { name: '← Back to Project' }).click();

    // Should navigate back to project details
    await expect(page).toHaveURL(`/projects/${projectId}`);
    await expect(page.getByRole('heading', { name: projectName })).toBeVisible();
  });

  test('invalid ticket ID shows error', async ({ page }) => {
    // Navigate to non-existent ticket
    await page.goto('/tickets/invalid-ticket-id-12345');

    // Should show error message (404 error from API)
    await expect(page.getByText(/Request failed with status code 404|Failed to load ticket|Ticket not found/)).toBeVisible();

    // Should see back link
    await expect(page.getByRole('link', { name: '← Back to Project' })).toBeVisible();
  });
});

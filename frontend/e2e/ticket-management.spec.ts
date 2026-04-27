import { test, expect } from '@playwright/test';
import {
  TEST_CONFIG,
  generateTestOrgName,
  generateTestProjectName,
  generateTestUserName,
} from './utils/test-config';
import { loginViaApi } from './utils/auth';

test.describe('Ticket Management', () => {
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
        name: generateTestOrgName('TicketMgmt'),
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
    projectName = generateTestProjectName('TicketMgmt');
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

    // Navigate to project details.
    await page.goto(`/projects/${projectId}`);
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

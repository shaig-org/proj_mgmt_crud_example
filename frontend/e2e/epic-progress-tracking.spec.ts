import { test, expect } from '@playwright/test';
import { TEST_CONFIG } from './utils/test-config';

/**
 * E2E tests for Epic Progress Tracking feature.
 * Tests that epics display progress based on ticket completion status.
 */
test.describe('Epic Progress Tracking', () => {
  let projectId: string;
  let username: string;
  let password: string;
  let pmToken: string;

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
    const pmLoginData = await pmLoginResponse.json();
    pmToken = pmLoginData.access_token;

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

    await page.close();
  });

  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.getByRole('textbox', { name: 'Username' }).fill(username);
    await page.getByRole('textbox', { name: 'Password' }).fill(password);
    await page.getByRole('button', { name: 'Login' }).click();
    await expect(page).toHaveURL('/projects');
  });

  /**
   * Helper function to create a fresh epic for each test.
   * This prevents epics from accumulating tickets across tests which would slow down page loads.
   */
  async function createEpic(page: { request: { post: (url: string, options: object) => Promise<{ ok: () => boolean; text: () => Promise<string>; json: () => Promise<{ id: string }> }> } }, name: string): Promise<string> {
    const epicResponse = await page.request.post(`${TEST_CONFIG.API_BASE_URL}/api/epics`, {
      headers: {
        Authorization: `Bearer ${pmToken}`,
        'Content-Type': 'application/json',
      },
      data: {
        name: `${name} ${Date.now()}`,
        description: 'Epic for testing progress tracking',
      },
    });

    if (!epicResponse.ok()) {
      const errorText = await epicResponse.text();
      throw new Error(`Failed to create epic: ${epicResponse.status()} - ${errorText}`);
    }

    const epic = await epicResponse.json();
    return epic.id;
  }

  test('epic with no tickets shows 0% progress', async ({ page }) => {
    await createEpic(page, 'No Tickets Epic');
    await page.goto(`/projects/${projectId}`);

    // Navigate to Epics section

    // Find the epic row
    const epicRow = page.locator('tbody tr').filter({ hasText: 'No Tickets Epic' });
    await expect(epicRow).toBeVisible();

    // Check progress shows 0 of 0 tickets and 0%
    await expect(epicRow.locator('.progress-text')).toContainText('0 of 0 tickets');
    await expect(epicRow.locator('.progress-percentage')).toContainText('0%');

    // Progress bar should exist (even if not visible at 0%)
    await expect(epicRow.locator('.progress-bar-container')).toBeVisible();
  });

  test('epic shows correct progress with some tickets completed', async ({ page }) => {
    const epicId = await createEpic(page, 'Some Complete Epic');
    await page.goto(`/projects/${projectId}`);

    // Create 3 tickets and assign to epic
    const ticketTitles = [
      `Progress Ticket 1 ${Date.now()}`,
      `Progress Ticket 2 ${Date.now() + 1}`,
      `Progress Ticket 3 ${Date.now() + 2}`,
    ];

    for (const title of ticketTitles) {
      await page.getByRole('button', { name: 'New Ticket' }).click();
      await page.getByLabel('Title *').fill(title);
      await page.locator('#ticket-epic').selectOption(epicId);
      await page.getByRole('button', { name: 'Create Ticket' }).click();
      await expect(page.locator('.modal-overlay')).not.toBeVisible();
    }

    // Mark first ticket as DONE
    await page.getByRole('link', { name: ticketTitles[0] }).click();
    await page.locator('.status-select').selectOption('DONE');
    await expect(page.locator('.status-select')).toHaveValue('DONE');

    // Go back to project page and check epic progress
    await page.goto(`/projects/${projectId}`);

    const epicRow = page.locator('tbody tr').filter({ hasText: 'Some Complete Epic' });

    // Should show 1 of 3 tickets completed (33%)
    await expect(epicRow.locator('.progress-text')).toContainText('1 of 3 tickets');
    await expect(epicRow.locator('.progress-percentage')).toContainText('33%');

    // Progress bar should have low color (< 30% shows red, but 33% should be medium yellow)
    const progressBar = epicRow.locator('.progress-bar');
    await expect(progressBar).toHaveClass(/progress-medium/);
  });

  test('epic shows 100% when all tickets are done', async ({ page }) => {
    const epicId = await createEpic(page, 'All Done Epic');
    await page.goto(`/projects/${projectId}`);

    // Create 2 tickets and assign to epic
    const ticketTitles = [`Done Ticket 1 ${Date.now()}`, `Done Ticket 2 ${Date.now() + 1}`];

    for (const title of ticketTitles) {
      await page.getByRole('button', { name: 'New Ticket' }).click();
      await page.getByLabel('Title *').fill(title);
      await page.locator('#ticket-epic').selectOption(epicId);
      await page.getByRole('button', { name: 'Create Ticket' }).click();
      await expect(page.locator('.modal-overlay')).not.toBeVisible();
    }

    // Mark both tickets as DONE
    for (const title of ticketTitles) {
      await page.getByRole('link', { name: title }).click();
      await page.locator('.status-select').selectOption('DONE');
      await expect(page.locator('.status-select')).toHaveValue('DONE');
      await page.goto(`/projects/${projectId}`);
    }

    // Check epic progress

    const epicRow = page.locator('tbody tr').filter({ hasText: 'All Done Epic' });

    // Should show 2 of 2 tickets completed (100%)
    await expect(epicRow.locator('.progress-text')).toContainText('2 of 2 tickets');
    await expect(epicRow.locator('.progress-percentage')).toContainText('100%');

    // Progress bar should have high color (green)
    const progressBar = epicRow.locator('.progress-bar');
    await expect(progressBar).toHaveClass(/progress-high/);
  });

  test('progress updates when ticket status changes', async ({ page }) => {
    const epicId = await createEpic(page, 'Status Change Epic');
    await page.goto(`/projects/${projectId}`);

    // Create ticket and assign to epic
    const ticketTitle = `Status Change Ticket ${Date.now()}`;
    await page.getByRole('button', { name: 'New Ticket' }).click();
    await page.getByLabel('Title *').fill(ticketTitle);
    await page.locator('#ticket-epic').selectOption(epicId);
    await page.getByRole('button', { name: 'Create Ticket' }).click();
    await expect(page.locator('.modal-overlay')).not.toBeVisible();

    // Reload page to get updated epic progress
    await page.goto(`/projects/${projectId}`);

    // Check initial progress (0% since ticket is TODO)
    let epicRow = page.locator('tbody tr').filter({ hasText: 'Status Change Epic' });
    await expect(epicRow.locator('.progress-text')).toContainText('0 of 1 tickets');
    await expect(epicRow.locator('.progress-percentage')).toContainText('0%');

    // Change ticket to DONE
    await page.getByRole('link', { name: ticketTitle }).click();
    await page.locator('.status-select').selectOption('DONE');
    await expect(page.locator('.status-select')).toHaveValue('DONE');

    // Go back and verify progress updated to 100%
    await page.goto(`/projects/${projectId}`);
    epicRow = page.locator('tbody tr').filter({ hasText: 'Status Change Epic' });
    await expect(epicRow.locator('.progress-text')).toContainText('1 of 1 tickets');
    await expect(epicRow.locator('.progress-percentage')).toContainText('100%');

    // Change back to IN_PROGRESS
    await page.getByRole('link', { name: ticketTitle }).click();
    await page.locator('.status-select').selectOption('IN_PROGRESS');
    await expect(page.locator('.status-select')).toHaveValue('IN_PROGRESS');

    // Verify progress back to 0%
    await page.goto(`/projects/${projectId}`);
    epicRow = page.locator('tbody tr').filter({ hasText: 'Status Change Epic' });
    await expect(epicRow.locator('.progress-text')).toContainText('0 of 1 tickets');
    await expect(epicRow.locator('.progress-percentage')).toContainText('0%');
  });

  test('progress updates when ticket is added to epic', async ({ page }) => {
    const epicId = await createEpic(page, 'Add Ticket Epic');
    await page.goto(`/projects/${projectId}`);

    // Check initial epic progress
    let epicRow = page.locator('tbody tr').filter({ hasText: 'Add Ticket Epic' });
    const initialProgressText = await epicRow.locator('.progress-text').textContent();

    // Create ticket WITHOUT epic initially
    const ticketTitle = `Add To Epic ${Date.now()}`;
    await page.getByRole('button', { name: 'New Ticket' }).click();
    await page.getByLabel('Title *').fill(ticketTitle);
    // Don't select epic
    await page.getByRole('button', { name: 'Create Ticket' }).click();
    await expect(page.locator('.modal-overlay')).not.toBeVisible();

    // Now assign ticket to epic
    await page.getByRole('link', { name: ticketTitle }).click();
    await page.locator('.epic-select').selectOption(epicId);
    await expect(page.locator('.epic-select')).toHaveValue(epicId);

    // Go back to project and verify progress updated
    await page.goto(`/projects/${projectId}`);
    epicRow = page.locator('tbody tr').filter({ hasText: 'Add Ticket Epic' });
    const newProgressText = await epicRow.locator('.progress-text').textContent();

    // Progress text should show one more ticket
    expect(newProgressText).not.toBe(initialProgressText);
    expect(newProgressText).toContain('of');
    expect(newProgressText).toContain('tickets');
  });

  test('progress updates when ticket is removed from epic', async ({ page }) => {
    const epicId = await createEpic(page, 'Remove Ticket Epic');
    await page.goto(`/projects/${projectId}`);

    // Create ticket with epic
    const ticketTitle = `Remove From Epic ${Date.now()}`;
    await page.getByRole('button', { name: 'New Ticket' }).click();
    await page.getByLabel('Title *').fill(ticketTitle);
    await page.locator('#ticket-epic').selectOption(epicId);
    await page.getByRole('button', { name: 'Create Ticket' }).click();
    await expect(page.locator('.modal-overlay')).not.toBeVisible();

    // Reload page to get updated epic progress
    await page.goto(`/projects/${projectId}`);

    // Check progress with ticket
    let epicRow = page.locator('tbody tr').filter({ hasText: 'Remove Ticket Epic' });
    const progressWithTicket = await epicRow.locator('.progress-text').textContent();

    // Remove ticket from epic
    await page.getByRole('link', { name: ticketTitle }).click();
    await page.locator('.epic-select').selectOption('');
    await expect(page.locator('.epic-select')).toHaveValue('');

    // Verify progress updated (should have one less ticket)
    await page.goto(`/projects/${projectId}`);
    epicRow = page.locator('tbody tr').filter({ hasText: 'Remove Ticket Epic' });
    const progressWithoutTicket = await epicRow.locator('.progress-text').textContent();

    // Progress text should be different
    expect(progressWithoutTicket).not.toBe(progressWithTicket);
  });

  test('progress bar color changes based on completion percentage', async ({ page }) => {
    const epicId = await createEpic(page, 'Color Progress Epic');
    await page.goto(`/projects/${projectId}`);

    // Create 10 tickets for granular percentage control
    const ticketTitles: string[] = [];
    for (let i = 0; i < 10; i++) {
      ticketTitles.push(`Color Test Ticket ${i} ${Date.now()}`);
    }

    for (const title of ticketTitles) {
      await page.getByRole('button', { name: 'New Ticket' }).click();
      await page.getByLabel('Title *').fill(title);
      await page.locator('#ticket-epic').selectOption(epicId);
      await page.getByRole('button', { name: 'Create Ticket' }).click();
      await expect(page.locator('.modal-overlay')).not.toBeVisible();
    }

    // Check initial state: 0% should show low color (red)
    let epicRow = page.locator('tbody tr').filter({ hasText: 'Color Progress Epic' });
    let progressBar = epicRow.locator('.progress-bar');
    await expect(progressBar).toHaveClass(/progress-low/);

    // Mark 2 tickets as DONE (20% - should be low/red)
    for (let i = 0; i < 2; i++) {
      await page.getByRole('link', { name: ticketTitles[i] }).click();
      await page.locator('.status-select').selectOption('DONE');
      await expect(page.locator('.status-select')).toHaveValue('DONE');
      await page.goto(`/projects/${projectId}`);
    }

    epicRow = page.locator('tbody tr').filter({ hasText: 'Color Progress Epic' });
    progressBar = epicRow.locator('.progress-bar');
    await expect(progressBar).toHaveClass(/progress-low/);

    // Mark 3 more tickets as DONE (50% total - should be medium/yellow)
    for (let i = 2; i < 5; i++) {
      await page.getByRole('link', { name: ticketTitles[i] }).click();
      await page.locator('.status-select').selectOption('DONE');
      await expect(page.locator('.status-select')).toHaveValue('DONE');
      await page.goto(`/projects/${projectId}`);
    }

    epicRow = page.locator('tbody tr').filter({ hasText: 'Color Progress Epic' });
    progressBar = epicRow.locator('.progress-bar');
    await expect(progressBar).toHaveClass(/progress-medium/);

    // Mark 3 more tickets as DONE (80% total - should be high/green)
    for (let i = 5; i < 8; i++) {
      await page.getByRole('link', { name: ticketTitles[i] }).click();
      await page.locator('.status-select').selectOption('DONE');
      await expect(page.locator('.status-select')).toHaveValue('DONE');
      await page.goto(`/projects/${projectId}`);
    }

    epicRow = page.locator('tbody tr').filter({ hasText: 'Color Progress Epic' });
    progressBar = epicRow.locator('.progress-bar');
    await expect(progressBar).toHaveClass(/progress-high/);
  });

  test('progress persists after page reload', async ({ page }) => {
    const epicId = await createEpic(page, 'Persist Epic');
    await page.goto(`/projects/${projectId}`);

    // Create ticket with epic and mark as done
    const ticketTitle = `Persist Test ${Date.now()}`;
    await page.getByRole('button', { name: 'New Ticket' }).click();
    await page.getByLabel('Title *').fill(ticketTitle);
    await page.locator('#ticket-epic').selectOption(epicId);
    await page.getByRole('button', { name: 'Create Ticket' }).click();
    await expect(page.locator('.modal-overlay')).not.toBeVisible();

    await page.getByRole('link', { name: ticketTitle }).click();
    await page.locator('.status-select').selectOption('DONE');
    await expect(page.locator('.status-select')).toHaveValue('DONE');

    // Check progress
    await page.goto(`/projects/${projectId}`);
    const epicRow = page.locator('tbody tr').filter({ hasText: 'Persist Epic' });
    const progressTextBefore = await epicRow.locator('.progress-text').textContent();
    const progressPercentageBefore = await epicRow.locator('.progress-percentage').textContent();

    // Reload page
    await page.reload();

    // Navigate back to Epics section

    // Verify progress is still the same
    const epicRowAfter = page.locator('tbody tr').filter({ hasText: 'Persist Epic' });
    await expect(epicRowAfter.locator('.progress-text')).toContainText(progressTextBefore || '');
    await expect(epicRowAfter.locator('.progress-percentage')).toContainText(
      progressPercentageBefore || ''
    );
  });
});

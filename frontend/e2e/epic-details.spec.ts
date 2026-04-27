import { test, expect } from '@playwright/test';
import {
  TEST_CONFIG,
  generateTestOrgName,
  generateTestProjectName,
  generateTestUserName,
} from './utils/test-config';
import { loginViaApi } from './utils/auth';

test.describe('Epic Details Page', () => {
  let projectId: string;
  let epicId: string;
  let pmUsername: string;
  let pmPassword: string;
  let pmToken: string;

  test.beforeAll(async ({ browser }) => {
    // Setup: Create org, user, project, and epic for all tests
    const page = await browser.newPage();

    // Login as admin to get token
    await page.goto('/login');
    await page.getByRole('textbox', { name: 'Username' }).fill('admin');
    await page.getByRole('textbox', { name: 'Password' }).fill('SuperAdmin123!');
    await page.getByRole('button', { name: 'Login' }).click();
    await expect(page).toHaveURL('/projects');

    // Get admin API token
    const adminLoginResponse = await page.request.post(`${TEST_CONFIG.API_BASE_URL}/auth/login`, {
      headers: { 'Content-Type': 'application/json' },
      data: { username: 'admin', password: 'SuperAdmin123!' },
    });
    const { access_token: adminToken } = await adminLoginResponse.json();

    // Create organization via API
    const orgResponse = await page.request.post(`${TEST_CONFIG.API_BASE_URL}/api/organizations`, {
      headers: {
        Authorization: `Bearer ${adminToken}`,
        'Content-Type': 'application/json',
      },
      data: {
        name: generateTestOrgName('EpicDetails'),
        description: 'Epic Details Test Org',
      },
    });
    const org = await orgResponse.json();
    const organizationId = org.id;

    // Create project manager user
    pmUsername = generateTestUserName('pm');
    const userResponse = await page.request.post(
      `${TEST_CONFIG.API_BASE_URL}/api/users?organization_id=${organizationId}&role=project_manager`,
      {
        headers: {
          Authorization: `Bearer ${adminToken}`,
          'Content-Type': 'application/json',
        },
        data: {
          username: pmUsername,
          email: `${pmUsername}@test.com`,
          full_name: 'Epic Test PM',
        },
      }
    );

    if (!userResponse.ok()) {
      const errorText = await userResponse.text();
      throw new Error(`Failed to create user: ${userResponse.status()} - ${errorText}`);
    }

    const userData = await userResponse.json();
    pmPassword = userData.generated_password;

    if (!pmPassword) {
      throw new Error(`No generated password in response: ${JSON.stringify(userData)}`);
    }

    // Get token for the PM user
    const pmLoginResponse = await page.request.post(`${TEST_CONFIG.API_BASE_URL}/auth/login`, {
      headers: { 'Content-Type': 'application/json' },
      data: { username: pmUsername, password: pmPassword },
    });
    const pmLoginData = await pmLoginResponse.json();
    pmToken = pmLoginData.access_token;

    // Create project via API as the PM user
    const projectResponse = await page.request.post(`${TEST_CONFIG.API_BASE_URL}/api/projects`, {
      headers: {
        Authorization: `Bearer ${pmToken}`,
        'Content-Type': 'application/json',
      },
      data: {
        name: generateTestProjectName('EpicDetails'),
        description: 'Epic Details Test Project',
      },
    });

    if (!projectResponse.ok()) {
      const errorText = await projectResponse.text();
      throw new Error(`Failed to create project: ${projectResponse.status()} - ${errorText}`);
    }

    const project = await projectResponse.json();
    projectId = project.id;

    // Create epic via API
    const epicResponse = await page.request.post(`${TEST_CONFIG.API_BASE_URL}/api/epics`, {
      headers: {
        Authorization: `Bearer ${pmToken}`,
        'Content-Type': 'application/json',
      },
      data: {
        name: 'Epic Details Test Epic',
        description: 'Test epic for epic details page',
      },
    });

    if (!epicResponse.ok()) {
      const errorText = await epicResponse.text();
      throw new Error(`Failed to create epic: ${epicResponse.status()} - ${errorText}`);
    }

    const epic = await epicResponse.json();
    epicId = epic.id;

    await page.close();
  });

  test.beforeEach(async ({ page }) => {
    // Seed auth state via API (one bcrypt per worker, cached) — no UI login.
    await loginViaApi(page, pmUsername, pmPassword);
    await page.goto('/projects');
  });

  test('can navigate to epic details from project page', async ({ page }) => {
    await page.goto(`/projects/${projectId}`);

    // Click on epic name to navigate to epic details
    await page.getByRole('link', { name: 'Epic Details Test Epic' }).click();

    // Should navigate to epic details page
    await expect(page).toHaveURL(`/epics/${epicId}`);
    await expect(page.getByRole('heading', { name: 'Epic Details Test Epic' })).toBeVisible();
  });

  test('displays all epic information correctly', async ({ page }) => {
    await page.goto(`/epics/${epicId}`);

    // Check epic name
    await expect(page.getByRole('heading', { name: 'Epic Details Test Epic' })).toBeVisible();

    // Check epic description
    await expect(page.getByText('Test epic for epic details page')).toBeVisible();

    // Check progress bar container exists
    await expect(page.locator('.progress-bar-container')).toBeVisible();
  });

  test('shows 0% progress when epic has no tickets', async ({ page }) => {
    // Create a dedicated epic for this test — the shared beforeAll epic gets
    // tickets added to it by other tests in the same worker, so we can't rely
    // on it being empty.
    const ownEpicResponse = await page.request.post(`${TEST_CONFIG.API_BASE_URL}/api/epics`, {
      headers: { Authorization: `Bearer ${pmToken}`, 'Content-Type': 'application/json' },
      data: { name: `Empty Epic ${Date.now()}-${Math.random().toString(36).slice(2, 8)}` },
    });
    if (!ownEpicResponse.ok()) {
      throw new Error(`Failed to create epic: ${ownEpicResponse.status()} - ${await ownEpicResponse.text()}`);
    }
    const ownEpic = await ownEpicResponse.json();

    await page.goto(`/epics/${ownEpic.id}`);

    // Check progress shows 0 of 0
    await expect(page.locator('.progress-text')).toContainText('0 of 0 tickets');
    await expect(page.locator('.progress-percentage')).toContainText('0%');

    // Check progress bar
    const progressBar = page.locator('.progress-bar');
    await expect(progressBar).toHaveClass(/progress-low/);
    await expect(progressBar).toHaveAttribute('style', /width:\s*0%/);
  });

  test('displays tickets section initially empty', async ({ page }) => {
    // Create a dedicated epic — shared beforeAll epic gets tickets added by
    // sibling tests, so we can't rely on its emptiness. Avoid the word
    // "Tickets" in the name so the page's "Tickets" h2 stays unambiguous.
    const ownEpicResponse = await page.request.post(`${TEST_CONFIG.API_BASE_URL}/api/epics`, {
      headers: { Authorization: `Bearer ${pmToken}`, 'Content-Type': 'application/json' },
      data: { name: `Empty Story Epic ${Date.now()}-${Math.random().toString(36).slice(2, 8)}` },
    });
    if (!ownEpicResponse.ok()) {
      throw new Error(`Failed to create epic: ${ownEpicResponse.status()} - ${await ownEpicResponse.text()}`);
    }
    const ownEpic = await ownEpicResponse.json();

    await page.goto(`/epics/${ownEpic.id}`);

    // Check tickets section header
    await expect(page.getByRole('heading', { name: /Tickets/ })).toBeVisible();

    // Should show 0 tickets initially
    await expect(page.getByText('No tickets in this epic yet')).toBeVisible();
  });

  test('back link navigates to projects list', async ({ page }) => {
    await page.goto(`/epics/${epicId}`);

    // Click back link
    await page.getByRole('link', { name: '← Back to Projects' }).click();

    // Should navigate to projects page
    await expect(page).toHaveURL('/projects');
    await expect(page.getByRole('heading', { name: 'Projects' })).toBeVisible();
  });

  test('shows tickets and allows filtering by status', async ({ page }) => {
    // Create tickets with different statuses through UI
    await page.goto(`/projects/${projectId}`);

    // Create TODO ticket
    await page.getByRole('button', { name: 'New Ticket' }).click();
    const todoTitle = `Epic TODO ${Date.now()}`;
    await page.getByLabel('Title *').fill(todoTitle);
    await page.locator('#ticket-epic').selectOption(epicId);
    await page.getByRole('button', { name: 'Create Ticket' }).click();
    await expect(page.locator('.modal-overlay')).not.toBeVisible();

    // Create IN_PROGRESS ticket
    await page.getByRole('button', { name: 'New Ticket' }).click();
    const inProgressTitle = `Epic IN_PROGRESS ${Date.now()}`;
    await page.getByLabel('Title *').fill(inProgressTitle);
    await page.locator('#ticket-epic').selectOption(epicId);
    await page.getByRole('button', { name: 'Create Ticket' }).click();
    await expect(page.locator('.modal-overlay')).not.toBeVisible();

    // Update second ticket to IN_PROGRESS
    await page.getByRole('link', { name: inProgressTitle }).click();
    await page.locator('.status-select').selectOption('IN_PROGRESS');
    await expect(page.locator('.status-select')).toHaveValue('IN_PROGRESS');

    // Navigate to epic details
    await page.goto(`/epics/${epicId}`);

    // Should show both tickets
    await expect(page.getByRole('link', { name: todoTitle })).toBeVisible();
    await expect(page.getByRole('link', { name: inProgressTitle })).toBeVisible();

    // Filter by TODO
    await page.locator('#status-filter').selectOption('TODO');
    await expect(page.getByRole('link', { name: todoTitle })).toBeVisible();
    await expect(page.getByRole('link', { name: inProgressTitle })).not.toBeVisible();

    // Filter by IN_PROGRESS
    await page.locator('#status-filter').selectOption('IN_PROGRESS');
    await expect(page.getByRole('link', { name: inProgressTitle })).toBeVisible();
    await expect(page.getByRole('link', { name: todoTitle })).not.toBeVisible();

    // Clear filter
    await page.locator('#status-filter').selectOption('');
    await expect(page.getByRole('link', { name: todoTitle })).toBeVisible();
    await expect(page.getByRole('link', { name: inProgressTitle })).toBeVisible();
  });

  test('allows sorting tickets by different criteria', async ({ page }) => {
    // Create a dedicated epic so the sort assertions don't get confused by
    // tickets that other tests on the same worker added to the shared epic.
    const ownEpicResponse = await page.request.post(`${TEST_CONFIG.API_BASE_URL}/api/epics`, {
      headers: { Authorization: `Bearer ${pmToken}`, 'Content-Type': 'application/json' },
      data: { name: `Sort Epic ${Date.now()}-${Math.random().toString(36).slice(2, 8)}` },
    });
    if (!ownEpicResponse.ok()) {
      throw new Error(`Failed to create epic: ${ownEpicResponse.status()} - ${await ownEpicResponse.text()}`);
    }
    const ownEpic = await ownEpicResponse.json();

    // Create tickets with different names through UI
    await page.goto(`/projects/${projectId}`);

    // Unique suffix per ticket title (not just Date.now() — that resolves at
    // load time, not at click time, so both literals would share the same
    // millisecond and we'd have title collisions across parallel workers).
    const suffix = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const ticketZ = `Z Epic Ticket ${suffix}`;
    await page.getByRole('button', { name: 'New Ticket' }).click();
    await page.getByLabel('Title *').fill(ticketZ);
    await page.locator('#ticket-epic').selectOption(ownEpic.id);
    await page.getByRole('button', { name: 'Create Ticket' }).click();
    await expect(page.locator('.modal-overlay')).not.toBeVisible();

    const ticketA = `A Epic Ticket ${suffix}`;
    await page.getByRole('button', { name: 'New Ticket' }).click();
    await page.getByLabel('Title *').fill(ticketA);
    await page.locator('#ticket-epic').selectOption(ownEpic.id);
    await page.getByRole('button', { name: 'Create Ticket' }).click();
    await expect(page.locator('.modal-overlay')).not.toBeVisible();

    // Navigate to epic details
    await page.goto(`/epics/${ownEpic.id}`);

    // Sort by title
    await page.locator('#sort-by').selectOption('title');
    const titleOrder = await page.locator('tbody tr td:first-child a').allTextContents();

    // Find indices of our test tickets
    const indexA = titleOrder.findIndex(t => t.includes(`A Epic Ticket ${suffix}`));
    const indexZ = titleOrder.findIndex(t => t.includes(`Z Epic Ticket ${suffix}`));

    // A should come before Z when sorted alphabetically
    expect(indexA).toBeLessThan(indexZ);

    // Sort by created_at — assert relative order (A more recent than Z)
    // rather than absolute "first", which is robust if the dedicated epic
    // somehow ends up with extra tickets later.
    await page.locator('#sort-by').selectOption('created_at');
    const createdOrder = await page.locator('tbody tr td:first-child a').allTextContents();
    const createdIndexA = createdOrder.findIndex(t => t.includes(`A Epic Ticket ${suffix}`));
    const createdIndexZ = createdOrder.findIndex(t => t.includes(`Z Epic Ticket ${suffix}`));
    expect(createdIndexA).toBeLessThan(createdIndexZ);
  });

  test('can click ticket to navigate to details', async ({ page }) => {
    // Create a ticket through UI
    await page.goto(`/projects/${projectId}`);
    const ticketTitle = `Navigate Ticket ${Date.now()}`;
    await page.getByRole('button', { name: 'New Ticket' }).click();
    await page.getByLabel('Title *').fill(ticketTitle);
    await page.locator('#ticket-epic').selectOption(epicId);
    await page.getByRole('button', { name: 'Create Ticket' }).click();
    await expect(page.locator('.modal-overlay')).not.toBeVisible();

    // Navigate to epic details
    await page.goto(`/epics/${epicId}`);

    // Click on the ticket
    await page.getByRole('link', { name: ticketTitle }).click();

    // Should navigate to ticket details page
    await expect(page).toHaveURL(/\/tickets\/.+/);
    await expect(page.getByRole('heading', { name: ticketTitle })).toBeVisible();
  });

  test('shows progress calculation with completed tickets', async ({ page }) => {
    // Create tickets with mixed statuses through UI
    await page.goto(`/projects/${projectId}`);

    // Create TODO ticket
    await page.getByRole('button', { name: 'New Ticket' }).click();
    await page.getByLabel('Title *').fill(`Progress TODO ${Date.now()}`);
    await page.locator('#ticket-epic').selectOption(epicId);
    await page.getByRole('button', { name: 'Create Ticket' }).click();
    await expect(page.locator('.modal-overlay')).not.toBeVisible();

    // Create DONE ticket
    await page.getByRole('button', { name: 'New Ticket' }).click();
    const doneTitle = `Progress DONE ${Date.now()}`;
    await page.getByLabel('Title *').fill(doneTitle);
    await page.locator('#ticket-epic').selectOption(epicId);
    await page.getByRole('button', { name: 'Create Ticket' }).click();
    await expect(page.locator('.modal-overlay')).not.toBeVisible();

    // Mark second ticket as DONE
    await page.getByRole('link', { name: doneTitle }).click();
    await page.locator('.status-select').selectOption('DONE');
    await expect(page.locator('.status-select')).toHaveValue('DONE');

    // Navigate to epic details
    await page.goto(`/epics/${epicId}`);

    // Should show progress (at least 1 ticket completed out of multiple)
    const progressText = await page.locator('.progress-text').textContent();
    expect(progressText).toMatch(/\d+ of \d+ tickets/);

    // Progress percentage should be > 0% but < 100%
    const progressPercentage = await page.locator('.progress-percentage').textContent();
    const percentage = parseInt(progressPercentage?.replace('%', '') || '0');
    expect(percentage).toBeGreaterThan(0);
    expect(percentage).toBeLessThan(100);
  });
});

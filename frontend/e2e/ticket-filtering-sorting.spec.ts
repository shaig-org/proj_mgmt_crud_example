import { test, expect } from '@playwright/test';
import { TEST_CONFIG } from './utils/test-config';

/**
 * Dedicated test suite for filtering and sorting tickets.
 * Uses its own project with controlled test data for reliable assertions.
 */
test.describe('Ticket Filtering and Sorting', () => {
  // Configure this test suite to run serially so beforeAll works correctly
  test.describe.configure({ mode: 'serial' });

  let projectId: string;
  let username: string;
  let password: string;
  const testPrefix = `FS${Date.now()}`;

  // Ticket names for our test data
  const tickets = {
    criticalTodo: `${testPrefix}-A-CRITICAL`,
    highTodo: `${testPrefix}-B-HIGH`,
    mediumInProgress: `${testPrefix}-C-MEDIUM`,
    lowDone: `${testPrefix}-D-LOW`,
  };

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();

    // Setup: Login as super admin and create test fixtures via API
    // (This is acceptable - we're setting up test environment, not testing these features)
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

    // Create organization
    const orgResponse = await page.request.post(`${TEST_CONFIG.API_BASE_URL}/api/organizations`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { name: `Filter Test Org ${Date.now()}`, description: 'For filtering tests' },
    });

    if (!orgResponse.ok()) {
      const errorText = await orgResponse.text();
      throw new Error(`Failed to create organization: ${orgResponse.status()} - ${errorText}`);
    }

    const org = await orgResponse.json();

    // Create project manager user
    const timestamp = Date.now();
    username = `pmfilter${timestamp}`;
    const userResponse = await page.request.post(
      `${TEST_CONFIG.API_BASE_URL}/api/users?organization_id=${org.id}&role=project_manager`,
      {
        headers: { Authorization: `Bearer ${token}` },
        data: {
          username,
          email: `${username}@example.com`,
          full_name: 'Filter Test PM',
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

    // Logout admin and login as PM
    await page.getByRole('button', { name: 'Logout' }).click();
    await page.getByRole('textbox', { name: 'Username' }).fill(username);
    await page.getByRole('textbox', { name: 'Password' }).fill(password);
    await page.getByRole('button', { name: 'Login' }).click();
    await expect(page).toHaveURL('/projects');

    // Create project
    await page.getByRole('button', { name: 'New Project' }).click();
    const projectName = `Filter Test Project ${Date.now()}`;
    await page.locator('#project-name').fill(projectName);
    await page.getByRole('button', { name: 'Create Project' }).click();
    await expect(page.getByRole('heading', { name: 'Create New Project' })).not.toBeVisible();
    await expect(page.getByText(projectName)).toBeVisible();

    const projectLink = page.locator('.project-link').filter({ hasText: projectName });
    const href = await projectLink.getAttribute('href');
    projectId = href?.split('/').pop() || '';

    // Navigate to project
    await projectLink.click();
    await expect(page).toHaveURL(`/projects/${projectId}`);

    // Create all test tickets via UI (this is what we're testing - the ticket management UI)
    // Ticket 1: CRITICAL priority, TODO status
    await page.getByRole('button', { name: 'New Ticket' }).click();
    await page.locator('#ticket-title').fill(tickets.criticalTodo);
    await page.locator('#ticket-priority').selectOption('CRITICAL');
    await page.getByRole('button', { name: 'Create Ticket' }).click();
    await expect(page.getByText(tickets.criticalTodo)).toBeVisible();

    // Ticket 2: HIGH priority, TODO status
    await page.getByRole('button', { name: 'New Ticket' }).click();
    await page.locator('#ticket-title').fill(tickets.highTodo);
    await page.locator('#ticket-priority').selectOption('HIGH');
    await page.getByRole('button', { name: 'Create Ticket' }).click();
    await expect(page.getByText(tickets.highTodo)).toBeVisible();

    // Ticket 3: MEDIUM priority, IN_PROGRESS status
    await page.getByRole('button', { name: 'New Ticket' }).click();
    await page.locator('#ticket-title').fill(tickets.mediumInProgress);
    await page.locator('#ticket-priority').selectOption('MEDIUM');
    await page.getByRole('button', { name: 'Create Ticket' }).click();
    await expect(page.getByText(tickets.mediumInProgress)).toBeVisible();

    // Change to IN_PROGRESS
    await page.locator('.ticket-link').filter({ hasText: tickets.mediumInProgress }).click();
    await page.locator('.status-select').selectOption('IN_PROGRESS');
    await expect(page.locator('.status-select')).toHaveValue('IN_PROGRESS');
    await page.getByRole('link', { name: '← Back to Project' }).click();

    // Ticket 4: LOW priority, DONE status
    await page.getByRole('button', { name: 'New Ticket' }).click();
    await page.locator('#ticket-title').fill(tickets.lowDone);
    await page.locator('#ticket-priority').selectOption('LOW');
    await page.getByRole('button', { name: 'Create Ticket' }).click();
    await expect(page.getByText(tickets.lowDone)).toBeVisible();

    // Change to DONE
    await page.locator('.ticket-link').filter({ hasText: tickets.lowDone }).click();
    await page.locator('.status-select').selectOption('DONE');
    await expect(page.locator('.status-select')).toHaveValue('DONE');
    await page.getByRole('link', { name: '← Back to Project' }).click();

    await page.close();
  });

  test.beforeEach(async ({ page }) => {
    // Login and navigate to project before each test
    await page.goto('/login');
    await page.getByRole('textbox', { name: 'Username' }).fill(username);
    await page.getByRole('textbox', { name: 'Password' }).fill(password);
    await page.getByRole('button', { name: 'Login' }).click();
    await expect(page).toHaveURL('/projects');
    await page.goto(`/projects/${projectId}`);
  });

  test('can filter tickets by status', async ({ page }) => {
    // Filter by TODO - should see CRITICAL and HIGH
    await page.locator('#filter-status').selectOption('TODO');
    await expect(page.getByText(tickets.criticalTodo)).toBeVisible();
    await expect(page.getByText(tickets.highTodo)).toBeVisible();
    await expect(page.getByText(tickets.mediumInProgress)).not.toBeVisible();
    await expect(page.getByText(tickets.lowDone)).not.toBeVisible();

    // Filter by IN_PROGRESS - should see MEDIUM
    await page.locator('#filter-status').selectOption('IN_PROGRESS');
    await expect(page.getByText(tickets.mediumInProgress)).toBeVisible();
    await expect(page.getByText(tickets.criticalTodo)).not.toBeVisible();
    await expect(page.getByText(tickets.highTodo)).not.toBeVisible();
    await expect(page.getByText(tickets.lowDone)).not.toBeVisible();

    // Filter by DONE - should see LOW
    await page.locator('#filter-status').selectOption('DONE');
    await expect(page.getByText(tickets.lowDone)).toBeVisible();
    await expect(page.getByText(tickets.criticalTodo)).not.toBeVisible();
    await expect(page.getByText(tickets.highTodo)).not.toBeVisible();
    await expect(page.getByText(tickets.mediumInProgress)).not.toBeVisible();
  });

  test('can filter tickets by priority', async ({ page }) => {
    // Filter by CRITICAL
    await page.locator('#filter-priority').selectOption('CRITICAL');
    await expect(page.getByText(tickets.criticalTodo)).toBeVisible();
    await expect(page.getByText(tickets.highTodo)).not.toBeVisible();
    await expect(page.getByText(tickets.mediumInProgress)).not.toBeVisible();
    await expect(page.getByText(tickets.lowDone)).not.toBeVisible();

    // Filter by HIGH
    await page.locator('#filter-priority').selectOption('HIGH');
    await expect(page.getByText(tickets.highTodo)).toBeVisible();
    await expect(page.getByText(tickets.criticalTodo)).not.toBeVisible();

    // Filter by MEDIUM
    await page.locator('#filter-priority').selectOption('MEDIUM');
    await expect(page.getByText(tickets.mediumInProgress)).toBeVisible();
    await expect(page.getByText(tickets.highTodo)).not.toBeVisible();

    // Filter by LOW
    await page.locator('#filter-priority').selectOption('LOW');
    await expect(page.getByText(tickets.lowDone)).toBeVisible();
    await expect(page.getByText(tickets.mediumInProgress)).not.toBeVisible();
  });

  test('can sort tickets by priority', async ({ page }) => {
    // Sort by priority
    await page.locator('#sort-by').selectOption('priority');

    // Wait for all 4 ticket links to be present and stable
    await expect(page.locator('.ticket-link')).toHaveCount(4);

    // Wait for sorting to take effect by checking the first ticket is the CRITICAL one
    await expect(page.locator('.ticket-link').first()).toContainText(tickets.criticalTodo);

    const ticketLinks = await page.locator('.ticket-link').allTextContents();

    // Find indices of our test tickets (use includes since text content may have extra whitespace)
    const indices = {
      critical: ticketLinks.findIndex(t => t.includes(tickets.criticalTodo)),
      high: ticketLinks.findIndex(t => t.includes(tickets.highTodo)),
      medium: ticketLinks.findIndex(t => t.includes(tickets.mediumInProgress)),
      low: ticketLinks.findIndex(t => t.includes(tickets.lowDone)),
    };

    // Debug: If any ticket not found, show what we got
    if (indices.critical < 0 || indices.high < 0 || indices.medium < 0 || indices.low < 0) {
      throw new Error(
        `Tickets not found in list. Looking for: ${JSON.stringify(tickets)}\n` +
        `Found in page: ${JSON.stringify(ticketLinks)}\n` +
        `Indices: ${JSON.stringify(indices)}`
      );
    }

    // Verify sort order: CRITICAL < HIGH < MEDIUM < LOW
    expect(indices.critical).toBeLessThan(indices.high);
    expect(indices.high).toBeLessThan(indices.medium);
    expect(indices.medium).toBeLessThan(indices.low);
  });

  test('can sort tickets by title', async ({ page }) => {
    // First, verify all our test tickets are visible before sorting
    await expect(page.getByText(tickets.criticalTodo)).toBeVisible();
    await expect(page.getByText(tickets.highTodo)).toBeVisible();
    await expect(page.getByText(tickets.mediumInProgress)).toBeVisible();
    await expect(page.getByText(tickets.lowDone)).toBeVisible();

    // Sort by title (alphabetical)
    await page.locator('#sort-by').selectOption('title');

    // Wait for all 4 ticket links to be present and stable
    await expect(page.locator('.ticket-link')).toHaveCount(4);

    // Wait for sorting to take effect by checking the first ticket is the A-CRITICAL one
    await expect(page.locator('.ticket-link').first()).toContainText(tickets.criticalTodo);

    const ticketLinks = await page.locator('.ticket-link').allTextContents();

    // Find indices of our test tickets (use includes since text content may have extra whitespace)
    const indices = {
      a: ticketLinks.findIndex(t => t.includes(tickets.criticalTodo)), // A-CRITICAL
      b: ticketLinks.findIndex(t => t.includes(tickets.highTodo)),     // B-HIGH
      c: ticketLinks.findIndex(t => t.includes(tickets.mediumInProgress)), // C-MEDIUM
      d: ticketLinks.findIndex(t => t.includes(tickets.lowDone)),      // D-LOW
    };

    // Debug: If any ticket not found, show what we got
    if (indices.a < 0 || indices.b < 0 || indices.c < 0 || indices.d < 0) {
      throw new Error(
        `Tickets not found in list. Looking for: ${JSON.stringify(tickets)}\n` +
        `Found in page: ${JSON.stringify(ticketLinks)}\n` +
        `Indices: ${JSON.stringify(indices)}`
      );
    }

    // Verify alphabetical order: A < B < C < D
    expect(indices.a).toBeLessThan(indices.b);
    expect(indices.b).toBeLessThan(indices.c);
    expect(indices.c).toBeLessThan(indices.d);
  });

  test('can combine status and priority filters', async ({ page }) => {
    // Filter by TODO status and HIGH priority
    await page.locator('#filter-status').selectOption('TODO');
    await page.locator('#filter-priority').selectOption('HIGH');

    // Should only see HIGH TODO ticket
    await expect(page.getByText(tickets.highTodo)).toBeVisible();
    await expect(page.getByText(tickets.criticalTodo)).not.toBeVisible(); // TODO but CRITICAL
    await expect(page.getByText(tickets.mediumInProgress)).not.toBeVisible(); // MEDIUM and IN_PROGRESS
    await expect(page.getByText(tickets.lowDone)).not.toBeVisible(); // LOW and DONE
  });
});

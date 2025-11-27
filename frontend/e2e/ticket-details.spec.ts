import { test, expect } from '@playwright/test';
import { TEST_CONFIG } from './utils/test-config';

/**
 * E2E tests for the Ticket Details page and comment system.
 */
test.describe('Ticket Details and Comments', () => {
  let ticketId: string;
  let ticketTitle: string;
  let projectId: string;
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

    // Create ticket via API as PM user
    ticketTitle = `Test Ticket ${Date.now()}`;
    const ticketResponse = await page.request.post(
      `${TEST_CONFIG.API_BASE_URL}/api/tickets?project_id=${projectId}`,
      {
        headers: {
          Authorization: `Bearer ${pmToken}`,
          'Content-Type': 'application/json',
        },
        data: {
          title: ticketTitle,
          description: 'This is a test ticket for E2E testing',
          priority: 'HIGH',
        },
      }
    );

    if (!ticketResponse.ok()) {
      const errorText = await ticketResponse.text();
      throw new Error(`Failed to create ticket: ${ticketResponse.status()} - ${errorText}`);
    }

    const ticket = await ticketResponse.json();
    ticketId = ticket.id;

    await page.close();
  });

  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.getByRole('textbox', { name: 'Username' }).fill(username);
    await page.getByRole('textbox', { name: 'Password' }).fill(password);
    await page.getByRole('button', { name: 'Login' }).click();
    await expect(page).toHaveURL('/projects');
  });

  test('displays all ticket information', async ({ page }) => {
    await page.goto(`/tickets/${ticketId}`);

    // Check title
    await expect(page.getByRole('heading', { name: ticketTitle })).toBeVisible();

    // Check description
    await expect(page.getByText('This is a test ticket for E2E testing')).toBeVisible();

    // Check status dropdown exists
    await expect(page.locator('.status-select')).toBeVisible();

    // Check priority badge
    await expect(page.locator('.priority-badge')).toContainText('HIGH');

    // Check timestamps exist (looking for the dt elements with these labels)
    await expect(page.locator('dt').filter({ hasText: 'Created' })).toBeVisible();
    await expect(page.locator('dt').filter({ hasText: 'Last Updated' })).toBeVisible();

    // Check back link
    await expect(page.locator('.back-link')).toBeVisible();
  });

  test('can update ticket status', async ({ page }) => {
    await page.goto(`/tickets/${ticketId}`);

    // Change status to IN_PROGRESS
    await page.locator('.status-select').selectOption('IN_PROGRESS');

    // Wait for update to complete (page should still be on same URL)
    await expect(page).toHaveURL(`/tickets/${ticketId}`);

    // Verify status changed
    await expect(page.locator('.status-select')).toHaveValue('IN_PROGRESS');

    // Change back to TODO
    await page.locator('.status-select').selectOption('TODO');
    await expect(page.locator('.status-select')).toHaveValue('TODO');
  });

  test('can update ticket assignee', async ({ page }) => {
    await page.goto(`/tickets/${ticketId}`);

    // Check assignee dropdown exists
    await expect(page.locator('.assignee-select')).toBeVisible();

    // Initially should be unassigned
    await expect(page.locator('.assignee-select')).toHaveValue('');

    // Get all options from the dropdown
    const allOptions = await page.locator('.assignee-select option').all();

    // Filter out the "Unassigned" option (value="") to find user options
    const userOptions = [];
    for (const option of allOptions) {
      const value = await option.getAttribute('value');
      if (value && value !== '') {
        userOptions.push(value);
      }
    }

    if (userOptions.length > 0) {
      const firstUserValue = userOptions[0];

      // Assign to the first available user
      await page.locator('.assignee-select').selectOption(firstUserValue);
      await expect(page.locator('.assignee-select')).toHaveValue(firstUserValue);

      // Unassign
      await page.locator('.assignee-select').selectOption('');
      await expect(page.locator('.assignee-select')).toHaveValue('');
    }
  });

  test('shows empty comments section initially', async ({ page }) => {
    await page.goto(`/tickets/${ticketId}`);

    // Check comments heading shows count of 0
    await expect(page.getByRole('heading', { name: 'Comments (0)' })).toBeVisible();

    // Check "no comments" message
    await expect(page.locator('.no-comments')).toBeVisible();
    await expect(page.locator('.no-comments')).toContainText('No comments yet');

    // Check add comment form is visible
    await expect(page.getByRole('heading', { name: 'Add Comment' })).toBeVisible();
    await expect(page.locator('.comment-input')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Add Comment' })).toBeVisible();
  });

  test('can add a comment', async ({ page }) => {
    await page.goto(`/tickets/${ticketId}`);

    const commentText = `Test comment ${Date.now()}`;

    // Fill in comment
    await page.locator('.comment-input').fill(commentText);

    // Submit button should be enabled
    await expect(page.getByRole('button', { name: 'Add Comment' })).toBeEnabled();

    // Submit comment
    await page.getByRole('button', { name: 'Add Comment' }).click();

    // Wait for comment to appear
    await expect(page.locator('.comment')).toBeVisible();
    await expect(page.locator('.comment-content')).toContainText(commentText);

    // Comment input should be cleared
    await expect(page.locator('.comment-input')).toHaveValue('');

    // Comments count should update
    await expect(page.getByRole('heading', { name: 'Comments (1)' })).toBeVisible();

    // Comment should show author (the PM user who is logged in)
    await expect(page.locator('.comment-author')).toBeVisible();
    await expect(page.locator('.comment-author')).toContainText(username);

    // Comment should show timestamp
    await expect(page.locator('.comment-timestamp')).toBeVisible();
  });

  test('can add multiple comments', async ({ page }) => {
    await page.goto(`/tickets/${ticketId}`);

    // Wait for comments section to load (either comments or "no comments" message)
    await page.waitForSelector('.comments-section h2');

    // Get initial comment count
    const initialCount = await page.locator('.comment').count();

    // Add first comment
    const comment1 = `Comment 1 ${Date.now()}`;
    await page.locator('.comment-input').fill(comment1);
    await page.getByRole('button', { name: 'Add Comment' }).click();
    await expect(page.locator('.comment-content').filter({ hasText: comment1 })).toBeVisible();

    // Add second comment
    const comment2 = `Comment 2 ${Date.now()}`;
    await page.locator('.comment-input').fill(comment2);
    await page.getByRole('button', { name: 'Add Comment' }).click();
    await expect(page.locator('.comment-content').filter({ hasText: comment2 })).toBeVisible();

    // Both new comments should be visible
    await expect(page.locator('.comment')).toHaveCount(initialCount + 2);

    // Comments count should update to show the new total
    const expectedCount = initialCount + 2;
    await expect(page.getByRole('heading', { name: `Comments (${expectedCount})` })).toBeVisible();
  });

  test('cannot submit empty comment', async ({ page }) => {
    await page.goto(`/tickets/${ticketId}`);

    // Submit button should be disabled initially
    await expect(page.getByRole('button', { name: 'Add Comment' })).toBeDisabled();

    // Type and then delete comment text
    await page.locator('.comment-input').fill('test');
    await expect(page.getByRole('button', { name: 'Add Comment' })).toBeEnabled();

    await page.locator('.comment-input').clear();
    await expect(page.getByRole('button', { name: 'Add Comment' })).toBeDisabled();

    // Submit button disabled for whitespace-only input
    await page.locator('.comment-input').fill('   ');
    await expect(page.getByRole('button', { name: 'Add Comment' })).toBeDisabled();
  });

  test('can delete a comment', async ({ page }) => {
    await page.goto(`/tickets/${ticketId}`);

    // Add a comment first
    const commentText = `Comment to delete ${Date.now()}`;
    await page.locator('.comment-input').fill(commentText);
    await page.getByRole('button', { name: 'Add Comment' }).click();
    await expect(page.locator('.comment-content').filter({ hasText: commentText })).toBeVisible();

    // Get initial comment count
    const initialCount = await page.locator('.comment').count();

    // Set up dialog handler to confirm deletion
    page.on('dialog', dialog => dialog.accept());

    // Click delete button
    await page.locator('.delete-comment-btn').first().click();

    // Comment should be removed
    await expect(page.locator('.comment')).toHaveCount(initialCount - 1);

    // If this was the last comment, should show "no comments" message
    if (initialCount === 1) {
      await expect(page.locator('.no-comments')).toBeVisible();
      await expect(page.getByRole('heading', { name: 'Comments (0)' })).toBeVisible();
    }
  });

  test('can cancel comment deletion', async ({ page }) => {
    await page.goto(`/tickets/${ticketId}`);

    // Add a comment first
    const commentText = `Comment to keep ${Date.now()}`;
    await page.locator('.comment-input').fill(commentText);
    await page.getByRole('button', { name: 'Add Comment' }).click();
    await expect(page.locator('.comment-content').filter({ hasText: commentText })).toBeVisible();

    // Get initial comment count
    const initialCount = await page.locator('.comment').count();

    // Set up dialog handler to CANCEL deletion
    page.on('dialog', dialog => dialog.dismiss());

    // Click delete button
    await page.locator('.delete-comment-btn').first().click();

    // Comment should still be there
    await expect(page.locator('.comment')).toHaveCount(initialCount);
    await expect(page.locator('.comment-content').filter({ hasText: commentText })).toBeVisible();
  });

  test('back link navigates to project details', async ({ page }) => {
    await page.goto(`/tickets/${ticketId}`);

    await page.locator('.back-link').click();
    await expect(page).toHaveURL(`/projects/${projectId}`);
  });

  test('invalid ticket ID shows error', async ({ page }) => {
    await page.goto('/tickets/invalid-ticket-id-12345');

    await expect(page.locator('.error-message')).toBeVisible();
    await expect(page.locator('.back-link')).toBeVisible();
  });

  test('comments persist after page reload', async ({ page }) => {
    await page.goto(`/tickets/${ticketId}`);

    // Add a unique comment
    const commentText = `Persistent comment ${Date.now()}`;
    await page.locator('.comment-input').fill(commentText);
    await page.getByRole('button', { name: 'Add Comment' }).click();
    await expect(page.locator('.comment-content').filter({ hasText: commentText })).toBeVisible();

    // Reload page
    await page.reload();

    // Comment should still be visible
    await expect(page.locator('.comment-content').filter({ hasText: commentText })).toBeVisible();
  });

  test('status changes persist after page reload', async ({ page }) => {
    await page.goto(`/tickets/${ticketId}`);

    // Change status to DONE
    await page.locator('.status-select').selectOption('DONE');
    await expect(page.locator('.status-select')).toHaveValue('DONE');

    // Reload page
    await page.reload();

    // Status should still be DONE
    await expect(page.locator('.status-select')).toHaveValue('DONE');

    // Change back to TODO for other tests
    await page.locator('.status-select').selectOption('TODO');
  });
});

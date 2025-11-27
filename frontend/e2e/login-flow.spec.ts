import { test, expect } from '@playwright/test';

test.describe('Login and Projects Flow', () => {
  test('super admin can login and view projects', async ({ page }) => {
    // Navigate to the app (should redirect to login)
    await page.goto('/');
    await expect(page).toHaveURL('/login');

    // Verify login page elements
    await expect(page.getByRole('heading', { name: 'Project Management System' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Login' })).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Username' })).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Password' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Login' })).toBeVisible();

    // Fill in login form
    await page.getByRole('textbox', { name: 'Username' }).fill('admin');
    await page.getByRole('textbox', { name: 'Password' }).fill('SuperAdmin123!');

    // Submit the form
    await page.getByRole('button', { name: 'Login' }).click();

    // Verify redirect to projects page
    await expect(page).toHaveURL('/projects');

    // Verify projects page header
    await expect(page.getByRole('heading', { name: 'Projects' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Logout' })).toBeVisible();

    // Verify projects page content loaded (either table or "no projects" message)
    // The backend may or may not have projects, so we check for either state
    // Wait for either the table or the "no projects" message to appear
    try {
      await expect(page.getByRole('table')).toBeVisible({ timeout: 3000 });
    } catch {
      // If no table, check for "no projects" message
      await expect(page.getByText('No projects found')).toBeVisible();
    }
  });

  test('logout redirects to login page', async ({ page }) => {
    // Navigate and login
    await page.goto('/login');
    await page.getByRole('textbox', { name: 'Username' }).fill('admin');
    await page.getByRole('textbox', { name: 'Password' }).fill('SuperAdmin123!');
    await page.getByRole('button', { name: 'Login' }).click();

    // Wait for projects page
    await expect(page).toHaveURL('/projects');

    // Click logout
    await page.getByRole('button', { name: 'Logout' }).click();

    // Verify redirect to login
    await expect(page).toHaveURL('/login');
    await expect(page.getByRole('heading', { name: 'Login' })).toBeVisible();
  });

  test('protected route redirects to login when not authenticated', async ({ page }) => {
    // Try to access projects page directly without logging in
    await page.goto('/projects');

    // Should redirect to login
    await expect(page).toHaveURL('/login');
    await expect(page.getByRole('heading', { name: 'Login' })).toBeVisible();
  });
});

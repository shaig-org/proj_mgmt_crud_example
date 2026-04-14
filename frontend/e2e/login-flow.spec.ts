import { test, expect } from '@playwright/test';

test.describe('Login and Projects Flow', () => {
  // Happy-path login is covered by login-happy-path.scenario.spec.ts.

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

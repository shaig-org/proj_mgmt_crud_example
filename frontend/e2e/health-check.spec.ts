import { test, expect } from '@playwright/test';

test.describe('Health Check', () => {
  test('should load the application and redirect to login', async ({ page }) => {
    await page.goto('/');

    // Should redirect to login page
    await expect(page).toHaveURL('/login');

    // Check for the main heading
    await expect(page.getByRole('heading', { name: 'Project Management System' })).toBeVisible();

    // Check for login heading
    await expect(page.getByRole('heading', { name: 'Login' })).toBeVisible();
  });

  test('should display login form elements', async ({ page }) => {
    await page.goto('/login');

    // Check for form elements
    await expect(page.getByRole('textbox', { name: 'Username' })).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Password' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Login' })).toBeVisible();
  });

  test('should be able to navigate to login page', async ({ page }) => {
    await page.goto('/login');

    // Check that we're on the login page
    await expect(page).toHaveURL('/login');
    await expect(page.getByRole('heading', { name: 'Login' })).toBeVisible();
  });
});

import { test, expect } from '@playwright/test';
import { loginViaApi } from './utils/auth';

test.describe('Navigation', () => {
  test.beforeEach(async ({ page }) => {
    // Seed auth state via API (one bcrypt per worker, cached) — no UI login.
    await loginViaApi(page, 'admin', 'SuperAdmin123!');
    await page.goto('/projects');
  });

  test('should display navigation bar with brand', async ({ page }) => {
    // Should see sidebar navigation
    const sidebar = page.locator('.sidebar');
    await expect(sidebar).toBeVisible();

    // Should see brand/title
    await expect(sidebar.getByRole('heading', { name: 'Project Hub' })).toBeVisible();
  });

  test('should display user info and logout button', async ({ page }) => {
    const sidebar = page.locator('.sidebar');

    // Should see user info (username displayed separately from role)
    await expect(sidebar.getByText('admin', { exact: true })).toBeVisible();
    await expect(sidebar.getByText('super admin', { exact: true })).toBeVisible();

    // Should see logout button
    await expect(sidebar.getByRole('button', { name: 'Logout' })).toBeVisible();
  });

  test('should show all navigation links for super admin', async ({ page }) => {
    const sidebar = page.locator('.sidebar');

    // Should see all three links for super admin
    await expect(sidebar.getByRole('link', { name: 'Projects' })).toBeVisible();
    await expect(sidebar.getByRole('link', { name: 'Users' })).toBeVisible();
    await expect(sidebar.getByRole('link', { name: 'Organizations' })).toBeVisible();
  });

  test('Projects link should be active on projects page', async ({ page }) => {
    const projectsLink = page.locator('.sidebar').getByRole('link', { name: 'Projects' });

    // Projects link should have active class
    await expect(projectsLink).toHaveClass(/active/);
  });

  test('can navigate to users page via navigation', async ({ page }) => {
    // Click Users link in navigation
    await page.locator('.sidebar').getByRole('link', { name: 'Users' }).click();

    // Should navigate to users page
    await expect(page).toHaveURL('/users');

    // Users link should now be active
    const usersLink = page.locator('.sidebar').getByRole('link', { name: 'Users' });
    await expect(usersLink).toHaveClass(/active/);

    // Projects link should no longer be active
    const projectsLink = page.locator('.sidebar').getByRole('link', { name: 'Projects' });
    await expect(projectsLink).not.toHaveClass(/active/);
  });

  test('can navigate back to projects via navigation', async ({ page }) => {
    // Go to users page first
    await page.locator('.sidebar').getByRole('link', { name: 'Users' }).click();
    await expect(page).toHaveURL('/users');

    // Navigate back to projects
    await page.locator('.sidebar').getByRole('link', { name: 'Projects' }).click();
    await expect(page).toHaveURL('/projects');

    // Projects link should be active again
    const projectsLink = page.locator('.sidebar').getByRole('link', { name: 'Projects' });
    await expect(projectsLink).toHaveClass(/active/);
  });

  test('logout button should work from navigation', async ({ page }) => {
    // Click logout in navigation
    await page.locator('.sidebar').getByRole('button', { name: 'Logout' }).click();

    // Should redirect to login page
    await expect(page).toHaveURL('/login');

    // Should no longer see sidebar navigation
    await expect(page.locator('.sidebar')).not.toBeVisible();
  });
});

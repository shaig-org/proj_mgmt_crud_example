import { test, expect } from '@playwright/test';

test.describe('Navigation', () => {
  test.beforeEach(async ({ page }) => {
    // Login as super admin
    await page.goto('/login');
    await page.getByRole('textbox', { name: 'Username' }).fill('admin');
    await page.getByRole('textbox', { name: 'Password' }).fill('SuperAdmin123!');
    await page.getByRole('button', { name: 'Login' }).click();
    await expect(page).toHaveURL('/projects');
  });

  test('should display navigation bar with brand', async ({ page }) => {
    // Should see navigation bar
    const nav = page.locator('.main-navigation');
    await expect(nav).toBeVisible();

    // Should see brand/title
    await expect(nav.getByRole('heading', { name: 'Project Management' })).toBeVisible();
  });

  test('should display user info and logout button', async ({ page }) => {
    const nav = page.locator('.main-navigation');

    // Should see user info
    await expect(nav.getByText('admin (super_admin)')).toBeVisible();

    // Should see logout button
    await expect(nav.getByRole('button', { name: 'Logout' })).toBeVisible();
  });

  test('should show all navigation links for super admin', async ({ page }) => {
    const nav = page.locator('.main-navigation');

    // Should see all three links for super admin
    await expect(nav.getByRole('link', { name: 'Projects' })).toBeVisible();
    await expect(nav.getByRole('link', { name: 'Users' })).toBeVisible();
    await expect(nav.getByRole('link', { name: 'Organizations' })).toBeVisible();
  });

  test('Projects link should be active on projects page', async ({ page }) => {
    const projectsLink = page.locator('.main-navigation').getByRole('link', { name: 'Projects' });

    // Projects link should have active class
    await expect(projectsLink).toHaveClass(/active/);
  });

  test('can navigate to users page via navigation', async ({ page }) => {
    // Click Users link in navigation
    await page.locator('.main-navigation').getByRole('link', { name: 'Users' }).click();

    // Should navigate to users page
    await expect(page).toHaveURL('/users');

    // Users link should now be active
    const usersLink = page.locator('.main-navigation').getByRole('link', { name: 'Users' });
    await expect(usersLink).toHaveClass(/active/);

    // Projects link should no longer be active
    const projectsLink = page.locator('.main-navigation').getByRole('link', { name: 'Projects' });
    await expect(projectsLink).not.toHaveClass(/active/);
  });

  test('can navigate back to projects via navigation', async ({ page }) => {
    // Go to users page first
    await page.locator('.main-navigation').getByRole('link', { name: 'Users' }).click();
    await expect(page).toHaveURL('/users');

    // Navigate back to projects
    await page.locator('.main-navigation').getByRole('link', { name: 'Projects' }).click();
    await expect(page).toHaveURL('/projects');

    // Projects link should be active again
    const projectsLink = page.locator('.main-navigation').getByRole('link', { name: 'Projects' });
    await expect(projectsLink).toHaveClass(/active/);
  });

  test('logout button should work from navigation', async ({ page }) => {
    // Click logout in navigation
    await page.locator('.main-navigation').getByRole('button', { name: 'Logout' }).click();

    // Should redirect to login page
    await expect(page).toHaveURL('/login');

    // Should no longer see navigation
    await expect(page.locator('.main-navigation')).not.toBeVisible();
  });
});

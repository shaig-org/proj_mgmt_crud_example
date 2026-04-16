/**
 * Scenario: super-admin auth round trip. Unauthed visit bounces to /login,
 * credentials log in, protected routes work, then logout returns to /login
 * and protected routes bounce back again.
 *
 * Replaces login-happy-path and logout.
 */

import { expect } from '@playwright/test';
import { scenarioTest } from '../../helpers/scenario';

scenarioTest('Super admin auth round trip', async ({ page, step }) => {
  await step('unauthed visit bounces to login', async () => {
    await page.goto('/projects');
    await expect(page).toHaveURL('/login');
    await expect(page.getByRole('heading', { name: 'Login' })).toBeVisible();
  });

  await step('fill in super admin credentials', async () => {
    await page.getByRole('textbox', { name: 'Username' }).fill('admin');
    await page.getByRole('textbox', { name: 'Password' }).fill('SuperAdmin123!');
    await expect(page.getByRole('textbox', { name: 'Username' })).toHaveValue('admin');
  });

  // Merged the prior `submit the login form` and `confirm authed chrome is
  // visible` steps: both landed on /projects with no visual change between
  // them, so the second frame was a duplicate of the first.
  await step('submit the login form and land on projects with authed chrome', async () => {
    await page.getByRole('button', { name: 'Login' }).click();
    await expect(page).toHaveURL('/projects');
    await expect(page.getByRole('heading', { name: 'Projects' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Organizations' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Logout' })).toBeVisible();
  });

  // Merged the prior `click logout` and `protected route bounces back` steps
  // since both landed on /login with no visible difference between frames.
  await step('logout returns to login and protected routes bounce back too', async () => {
    await page.getByRole('button', { name: 'Logout' }).click();
    await expect(page).toHaveURL('/login');
    await expect(page.getByRole('heading', { name: 'Login' })).toBeVisible();
    await page.goto('/projects');
    await expect(page).toHaveURL('/login');
    await expect(page.getByRole('textbox', { name: 'Username' })).toBeVisible();
  });
});

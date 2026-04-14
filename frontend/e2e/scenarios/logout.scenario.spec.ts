/**
 * Scenario: a logged-in super admin clicks the sidebar Logout icon and is
 * redirected back to the login page.
 */

import { expect } from '@playwright/test';
import { scenarioTest } from '../helpers/scenario';

scenarioTest('Logout returns user to login page', async ({ page, step }) => {
  await step('login as super admin', async () => {
    await page.goto('/login');
    await page.getByRole('textbox', { name: 'Username' }).fill('admin');
    await page.getByRole('textbox', { name: 'Password' }).fill('SuperAdmin123!');
    await page.getByRole('button', { name: 'Login' }).click();
    await expect(page).toHaveURL('/projects');
  });

  await step('confirm logged-in chrome is visible', async () => {
    await expect(page.getByRole('heading', { name: 'Projects' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Logout' })).toBeVisible();
  });

  await step('click the logout button', async () => {
    await page.getByRole('button', { name: 'Logout' }).click();
    await expect(page).toHaveURL('/login');
  });

  await step('see login page again', async () => {
    await expect(page.getByRole('heading', { name: 'Login' })).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Username' })).toBeVisible();
  });

  await step('protected route bounces back to login', async () => {
    await page.goto('/projects');
    await expect(page).toHaveURL('/login');
  });
});

/**
 * Scenario: super-admin logs in from the login page and lands on the
 * projects list. Covers the protected-route redirect and auth-state
 * transition in one tour.
 */

import { expect } from '@playwright/test';
import { scenarioTest } from '../helpers/scenario';

scenarioTest('Super admin login happy path', async ({ page, step }) => {
  await step('open the app and land on login', async () => {
    await page.goto('/');
    await expect(page).toHaveURL('/login');
    await expect(page.getByRole('heading', { name: 'Login' })).toBeVisible();
  });

  await step('fill in super admin credentials', async () => {
    await page.getByRole('textbox', { name: 'Username' }).fill('admin');
    await page.getByRole('textbox', { name: 'Password' }).fill('SuperAdmin123!');
    await expect(page.getByRole('textbox', { name: 'Username' })).toHaveValue('admin');
  });

  await step('submit the login form', async () => {
    await page.getByRole('button', { name: 'Login' }).click();
    await expect(page).toHaveURL('/projects');
  });

  await step('see the projects page with sidebar', async () => {
    await expect(page.getByRole('heading', { name: 'Projects' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Projects' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Organizations' })).toBeVisible();
  });
});

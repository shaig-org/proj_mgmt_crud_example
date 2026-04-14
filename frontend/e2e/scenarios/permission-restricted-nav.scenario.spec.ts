/**
 * Scenario: a PM logs in and sees only the Projects sidebar link — the
 * Users and Organizations entries are hidden for non-admin roles.
 */

import { expect } from '@playwright/test';
import { scenarioTest } from '../helpers/scenario';
import { createOrgAndPM, loginViaUI, type PMContext } from '../helpers/fixtures';

let pm: PMContext;

scenarioTest.beforeAll(async ({ request }) => {
  pm = await createOrgAndPM(request, 'NavPerms');
});

scenarioTest('PM sees a restricted sidebar without Users or Organizations', async ({ page, step }) => {
  await step('open the login page', async () => {
    await page.goto('/login');
    await expect(page.getByRole('heading', { name: 'Login' })).toBeVisible();
  });

  await step('login as PM', async () => {
    await loginViaUI(page, pm.username, pm.password);
    await expect(page).toHaveURL('/projects');
  });

  await step('confirm Projects link IS shown in the sidebar', async () => {
    const sidebar = page.locator('.sidebar');
    await expect(sidebar.getByRole('link', { name: 'Projects' })).toBeVisible();
  });

  await step('confirm Users link is NOT present', async () => {
    const sidebar = page.locator('.sidebar');
    await expect(sidebar.getByRole('link', { name: 'Users' })).toHaveCount(0);
  });

  await step('confirm Organizations link is NOT present', async () => {
    const sidebar = page.locator('.sidebar');
    await expect(sidebar.getByRole('link', { name: 'Organizations' })).toHaveCount(0);
  });

  await step('user chip in the footer shows the PM role', async () => {
    await expect(page.locator('.user-role')).toHaveText(/project manager/i);
  });
});

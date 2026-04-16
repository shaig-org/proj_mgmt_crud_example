/**
 * Scenario: a PM logs in and sees only the Projects sidebar link — the
 * Users and Organizations entries are hidden for non-admin roles.
 */

import { expect } from '@playwright/test';
import { scenarioTest } from '../../helpers/scenario';
import { createOrgAndPM, loginViaUI, type PMContext } from '../../helpers/fixtures';

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

  // Merged the prior three sidebar-assertion steps (Projects shown, Users
  // hidden, Organizations hidden). Each landed on the same /projects view
  // with no DOM mutation, so screenshots were identical to the login frame.
  // Hovering the Projects link gives the merged frame a distinct visual cue.
  await step('confirm sidebar shows only Projects (no Users, no Organizations)', async () => {
    const sidebar = page.locator('.sidebar');
    await sidebar.getByRole('link', { name: 'Projects' }).hover();
    await expect(sidebar.getByRole('link', { name: 'Projects' })).toBeVisible();
    await expect(sidebar.getByRole('link', { name: 'Users' })).toHaveCount(0);
    await expect(sidebar.getByRole('link', { name: 'Organizations' })).toHaveCount(0);
  });

  await step('user chip in the footer shows the PM role', async () => {
    // Hover the user chip so the footer area is the visible focus of this
    // frame and it doesn't blend into the prior sidebar-focused screenshot.
    await page.locator('.user-role').hover();
    await expect(page.locator('.user-role')).toHaveText(/project manager/i);
  });
});

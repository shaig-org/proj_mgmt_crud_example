/**
 * Scenario: a PM with multiple projects already provisioned opens the
 * Projects page and sees them all listed in the table.
 */

import { expect } from '@playwright/test';
import { scenarioTest } from '../helpers/scenario';
import { createOrgAndPM, createProjectForPM, loginViaUI, type PMContext } from '../helpers/fixtures';

interface Ctx {
  pm: PMContext;
  projectNames: string[];
}

let ctx: Ctx;

scenarioTest.beforeAll(async ({ request }) => {
  const pm = await createOrgAndPM(request, 'Overview');
  const p1 = await createProjectForPM(request, pm, 'Alpha');
  const p2 = await createProjectForPM(request, pm, 'Beta');
  const p3 = await createProjectForPM(request, pm, 'Gamma');
  ctx = { pm, projectNames: [p1.projectName, p2.projectName, p3.projectName] };
});

scenarioTest('PM sees all projects in the overview list', async ({ page, step }) => {
  await step('open the login page', async () => {
    await page.goto('/login');
    await expect(page.getByRole('heading', { name: 'Login' })).toBeVisible();
  });

  await step('submit PM credentials', async () => {
    await loginViaUI(page, ctx.pm.username, ctx.pm.password);
    await expect(page).toHaveURL('/projects');
  });

  await step('see the Projects heading and list', async () => {
    await expect(page.getByRole('heading', { name: 'Projects' })).toBeVisible();
    await expect(page.locator('.projects-table')).toBeVisible();
  });

  await step('confirm every seeded project appears in the list', async () => {
    for (const name of ctx.projectNames) {
      await expect(page.getByRole('link', { name })).toBeVisible();
    }
  });

  await step('open the first project link', async () => {
    await page.getByRole('link', { name: ctx.projectNames[0] }).click();
    await expect(page).toHaveURL(/\/projects\/[^/]+$/);
    await expect(page.getByRole('heading', { name: ctx.projectNames[0] })).toBeVisible();
  });
});

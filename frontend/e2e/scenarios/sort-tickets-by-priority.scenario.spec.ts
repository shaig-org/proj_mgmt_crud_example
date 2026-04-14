/**
 * Scenario: PM sorts project tickets by priority and sees the CRITICAL
 * ticket move to the top of the list.
 */

import { expect } from '@playwright/test';
import { scenarioTest } from '../helpers/scenario';
import {
  createOrgAndPM,
  createProjectForPM,
  createTicket,
  loginViaUI,
  type PMProjectContext,
} from '../helpers/fixtures';
import { generateTestTicketTitle } from '../utils/test-config';

interface Ctx {
  project: PMProjectContext;
  lowTitle: string;
  criticalTitle: string;
}

let ctx: Ctx;

scenarioTest.beforeAll(async ({ request }) => {
  const pm = await createOrgAndPM(request, 'SortPriority');
  const project = await createProjectForPM(request, pm, 'SortPriority');
  // Create LOW first so it's "older"; then CRITICAL last so it's newest.
  const low = await createTicket(request, project, {
    title: generateTestTicketTitle('LowPrio'),
    priority: 'LOW',
  });
  const critical = await createTicket(request, project, {
    title: generateTestTicketTitle('CritPrio'),
    priority: 'CRITICAL',
  });
  ctx = { project, lowTitle: low.title, criticalTitle: critical.title };
});

scenarioTest('PM sorts tickets by priority', async ({ page, step }) => {
  await step('login as PM', async () => {
    await loginViaUI(page, ctx.project.username, ctx.project.password);
    await expect(page).toHaveURL('/projects');
  });

  await step('open project details with default sort (created date)', async () => {
    await page.goto(`/projects/${ctx.project.projectId}`);
    // Default sort is created_at DESC, so the most recently created
    // (CRITICAL) is first; confirm default order.
    const rows = page.locator('.tickets-table tbody tr');
    await expect(rows.first()).toContainText(ctx.criticalTitle);
  });

  await step('switch to sort-by-title to produce a distinct order', async () => {
    await page.locator('#sort-by').selectOption('title');
    await expect(page.locator('#sort-by')).toHaveValue('title');
  });

  await step('switch sort to Priority', async () => {
    await page.locator('#sort-by').selectOption('priority');
    await expect(page.locator('#sort-by')).toHaveValue('priority');
  });

  await step('CRITICAL ticket is first, LOW is below it', async () => {
    const rows = page.locator('.tickets-table tbody tr');
    await expect(rows.first()).toContainText(ctx.criticalTitle);
    await expect(rows.nth(1)).toContainText(ctx.lowTitle);
  });
});

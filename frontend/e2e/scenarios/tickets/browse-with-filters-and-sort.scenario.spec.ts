/**
 * Scenario: PM browses a project's tickets, applies a status filter,
 * clears it, sorts by priority, and finally combines both filter + sort.
 *
 * Replaces filter-tickets-by-status and sort-tickets-by-priority.
 */

import { expect } from '@playwright/test';
import { scenarioTest } from '../../helpers/scenario';
import {
  createOrgAndPM,
  createProjectForPM,
  createTicket,
  loginViaUI,
  type PMProjectContext,
} from '../../helpers/fixtures';
import { generateTestTicketTitle } from '../../utils/test-config';

interface Ctx {
  project: PMProjectContext;
  lowTodoTitle: string;
  critTodoTitle: string;
  highDoneTitle: string;
  medDoneTitle: string;
}

let ctx: Ctx;

scenarioTest.beforeAll(async ({ request }) => {
  const pm = await createOrgAndPM(request, 'BrowseTickets');
  const project = await createProjectForPM(request, pm, 'BrowseTickets');
  // Seed four tickets with distinct status + priority combos so filter
  // and sort produce visibly different DOM states.
  const lowTodo = await createTicket(request, project, {
    title: generateTestTicketTitle('LowTodo'),
    priority: 'LOW',
  });
  const critTodo = await createTicket(request, project, {
    title: generateTestTicketTitle('CritTodo'),
    priority: 'CRITICAL',
  });
  const highDone = await createTicket(request, project, {
    title: generateTestTicketTitle('HighDone'),
    priority: 'HIGH',
    status: 'DONE',
  });
  const medDone = await createTicket(request, project, {
    title: generateTestTicketTitle('MedDone'),
    priority: 'MEDIUM',
    status: 'DONE',
  });
  ctx = {
    project,
    lowTodoTitle: lowTodo.title,
    critTodoTitle: critTodo.title,
    highDoneTitle: highDone.title,
    medDoneTitle: medDone.title,
  };
});

scenarioTest('PM browses tickets with filters and sort', async ({ page, step }) => {
  await step('login as PM', async () => {
    await loginViaUI(page, ctx.project.username, ctx.project.password);
    await expect(page).toHaveURL('/projects');
  });

  await step('open project details and see all four tickets', async () => {
    await page.goto(`/projects/${ctx.project.projectId}`);
    await expect(page.getByRole('link', { name: ctx.lowTodoTitle })).toBeVisible();
    await expect(page.getByRole('link', { name: ctx.critTodoTitle })).toBeVisible();
    await expect(page.getByRole('link', { name: ctx.highDoneTitle })).toBeVisible();
    await expect(page.getByRole('link', { name: ctx.medDoneTitle })).toBeVisible();
  });

  await step('filter to only TODO tickets', async () => {
    await page.locator('#filter-status').selectOption('TODO');
    await expect(page.getByRole('link', { name: ctx.lowTodoTitle })).toBeVisible();
    await expect(page.getByRole('link', { name: ctx.critTodoTitle })).toBeVisible();
    await expect(page.getByRole('link', { name: ctx.highDoneTitle })).not.toBeVisible();
    await expect(page.getByRole('link', { name: ctx.medDoneTitle })).not.toBeVisible();
  });

  await step('clear filter and see all tickets again', async () => {
    await page.locator('#filter-status').selectOption('');
    await expect(page.getByRole('link', { name: ctx.highDoneTitle })).toBeVisible();
    await expect(page.getByRole('link', { name: ctx.medDoneTitle })).toBeVisible();
  });

  await step('sort tickets by priority', async () => {
    await page.locator('#sort-by').selectOption('priority');
    await expect(page.locator('#sort-by')).toHaveValue('priority');
    const rows = page.locator('.tickets-table tbody tr');
    await expect(rows.first()).toContainText(ctx.critTodoTitle);
  });

  await step('verify full priority-sorted order', async () => {
    const rows = page.locator('.tickets-table tbody tr');
    await expect(rows.nth(0)).toContainText(ctx.critTodoTitle);
    await expect(rows.nth(1)).toContainText(ctx.highDoneTitle);
    await expect(rows.nth(2)).toContainText(ctx.medDoneTitle);
    await expect(rows.nth(3)).toContainText(ctx.lowTodoTitle);
  });

  await step('apply DONE filter on top of priority sort', async () => {
    await page.locator('#filter-status').selectOption('DONE');
    const rows = page.locator('.tickets-table tbody tr');
    await expect(rows).toHaveCount(2);
    await expect(rows.nth(0)).toContainText(ctx.highDoneTitle);
    await expect(rows.nth(1)).toContainText(ctx.medDoneTitle);
  });
});

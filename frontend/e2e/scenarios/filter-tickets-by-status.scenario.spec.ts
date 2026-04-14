/**
 * Scenario: PM filters project tickets by status using the Status filter
 * on the project details page. Fixture seeds one ticket in each of TODO
 * and DONE so the filter makes one visibly appear or disappear.
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
  todoTitle: string;
  doneTitle: string;
}

let ctx: Ctx;

scenarioTest.beforeAll(async ({ request }) => {
  const pm = await createOrgAndPM(request, 'FilterStatus');
  const project = await createProjectForPM(request, pm, 'FilterStatus');
  const todo = await createTicket(request, project, {
    title: generateTestTicketTitle('StillTodo'),
  });
  const done = await createTicket(request, project, {
    title: generateTestTicketTitle('AllDone'),
    status: 'DONE',
  });
  ctx = { project, todoTitle: todo.title, doneTitle: done.title };
});

scenarioTest('PM filters tickets by status', async ({ page, step }) => {
  await step('login as PM', async () => {
    await loginViaUI(page, ctx.project.username, ctx.project.password);
    await expect(page).toHaveURL('/projects');
  });

  await step('open project details page', async () => {
    await page.goto(`/projects/${ctx.project.projectId}`);
    await expect(page.getByRole('link', { name: ctx.todoTitle })).toBeVisible();
    await expect(page.getByRole('link', { name: ctx.doneTitle })).toBeVisible();
  });

  await step('filter tickets to only TODO', async () => {
    await page.locator('#filter-status').selectOption('TODO');
    await expect(page.getByRole('link', { name: ctx.todoTitle })).toBeVisible();
    await expect(page.getByRole('link', { name: ctx.doneTitle })).not.toBeVisible();
  });

  await step('switch filter to DONE', async () => {
    await page.locator('#filter-status').selectOption('DONE');
    await expect(page.getByRole('link', { name: ctx.doneTitle })).toBeVisible();
    await expect(page.getByRole('link', { name: ctx.todoTitle })).not.toBeVisible();
  });

  await step('reset the filter and see both tickets', async () => {
    await page.locator('#filter-status').selectOption('');
    await expect(page.getByRole('link', { name: ctx.todoTitle })).toBeVisible();
    await expect(page.getByRole('link', { name: ctx.doneTitle })).toBeVisible();
  });
});

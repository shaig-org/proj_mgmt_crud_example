/**
 * Scenario: PM links an existing ticket to an epic using the Epic select
 * on the ticket details page.
 */

import { expect } from '@playwright/test';
import { scenarioTest } from '../helpers/scenario';
import {
  createOrgAndPM,
  createProjectForPM,
  createEpicForProject,
  createTicket,
  loginViaUI,
  type PMProjectContext,
} from '../helpers/fixtures';
import { generateTestEpicTitle, generateTestTicketTitle } from '../utils/test-config';

interface Ctx {
  project: PMProjectContext;
  ticketId: string;
  ticketTitle: string;
  epicName: string;
}

let ctx: Ctx;

scenarioTest.beforeAll(async ({ request }) => {
  const pm = await createOrgAndPM(request, 'LinkEpic');
  const project = await createProjectForPM(request, pm, 'LinkEpic');
  const epic = await createEpicForProject(request, project, generateTestEpicTitle('Target'));
  const ticket = await createTicket(request, project, {
    title: generateTestTicketTitle('Orphan'),
  });
  ctx = {
    project,
    ticketId: ticket.id,
    ticketTitle: ticket.title,
    epicName: epic.name,
  };
});

scenarioTest('PM links an existing ticket to an epic', async ({ page, step }) => {
  await step('login as PM', async () => {
    await loginViaUI(page, ctx.project.username, ctx.project.password);
    await expect(page).toHaveURL('/projects');
  });

  await step('open the ticket details', async () => {
    await page.goto(`/tickets/${ctx.ticketId}`);
    await expect(page.getByRole('heading', { name: ctx.ticketTitle })).toBeVisible();
  });

  await step('confirm the epic select is empty', async () => {
    await expect(page.locator('.epic-select')).toHaveValue('');
  });

  await step('pick the target epic', async () => {
    await page.locator('.epic-select').selectOption({ label: ctx.epicName });
    await expect(page.locator('.epic-select')).not.toHaveValue('');
  });

  await step('verify the ticket appears on the epic page', async () => {
    await page.goto(`/projects/${ctx.project.projectId}`);
    await page.getByRole('link', { name: ctx.epicName }).click();
    await expect(page.locator('.tickets-section').getByRole('link', { name: ctx.ticketTitle })).toBeVisible();
  });
});

/**
 * Scenario: the epic progress bar moves from 0% to 100% when the PM
 * transitions the single linked ticket through TODO → IN_PROGRESS → DONE
 * on the ticket details page.
 */

import { expect } from '@playwright/test';
import { scenarioTest } from '../helpers/scenario';
import {
  createOrgAndPM,
  createProjectForPM,
  createEpicForProject,
  createTicket,
  addTicketToEpic,
  loginViaUI,
  type PMProjectContext,
} from '../helpers/fixtures';
import { generateTestEpicTitle, generateTestTicketTitle } from '../utils/test-config';

interface Ctx {
  project: PMProjectContext;
  epicId: string;
  epicName: string;
  ticketId: string;
}

let ctx: Ctx;

scenarioTest.beforeAll(async ({ request }) => {
  const pm = await createOrgAndPM(request, 'EpicProgress');
  const project = await createProjectForPM(request, pm, 'EpicProgress');
  const epic = await createEpicForProject(request, project, generateTestEpicTitle('Progress'));
  const ticket = await createTicket(request, project, {
    title: generateTestTicketTitle('ProgressT'),
    priority: 'MEDIUM',
  });
  await addTicketToEpic(request, project, epic.id, ticket.id);
  ctx = { project, epicId: epic.id, epicName: epic.name, ticketId: ticket.id };
});

scenarioTest('Epic progress bar updates as ticket moves to DONE', async ({ page, step }) => {
  await step('login as PM', async () => {
    await loginViaUI(page, ctx.project.username, ctx.project.password);
    await expect(page).toHaveURL('/projects');
  });

  await step('open the epic details page', async () => {
    await page.goto(`/epics/${ctx.epicId}`);
    await expect(page.getByRole('heading', { name: ctx.epicName })).toBeVisible();
    await expect(page.locator('.progress-percentage')).toHaveText('0%');
  });

  await step('open the linked ticket', async () => {
    await page.locator('.tickets-section').getByRole('link').first().click();
    await expect(page).toHaveURL(/\/tickets\/[^/]+$/);
    await expect(page.locator('.status-select')).toHaveValue('TODO');
  });

  await step('move the ticket to DONE', async () => {
    await page.locator('.status-select').selectOption('DONE');
    await expect(page.locator('.status-select')).toHaveValue('DONE');
  });

  await step('return to the epic and see 100% progress', async () => {
    await page.goto(`/epics/${ctx.epicId}`);
    await expect(page.locator('.progress-percentage')).toHaveText('100%');
  });
});

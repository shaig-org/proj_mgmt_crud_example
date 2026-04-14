/**
 * Scenario: PM opens an epic that has two linked tickets and sees them
 * listed on the epic details page.
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
  ticketTitles: string[];
}

let ctx: Ctx;

scenarioTest.beforeAll(async ({ request }) => {
  const pm = await createOrgAndPM(request, 'EpicTicketList');
  const project = await createProjectForPM(request, pm, 'EpicTicketList');
  const epic = await createEpicForProject(request, project, generateTestEpicTitle('Grouped'));
  const t1 = await createTicket(request, project, { title: generateTestTicketTitle('GroupedA') });
  const t2 = await createTicket(request, project, { title: generateTestTicketTitle('GroupedB') });
  await addTicketToEpic(request, project, epic.id, t1.id);
  await addTicketToEpic(request, project, epic.id, t2.id);
  ctx = {
    project,
    epicId: epic.id,
    epicName: epic.name,
    ticketTitles: [t1.title, t2.title],
  };
});

scenarioTest('PM views the tickets linked to an epic', async ({ page, step }) => {
  await step('login as PM', async () => {
    await loginViaUI(page, ctx.project.username, ctx.project.password);
    await expect(page).toHaveURL('/projects');
  });

  await step('open project details', async () => {
    await page.goto(`/projects/${ctx.project.projectId}`);
    await expect(page.getByRole('link', { name: ctx.epicName })).toBeVisible();
  });

  await step('click into the epic', async () => {
    await page.getByRole('link', { name: ctx.epicName }).click();
    await expect(page).toHaveURL(/\/epics\/[^/]+$/);
    await expect(page.getByRole('heading', { name: ctx.epicName })).toBeVisible();
  });

  await step('see both linked tickets in the epic tickets section', async () => {
    for (const t of ctx.ticketTitles) {
      await expect(page.locator('.tickets-section').getByRole('link', { name: t })).toBeVisible();
    }
  });
});

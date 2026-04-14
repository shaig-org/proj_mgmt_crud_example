/**
 * Scenario: PM opens a pre-seeded project and sees the three major
 * sections of the details page (Info, Epics, Tickets).
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
  epicName: string;
  ticketTitle: string;
}

let ctx: Ctx;

scenarioTest.beforeAll(async ({ request }) => {
  const pm = await createOrgAndPM(request, 'ViewDetails');
  const project = await createProjectForPM(request, pm, 'DetailsView');
  const epicName = generateTestEpicTitle('ViewDetailsEpic');
  await createEpicForProject(request, project, epicName);
  const ticketTitle = generateTestTicketTitle('ViewDetailsTicket');
  await createTicket(request, project, { title: ticketTitle, priority: 'HIGH' });
  ctx = { project, epicName, ticketTitle };
});

scenarioTest('PM views full project details page', async ({ page, step }) => {
  await step('login as PM', async () => {
    await loginViaUI(page, ctx.project.username, ctx.project.password);
    await expect(page).toHaveURL('/projects');
  });

  await step('click the project in the list', async () => {
    await page.getByRole('link', { name: ctx.project.projectName }).click();
    await expect(page).toHaveURL(/\/projects\/[^/]+$/);
  });

  await step('see the project information block', async () => {
    await expect(page.getByRole('heading', { name: ctx.project.projectName })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Project Information' })).toBeVisible();
  });

  await step('see the epics section with the seeded epic', async () => {
    await expect(page.getByRole('heading', { name: 'Epics', exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: ctx.epicName })).toBeVisible();
  });

  await step('see the tickets section with the seeded ticket', async () => {
    await expect(page.getByRole('heading', { name: 'Tickets', exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: ctx.ticketTitle })).toBeVisible();
  });
});

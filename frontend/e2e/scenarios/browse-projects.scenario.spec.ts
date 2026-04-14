/**
 * Scenario: PM with multiple seeded projects (and an epic+ticket inside one
 * of them) opens the Projects page, sees them all, and drills into one to
 * view its Info / Epics / Tickets sections.
 *
 * Replaces project-list-overview and view-project-details.
 */

import { expect } from '@playwright/test';
import { scenarioTest } from '../helpers/scenario';
import {
  createEpicForProject,
  createOrgAndPM,
  createProjectForPM,
  createTicket,
  loginViaUI,
  type PMContext,
  type PMProjectContext,
} from '../helpers/fixtures';
import { generateTestEpicTitle, generateTestTicketTitle } from '../utils/test-config';

interface Ctx {
  pm: PMContext;
  projects: PMProjectContext[];
  detailedProjectIndex: number;
  epicName: string;
  ticketTitle: string;
}

let ctx: Ctx;

scenarioTest.beforeAll(async ({ request }) => {
  const pm = await createOrgAndPM(request, 'BrowseProjects');
  const p1 = await createProjectForPM(request, pm, 'Alpha');
  const p2 = await createProjectForPM(request, pm, 'Beta');
  const p3 = await createProjectForPM(request, pm, 'Gamma');

  const epicName = generateTestEpicTitle('BrowseEpic');
  await createEpicForProject(request, p2, epicName);
  const ticketTitle = generateTestTicketTitle('BrowseT');
  await createTicket(request, p2, { title: ticketTitle, priority: 'HIGH' });

  ctx = {
    pm,
    projects: [p1, p2, p3],
    detailedProjectIndex: 1,
    epicName,
    ticketTitle,
  };
});

scenarioTest('PM browses projects and views one in detail', async ({ page, step }) => {
  await step('open the login page', async () => {
    await page.goto('/login');
    await expect(page.getByRole('heading', { name: 'Login' })).toBeVisible();
  });

  await step('submit PM credentials', async () => {
    await loginViaUI(page, ctx.pm.username, ctx.pm.password);
    await expect(page).toHaveURL('/projects');
  });

  await step('see the Projects heading and table', async () => {
    await expect(page.getByRole('heading', { name: 'Projects' })).toBeVisible();
    await expect(page.locator('.projects-table')).toBeVisible();
  });

  await step('confirm every seeded project is in the list', async () => {
    for (const p of ctx.projects) {
      await expect(page.getByRole('link', { name: p.projectName })).toBeVisible();
    }
  });

  await step('click into the detailed project', async () => {
    const target = ctx.projects[ctx.detailedProjectIndex];
    await page.getByRole('link', { name: target.projectName }).click();
    await expect(page).toHaveURL(/\/projects\/[^/]+$/);
    await expect(page.getByRole('heading', { name: target.projectName })).toBeVisible();
  });

  await step('see project information block', async () => {
    await expect(page.getByRole('heading', { name: 'Project Information' })).toBeVisible();
  });

  await step('see epics section with the seeded epic', async () => {
    await expect(page.getByRole('heading', { name: 'Epics', exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: ctx.epicName })).toBeVisible();
  });

  await step('see tickets section with the seeded ticket', async () => {
    await expect(page.getByRole('heading', { name: 'Tickets', exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: ctx.ticketTitle })).toBeVisible();
  });
});

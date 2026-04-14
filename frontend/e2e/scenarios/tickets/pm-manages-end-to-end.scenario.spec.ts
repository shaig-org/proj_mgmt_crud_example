/**
 * Scenario: PM creates a ticket inside a project via the UI, assigns it to
 * themself, links it to an existing epic, and advances it through the
 * default workflow (TODO → IN_PROGRESS → DONE).
 *
 * Replaces assign-ticket-to-user, link-ticket-to-epic, and
 * create-ticket-and-change-status.
 */

import { expect } from '@playwright/test';
import { scenarioTest } from '../../helpers/scenario';
import {
  createEpicForProject,
  createOrgAndPM,
  createProjectForPM,
  loginViaUI,
  type EpicRef,
  type PMProjectContext,
} from '../../helpers/fixtures';
import { generateTestEpicTitle, generateTestTicketTitle } from '../../utils/test-config';

interface Ctx {
  project: PMProjectContext;
  epic: EpicRef;
}

let ctx: Ctx;

scenarioTest.beforeAll(async ({ request }) => {
  const pm = await createOrgAndPM(request, 'PmMgmtE2E');
  const project = await createProjectForPM(request, pm, 'PmMgmtE2E');
  const epic = await createEpicForProject(request, project, generateTestEpicTitle('Launch'));
  ctx = { project, epic };
});

scenarioTest('PM manages a ticket end to end', async ({ page, step }) => {
  const ticketTitle = generateTestTicketTitle('E2EFlow');

  await step('login as PM', async () => {
    await loginViaUI(page, ctx.project.username, ctx.project.password);
    await expect(page).toHaveURL('/projects');
  });

  await step('open project details', async () => {
    await page.goto(`/projects/${ctx.project.projectId}`);
    await expect(page.getByRole('heading', { name: 'Tickets', exact: true })).toBeVisible();
  });

  await step('create a new ticket via the modal', async () => {
    await page.getByRole('button', { name: 'New Ticket' }).click();
    await expect(page.getByRole('heading', { name: 'Create New Ticket' })).toBeVisible();
    await page.locator('#ticket-title').fill(ticketTitle);
    await page.locator('#ticket-description').fill('End-to-end scenario ticket');
    await page.locator('#ticket-priority').selectOption('MEDIUM');
    await page.getByRole('button', { name: 'Create Ticket' }).click();
    await expect(page.getByRole('heading', { name: 'Create New Ticket' })).not.toBeVisible();
    await expect(page.getByRole('link', { name: ticketTitle })).toBeVisible();
  });

  await step('open the new ticket details', async () => {
    await page.getByRole('link', { name: ticketTitle }).click();
    await expect(page).toHaveURL(/\/tickets\/[a-f0-9-]+/);
    await expect(page.getByRole('heading', { name: ticketTitle })).toBeVisible();
    await expect(page.locator('.assignee-select')).toHaveValue('');
  });

  await step('assign the ticket to the PM', async () => {
    const select = page.locator('.assignee-select');
    const firstUserValue = await select.locator('option').nth(1).getAttribute('value');
    if (!firstUserValue) throw new Error('expected at least one assignable user');
    await select.selectOption(firstUserValue);
    await expect(select).not.toHaveValue('');
  });

  await step('link the ticket to the epic', async () => {
    await page.locator('.epic-select').selectOption({ label: ctx.epic.name });
    await expect(page.locator('.epic-select')).not.toHaveValue('');
  });

  await step('advance status TODO to IN_PROGRESS', async () => {
    await page.locator('.status-select').selectOption('IN_PROGRESS');
    await expect(page.locator('.status-select')).toHaveValue('IN_PROGRESS');
  });

  await step('advance status IN_PROGRESS to DONE', async () => {
    await page.locator('.status-select').selectOption('DONE');
    await expect(page.locator('.status-select')).toHaveValue('DONE');
  });

  await step('verify the ticket is linked on the epic page', async () => {
    await page.goto(`/epics/${ctx.epic.id}`);
    await expect(
      page.locator('.tickets-section').getByRole('link', { name: ticketTitle }),
    ).toBeVisible();
  });
});

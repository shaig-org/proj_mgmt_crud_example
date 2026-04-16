/**
 * Scenario: PM creates an epic via the UI in a pre-seeded project, then
 * seeds tickets into it via the API, views them on the epic page, and
 * watches the progress percentage move when one ticket is set to DONE.
 *
 * Replaces epic-progress-updates, epic-ticket-list, and
 * create-epic-in-project.
 */

import { expect } from '@playwright/test';
import { scenarioTest } from '../../helpers/scenario';
import {
  addTicketToEpic,
  createOrgAndPM,
  createProjectForPM,
  createTicket,
  loginViaUI,
  type PMProjectContext,
  type TicketRef,
} from '../../helpers/fixtures';
import { generateTestEpicTitle, generateTestTicketTitle } from '../../utils/test-config';

interface Ctx {
  project: PMProjectContext;
  epicName: string;
  tickets: TicketRef[];
}

let ctx: Ctx;

scenarioTest.beforeAll(async ({ request }) => {
  const pm = await createOrgAndPM(request, 'EpicProgress');
  const project = await createProjectForPM(request, pm, 'EpicProgress');
  ctx = {
    project,
    epicName: generateTestEpicTitle('EPWithTickets'),
    tickets: [],
  };
});

scenarioTest('Epic with ticket progress', async ({ page, request, step }) => {
  await step('login as PM', async () => {
    await loginViaUI(page, ctx.project.username, ctx.project.password);
    await expect(page).toHaveURL('/projects');
  });

  await step('open project details', async () => {
    await page.goto(`/projects/${ctx.project.projectId}`);
    await expect(page.getByRole('heading', { name: 'Epics', exact: true })).toBeVisible();
  });

  await step('create a new epic via the modal', async () => {
    await page.getByRole('button', { name: 'New Epic' }).click();
    await expect(page.getByRole('heading', { name: 'Create New Epic' })).toBeVisible();
    await page.getByLabel('Epic Name *').fill(ctx.epicName);
    await page.getByLabel('Description').fill('Scenario epic with tickets');
    await page.getByRole('button', { name: 'Create Epic' }).click();
    await expect(page.getByRole('heading', { name: 'Create New Epic' })).not.toBeVisible();
    await expect(page.getByRole('link', { name: ctx.epicName })).toBeVisible();
  });

  await step('seed two tickets into the epic via API', async () => {
    const t1 = await createTicket(request, ctx.project, {
      title: generateTestTicketTitle('EPTicketA'),
    });
    const t2 = await createTicket(request, ctx.project, {
      title: generateTestTicketTitle('EPTicketB'),
    });
    // Look up the epic id from the DOM so we avoid returning one from
    // the UI step above.
    const epicLink = page.getByRole('link', { name: ctx.epicName });
    const href = await epicLink.getAttribute('href');
    if (!href) throw new Error('epic link href missing');
    const epicId = href.split('/').pop()!;
    await addTicketToEpic(request, ctx.project, epicId, t1.id);
    await addTicketToEpic(request, ctx.project, epicId, t2.id);
    ctx.tickets = [t1, t2];
    // Reload so the link we click lands on a page with the new tickets.
    await page.reload();
    await expect(page.getByRole('link', { name: ctx.epicName })).toBeVisible();
  });

  await step('open the epic details page', async () => {
    await page.getByRole('link', { name: ctx.epicName }).click();
    await expect(page).toHaveURL(/\/epics\/[^/]+$/);
    await expect(page.getByRole('heading', { name: ctx.epicName })).toBeVisible();
  });

  await step('see both tickets listed and 0% progress', async () => {
    // Scroll the tickets section into view so the screenshot differs from the
    // prior `open the epic details page` frame, which lands at the top of the
    // epic page where the ticket list isn't necessarily visible yet.
    await page.locator('.tickets-section').scrollIntoViewIfNeeded();
    for (const t of ctx.tickets) {
      await expect(
        page.locator('.tickets-section').getByRole('link', { name: t.title }),
      ).toBeVisible();
    }
    await expect(page.locator('.progress-percentage')).toHaveText('0%');
  });

  await step('open the first linked ticket and set status to DONE', async () => {
    await page
      .locator('.tickets-section')
      .getByRole('link', { name: ctx.tickets[0].title })
      .click();
    await expect(page).toHaveURL(/\/tickets\/[^/]+$/);
    await page.locator('.status-select').selectOption('DONE');
    await expect(page.locator('.status-select')).toHaveValue('DONE');
  });

  await step('return to the epic and see progress increased to 50%', async () => {
    await page.goBack();
    await expect(page.locator('.progress-percentage')).toHaveText('50%');
  });
});

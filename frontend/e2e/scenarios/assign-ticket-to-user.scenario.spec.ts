/**
 * Scenario: PM opens a ticket and assigns it to themself using the
 * assignee dropdown on the ticket details page.
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
  ticketId: string;
  ticketTitle: string;
}

let ctx: Ctx;

scenarioTest.beforeAll(async ({ request }) => {
  const pm = await createOrgAndPM(request, 'AssignTicket');
  const project = await createProjectForPM(request, pm, 'AssignTicket');
  const ticket = await createTicket(request, project, {
    title: generateTestTicketTitle('ToAssign'),
  });
  ctx = { project, ticketId: ticket.id, ticketTitle: ticket.title };
});

scenarioTest('PM assigns a ticket to a user', async ({ page, step }) => {
  await step('login as PM', async () => {
    await loginViaUI(page, ctx.project.username, ctx.project.password);
    await expect(page).toHaveURL('/projects');
  });

  await step('open the ticket', async () => {
    await page.goto(`/tickets/${ctx.ticketId}`);
    await expect(page.getByRole('heading', { name: ctx.ticketTitle })).toBeVisible();
  });

  await step('see the assignee dropdown defaulted to Unassigned', async () => {
    await expect(page.locator('.assignee-select')).toHaveValue('');
  });

  await step('pick a user from the assignee dropdown', async () => {
    const select = page.locator('.assignee-select');
    const options = select.locator('option');
    // The first option is "Unassigned" (value=""); the second is the PM user.
    const firstUserValue = await options.nth(1).getAttribute('value');
    if (!firstUserValue) throw new Error('expected at least one assignable user');
    await select.selectOption(firstUserValue);
  });

  await step('confirm the assignee select reflects the new value', async () => {
    const select = page.locator('.assignee-select');
    await expect(select).not.toHaveValue('');
    await expect(select).toBeEnabled();
  });
});

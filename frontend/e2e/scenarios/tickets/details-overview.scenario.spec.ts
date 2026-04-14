/**
 * Scenario: PM opens a pre-seeded ticket and sees the full details layout —
 * description, editable status select, priority badge, assignee select,
 * and comments section.
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
  ticketId: string;
  ticketTitle: string;
}

let ctx: Ctx;

scenarioTest.beforeAll(async ({ request }) => {
  const pm = await createOrgAndPM(request, 'TicketOverview');
  const project = await createProjectForPM(request, pm, 'TicketOverview');
  const ticket = await createTicket(request, project, {
    title: generateTestTicketTitle('Overview'),
    priority: 'HIGH',
  });
  ctx = { project, ticketId: ticket.id, ticketTitle: ticket.title };
});

scenarioTest('PM reviews full ticket details layout', async ({ page, step }) => {
  await step('login as PM', async () => {
    await loginViaUI(page, ctx.project.username, ctx.project.password);
    await expect(page).toHaveURL('/projects');
  });

  await step('navigate directly to the ticket', async () => {
    await page.goto(`/tickets/${ctx.ticketId}`);
    await expect(page.getByRole('heading', { name: ctx.ticketTitle })).toBeVisible();
  });

  await step('see the ticket information block', async () => {
    await expect(page.getByRole('heading', { name: 'Ticket Information' })).toBeVisible();
    await expect(page.locator('.status-select')).toHaveValue('TODO');
  });

  await step('see priority and assignee controls', async () => {
    await expect(page.locator('.priority-badge.priority-high')).toBeVisible();
    await expect(page.locator('.assignee-select')).toBeVisible();
    await expect(page.locator('.epic-select')).toBeVisible();
  });

  await step('see the comments section below', async () => {
    await expect(page.getByRole('heading', { name: /Comments/ })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Add Comment' })).toBeVisible();
  });
});

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

  // Merged the prior `navigate directly to the ticket`, `see the ticket
  // information block`, and `see priority and assignee controls` steps. All
  // three landed on the same top-of-ticket viewport with no DOM mutation, so
  // the screenshots were duplicates of each other.
  await step('navigate to the ticket and review the information block', async () => {
    await page.goto(`/tickets/${ctx.ticketId}`);
    await expect(page.getByRole('heading', { name: ctx.ticketTitle })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Ticket Information' })).toBeVisible();
    await expect(page.locator('.status-select')).toHaveValue('TODO');
    await expect(page.locator('.priority-badge.priority-high')).toBeVisible();
    await expect(page.locator('.assignee-select')).toBeVisible();
    await expect(page.locator('.epic-select')).toBeVisible();
  });

  await step('scroll down to see the comments section below', async () => {
    // Scroll the comments heading into view so this frame is visually
    // distinct from the prior top-of-ticket frame; without the scroll the
    // viewport screenshot would be identical.
    await page.getByRole('heading', { name: /Comments/ }).scrollIntoViewIfNeeded();
    await expect(page.getByRole('heading', { name: /Comments/ })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Add Comment' })).toBeVisible();
  });
});

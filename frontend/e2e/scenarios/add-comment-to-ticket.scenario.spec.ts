/**
 * Scenario: PM opens a ticket and posts a comment via the Add Comment form.
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
  const pm = await createOrgAndPM(request, 'AddComment');
  const project = await createProjectForPM(request, pm, 'AddComment');
  const ticket = await createTicket(request, project, {
    title: generateTestTicketTitle('Discussed'),
  });
  ctx = { project, ticketId: ticket.id, ticketTitle: ticket.title };
});

scenarioTest('PM adds a comment to a ticket', async ({ page, step }) => {
  const commentBody = `Scenario comment ${Date.now()}`;

  await step('login as PM', async () => {
    await loginViaUI(page, ctx.project.username, ctx.project.password);
    await expect(page).toHaveURL('/projects');
  });

  await step('open the ticket details page', async () => {
    await page.goto(`/tickets/${ctx.ticketId}`);
    await expect(page.getByRole('heading', { name: ctx.ticketTitle })).toBeVisible();
    await expect(page.getByText('No comments yet. Be the first to comment!')).toBeVisible();
  });

  await step('type a comment into the Add Comment form', async () => {
    await page.getByLabel('New comment content').fill(commentBody);
    await expect(page.getByLabel('New comment content')).toHaveValue(commentBody);
  });

  await step('submit the comment', async () => {
    await page.getByRole('button', { name: /Add Comment/ }).click();
    await expect(page.getByText(commentBody)).toBeVisible();
  });

  await step('see the new comment in the list with a delete button', async () => {
    const comment = page.locator('.comment', { hasText: commentBody });
    await expect(comment).toBeVisible();
    await expect(comment.getByRole('button', { name: /Delete comment/ })).toBeVisible();
  });
});

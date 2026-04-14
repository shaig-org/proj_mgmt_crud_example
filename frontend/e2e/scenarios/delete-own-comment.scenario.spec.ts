/**
 * Scenario: PM deletes their own comment on a ticket via the per-comment
 * Delete button. The delete flow goes through a `window.confirm()` prompt,
 * which we accept via a dialog handler registered before the click.
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
  const pm = await createOrgAndPM(request, 'DeleteComment');
  const project = await createProjectForPM(request, pm, 'DeleteComment');
  const ticket = await createTicket(request, project, {
    title: generateTestTicketTitle('CommentedOn'),
  });
  ctx = { project, ticketId: ticket.id, ticketTitle: ticket.title };
});

scenarioTest('PM deletes their own comment', async ({ page, step }) => {
  const commentBody = `Scenario delete me ${Date.now()}`;

  await step('login as PM', async () => {
    await loginViaUI(page, ctx.project.username, ctx.project.password);
    await expect(page).toHaveURL('/projects');
  });

  await step('open the ticket and post a comment', async () => {
    await page.goto(`/tickets/${ctx.ticketId}`);
    await page.getByLabel('New comment content').fill(commentBody);
    await page.getByRole('button', { name: /Add Comment/ }).click();
    await expect(page.locator('.comment', { hasText: commentBody })).toBeVisible();
  });

  await step('focus the delete button on the comment', async () => {
    const btn = page.locator('.comment', { hasText: commentBody })
      .getByRole('button', { name: /Delete comment/ });
    await btn.focus();
    await expect(btn).toBeFocused();
  });

  await step('click delete, accept confirm, and see it disappear', async () => {
    page.once('dialog', async (dialog) => {
      await dialog.accept();
    });
    await page.locator('.comment', { hasText: commentBody })
      .getByRole('button', { name: /Delete comment/ })
      .click();
    await expect(page.locator('.comment', { hasText: commentBody })).toHaveCount(0);
  });

  await step('comments section returns to the empty state', async () => {
    await expect(page.getByText('No comments yet. Be the first to comment!')).toBeVisible();
  });
});

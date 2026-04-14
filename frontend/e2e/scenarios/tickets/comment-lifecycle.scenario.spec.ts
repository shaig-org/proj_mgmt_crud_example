/**
 * Scenario: PM opens a ticket with no comments, adds one via the Add Comment
 * form, confirms it appears, then deletes it and sees the empty state again.
 *
 * Replaces add-comment-to-ticket and delete-own-comment.
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
  const pm = await createOrgAndPM(request, 'CommentLifecycle');
  const project = await createProjectForPM(request, pm, 'CommentLifecycle');
  const ticket = await createTicket(request, project, {
    title: generateTestTicketTitle('CommentLC'),
  });
  ctx = { project, ticketId: ticket.id, ticketTitle: ticket.title };
});

scenarioTest('PM adds and deletes a comment on a ticket', async ({ page, step }) => {
  const commentBody = `Lifecycle comment ${Date.now()}`;

  await step('login as PM', async () => {
    await loginViaUI(page, ctx.project.username, ctx.project.password);
    await expect(page).toHaveURL('/projects');
  });

  await step('open the ticket details with empty comments', async () => {
    await page.goto(`/tickets/${ctx.ticketId}`);
    await expect(page.getByRole('heading', { name: ctx.ticketTitle })).toBeVisible();
    await expect(page.getByText('No comments yet. Be the first to comment!')).toBeVisible();
  });

  await step('type the comment content', async () => {
    await page.getByLabel('New comment content').fill(commentBody);
    await expect(page.getByLabel('New comment content')).toHaveValue(commentBody);
  });

  await step('submit the comment and see it in the list', async () => {
    await page.getByRole('button', { name: /Add Comment/ }).click();
    const comment = page.locator('.comment', { hasText: commentBody });
    await expect(comment).toBeVisible();
    await expect(comment.getByRole('button', { name: /Delete comment/ })).toBeVisible();
  });

  await step('focus the delete button on the new comment', async () => {
    const btn = page
      .locator('.comment', { hasText: commentBody })
      .getByRole('button', { name: /Delete comment/ });
    await btn.focus();
    await expect(btn).toBeFocused();
  });

  await step('click delete and accept the confirm dialog', async () => {
    page.once('dialog', async (dialog) => {
      await dialog.accept();
    });
    await page
      .locator('.comment', { hasText: commentBody })
      .getByRole('button', { name: /Delete comment/ })
      .click();
    await expect(page.locator('.comment', { hasText: commentBody })).toHaveCount(0);
  });

  await step('comments section returns to the empty state', async () => {
    await expect(page.getByText('No comments yet. Be the first to comment!')).toBeVisible();
  });
});

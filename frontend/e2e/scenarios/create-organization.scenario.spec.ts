/**
 * Scenario: super admin opens the Organizations page, creates a new
 * organization through the modal, and sees it appear in the list.
 */

import { expect } from '@playwright/test';
import { scenarioTest } from '../helpers/scenario';
import { generateTestOrgName } from '../utils/test-config';

scenarioTest('Super admin creates an organization', async ({ page, step }) => {
  const orgName = generateTestOrgName('FromUI');

  await step('login as super admin', async () => {
    await page.goto('/login');
    await page.getByRole('textbox', { name: 'Username' }).fill('admin');
    await page.getByRole('textbox', { name: 'Password' }).fill('SuperAdmin123!');
    await page.getByRole('button', { name: 'Login' }).click();
    await expect(page).toHaveURL('/projects');
  });

  await step('navigate to organizations page', async () => {
    await page.getByRole('link', { name: 'Organizations' }).click();
    await expect(page).toHaveURL('/organizations');
    await expect(page.getByRole('heading', { name: 'Organizations' })).toBeVisible();
  });

  await step('open the create-organization modal', async () => {
    await page.getByRole('button', { name: 'New Organization' }).click();
    await expect(page.getByRole('heading', { name: 'Create New Organization' })).toBeVisible();
  });

  await step('fill out the organization form', async () => {
    await page.getByLabel('Organization Name *').fill(orgName);
    await page.getByLabel('Description').fill('Created via scenario test');
    await expect(page.getByLabel('Organization Name *')).toHaveValue(orgName);
  });

  await step('submit and see the new organization in the list', async () => {
    await page.getByRole('button', { name: 'Create Organization' }).click();
    await expect(page.getByRole('heading', { name: 'Create New Organization' })).not.toBeVisible();
    await expect(page.getByText(orgName)).toBeVisible();
  });
});

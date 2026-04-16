/**
 * Scenario: a super admin bootstraps a new team — creates an organization,
 * then a project-manager user in that org, and finally reveals the
 * generated password on the success modal.
 */

import { expect } from '@playwright/test';
import { scenarioTest } from '../../helpers/scenario';
import { generateTestOrgName, generateTestUserName } from '../../utils/test-config';

scenarioTest('Super admin onboards a new organization and PM', async ({ page, step }) => {
  const orgName = generateTestOrgName('Onboarding');
  const pmUsername = generateTestUserName('pm').toLowerCase().replace(/[^a-z0-9]/g, '').slice(0, 40);

  await step('login as super admin', async () => {
    await page.goto('/login');
    await page.getByRole('textbox', { name: 'Username' }).fill('admin');
    await page.getByRole('textbox', { name: 'Password' }).fill('SuperAdmin123!');
    await page.getByRole('button', { name: 'Login' }).click();
    await expect(page).toHaveURL('/projects');
  });

  await step('create the organization', async () => {
    await page.getByRole('link', { name: 'Organizations' }).click();
    await page.getByRole('button', { name: 'New Organization' }).click();
    await page.getByLabel('Organization Name *').fill(orgName);
    await page.getByRole('button', { name: 'Create Organization' }).click();
    await expect(page.getByText(orgName)).toBeVisible();
  });

  await step('open the users page and launch create-user modal', async () => {
    await page.getByRole('link', { name: 'Users' }).click();
    await expect(page).toHaveURL('/users');
    await page.getByRole('button', { name: 'New User' }).click();
    await expect(page.getByRole('heading', { name: 'Create New User' })).toBeVisible();
  });

  await step('fill the user form and pick the new organization', async () => {
    await page.getByLabel('Username *').fill(pmUsername);
    await page.getByLabel('Email *').fill(`${pmUsername}@example.com`);
    await page.getByLabel('Full Name *').fill('Onboarded PM');
    await page.getByLabel('Organization *').selectOption({ label: orgName });
    await page.getByLabel('Role *').selectOption('project_manager');
    await expect(page.getByLabel('Username *')).toHaveValue(pmUsername);
  });

  await step('submit and see the generated password modal', async () => {
    await page.getByRole('button', { name: 'Create User' }).click();
    await expect(page.getByRole('heading', { name: 'User Created Successfully!' })).toBeVisible();
    await expect(page.getByText('Generated Password')).toBeVisible();
  });

  await step('close the success modal and see user in list', async () => {
    await page
      .locator('.success-modal')
      .locator('button.primary-button', { hasText: 'Close' })
      .click();
    await expect(page.getByRole('heading', { name: 'User Created Successfully!' })).not.toBeVisible();
    await expect(page.locator('.users-table').getByText(pmUsername).first()).toBeVisible();
  });
});

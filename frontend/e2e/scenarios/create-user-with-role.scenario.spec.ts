/**
 * Scenario: super admin creates a write_access user via the Users page.
 * Fixture creates the organization via API so the scenario can focus
 * on the user-creation UI and the generated-password modal.
 */

import { expect } from '@playwright/test';
import { scenarioTest } from '../helpers/scenario';
import { TEST_CONFIG, generateTestOrgName, generateTestUserName } from '../utils/test-config';

interface Fixture {
  orgName: string;
}

let fixture: Fixture;

scenarioTest.beforeAll(async ({ request }) => {
  const loginRes = await request.post(`${TEST_CONFIG.API_BASE_URL}/auth/login`, {
    headers: { 'Content-Type': 'application/json' },
    data: { username: 'admin', password: 'SuperAdmin123!' },
  });
  const { access_token: token } = (await loginRes.json()) as { access_token: string };

  const orgName = generateTestOrgName('WithRole');
  const orgRes = await request.post(`${TEST_CONFIG.API_BASE_URL}/api/organizations`, {
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    data: { name: orgName, description: 'Scenario fixture org' },
  });
  if (!orgRes.ok()) throw new Error(`org create failed: ${orgRes.status()}`);
  fixture = { orgName };
});

scenarioTest('Create a write-access user and reveal the generated password', async ({ page, step }) => {
  const username = generateTestUserName('writer').toLowerCase().replace(/[^a-z0-9]/g, '').slice(0, 40);

  await step('login as super admin', async () => {
    await page.goto('/login');
    await page.getByRole('textbox', { name: 'Username' }).fill('admin');
    await page.getByRole('textbox', { name: 'Password' }).fill('SuperAdmin123!');
    await page.getByRole('button', { name: 'Login' }).click();
    await expect(page).toHaveURL('/projects');
  });

  await step('open the users page', async () => {
    await page.getByRole('link', { name: 'Users' }).click();
    await expect(page).toHaveURL('/users');
    await expect(page.getByRole('heading', { name: 'Users' })).toBeVisible();
  });

  await step('open the create-user modal', async () => {
    await page.getByRole('button', { name: 'New User' }).click();
    await expect(page.getByRole('heading', { name: 'Create New User' })).toBeVisible();
  });

  await step('fill the form and pick the write_access role', async () => {
    await page.getByLabel('Username *').fill(username);
    await page.getByLabel('Email *').fill(`${username}@example.com`);
    await page.getByLabel('Full Name *').fill('Write User');
    await page.getByLabel('Organization *').selectOption({ label: fixture.orgName });
    await page.getByLabel('Role *').selectOption('write_access');
    await expect(page.getByLabel('Role *')).toHaveValue('write_access');
  });

  await step('submit and reveal the generated password', async () => {
    await page.getByRole('button', { name: 'Create User' }).click();
    await expect(page.getByRole('heading', { name: 'User Created Successfully!' })).toBeVisible();
    await expect(page.getByText('Generated Password')).toBeVisible();
  });

  await step('close modal and confirm user in list', async () => {
    await page
      .locator('.success-modal')
      .locator('button.primary-button', { hasText: 'Close' })
      .click();
    await expect(page.locator('.users-table').getByText(username).first()).toBeVisible();
  });
});

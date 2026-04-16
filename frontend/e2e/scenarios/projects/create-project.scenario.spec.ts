/**
 * Scenario: admin creates a project via the UI and sees it in the list.
 */

import { expect } from '@playwright/test';
import { scenarioTest } from '../../helpers/scenario';
import { TEST_CONFIG, generateTestOrgName, generateTestProjectName } from '../../utils/test-config';

interface FixtureUser {
  username: string;
  password: string;
}

let pm: FixtureUser;

scenarioTest.beforeAll(async ({ request }) => {
  const loginRes = await request.post(`${TEST_CONFIG.API_BASE_URL}/auth/login`, {
    headers: { 'Content-Type': 'application/json' },
    data: { username: 'admin', password: 'SuperAdmin123!' },
  });
  const { access_token: adminToken } = (await loginRes.json()) as { access_token: string };

  const orgRes = await request.post(`${TEST_CONFIG.API_BASE_URL}/api/organizations`, {
    headers: { Authorization: `Bearer ${adminToken}`, 'Content-Type': 'application/json' },
    data: { name: generateTestOrgName('CreateProject'), description: 'Scenario test org' },
  });
  const org = (await orgRes.json()) as { id: string };

  const pmUsername = `pm${Date.now()}${Math.random().toString(36).slice(2, 6)}`;
  const userRes = await request.post(
    `${TEST_CONFIG.API_BASE_URL}/api/users?organization_id=${org.id}&role=project_manager`,
    {
      headers: { Authorization: `Bearer ${adminToken}`, 'Content-Type': 'application/json' },
      data: { username: pmUsername, email: `${pmUsername}@example.com`, full_name: 'PM Scenario' },
    },
  );
  if (!userRes.ok()) {
    throw new Error(`user create failed: ${userRes.status()} ${await userRes.text()}`);
  }
  const userBody = (await userRes.json()) as { generated_password: string };
  if (!userBody.generated_password) {
    throw new Error(`no generated_password in response: ${JSON.stringify(userBody)}`);
  }
  pm = { username: pmUsername, password: userBody.generated_password };
});

scenarioTest('Create project full flow', async ({ page, step }) => {
  const projectName = generateTestProjectName('WebApp');

  await step('login as project manager', async () => {
    await page.goto('/login');
    await page.getByRole('textbox', { name: 'Username' }).fill(pm.username);
    await page.getByRole('textbox', { name: 'Password' }).fill(pm.password);
    await page.getByRole('button', { name: 'Login' }).click();
    await expect(page).toHaveURL('/projects');
  });

  await step('open new project modal', async () => {
    await page.getByRole('button', { name: 'New Project' }).click();
    await expect(page.getByRole('heading', { name: 'Create New Project' })).toBeVisible();
  });

  await step('fill project form', async () => {
    await page.getByLabel('Project Name *').fill(projectName);
    await page.getByLabel('Description').fill('Created from scenario test');
    await expect(page.getByLabel('Project Name *')).toHaveValue(projectName);
  });

  await step('submit and see project in list', async () => {
    await page.getByRole('button', { name: 'Create Project' }).click();
    await expect(page.getByRole('heading', { name: 'Create New Project' })).not.toBeVisible();
    await expect(page.getByText(projectName)).toBeVisible();
  });
});

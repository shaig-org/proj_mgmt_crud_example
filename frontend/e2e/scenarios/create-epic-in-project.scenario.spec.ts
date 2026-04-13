/**
 * Scenario: given a project (API pre-created), admin creates an epic
 * via the project details page.
 */

import { expect } from '@playwright/test';
import { scenarioTest } from '../helpers/scenario';
import {
  TEST_CONFIG,
  generateTestOrgName,
  generateTestProjectName,
  generateTestEpicTitle,
} from '../utils/test-config';

interface SetupFixture {
  username: string;
  password: string;
  projectId: string;
  projectName: string;
}

let setup: SetupFixture;

scenarioTest.beforeAll(async ({ request }) => {
  const adminLogin = await request.post(`${TEST_CONFIG.API_BASE_URL}/auth/login`, {
    headers: { 'Content-Type': 'application/json' },
    data: { username: 'admin', password: 'SuperAdmin123!' },
  });
  const { access_token: adminToken } = (await adminLogin.json()) as { access_token: string };

  const orgRes = await request.post(`${TEST_CONFIG.API_BASE_URL}/api/organizations`, {
    headers: { Authorization: `Bearer ${adminToken}`, 'Content-Type': 'application/json' },
    data: { name: generateTestOrgName('CreateEpic'), description: 'Scenario test org' },
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
  const { generated_password: password } = (await userRes.json()) as { generated_password: string };

  const pmLogin = await request.post(`${TEST_CONFIG.API_BASE_URL}/auth/login`, {
    headers: { 'Content-Type': 'application/json' },
    data: { username: pmUsername, password },
  });
  const { access_token: pmToken } = (await pmLogin.json()) as { access_token: string };

  const projectName = generateTestProjectName('EpicScenario');
  const projectRes = await request.post(
    `${TEST_CONFIG.API_BASE_URL}/api/projects?organization_id=${org.id}`,
    {
      headers: { Authorization: `Bearer ${pmToken}`, 'Content-Type': 'application/json' },
      data: { name: projectName, description: 'Project for epic scenario' },
    },
  );
  const project = (await projectRes.json()) as { id: string };

  setup = { username: pmUsername, password, projectId: project.id, projectName };
});

scenarioTest('scenario_create_epic_in_project', async ({ page, step }) => {
  const epicName = generateTestEpicTitle('LaunchPrep');

  await step('login as project manager', async () => {
    await page.goto('/login');
    await page.getByRole('textbox', { name: 'Username' }).fill(setup.username);
    await page.getByRole('textbox', { name: 'Password' }).fill(setup.password);
    await page.getByRole('button', { name: 'Login' }).click();
    await expect(page).toHaveURL('/projects');
  });

  await step('open project details', async () => {
    await page.goto(`/projects/${setup.projectId}`);
    await expect(page).toHaveURL(`/projects/${setup.projectId}`);
    await expect(page.getByRole('heading', { name: 'Epics', exact: true })).toBeVisible();
  });

  await step('open new epic modal', async () => {
    await page.getByRole('button', { name: 'New Epic' }).click();
    await expect(page.getByRole('heading', { name: 'Create New Epic' })).toBeVisible();
  });

  await step('fill epic form', async () => {
    await page.getByLabel('Epic Name *').fill(epicName);
    await page.getByLabel('Description').fill('Scenario-created epic');
    await expect(page.getByLabel('Epic Name *')).toHaveValue(epicName);
  });

  await step('submit epic form', async () => {
    await page.getByRole('button', { name: 'Create Epic' }).click();
    await expect(page.getByRole('heading', { name: 'Create New Epic' })).not.toBeVisible();
  });

  await step('verify epic on project page', async () => {
    await expect(page.getByText(epicName)).toBeVisible();
  });
});

/**
 * Scenario: given a project + epic (API pre-created), admin creates a
 * ticket via the project UI and transitions its status via the ticket
 * details page.
 *
 * Note: in this app, the "New Ticket" button lives on the project details
 * page (not the epic details page); tickets may optionally be linked to
 * an epic via the form. This scenario creates the ticket from the project
 * page, then opens its details and updates status.
 */

import { expect } from '@playwright/test';
import { scenarioTest } from '../helpers/scenario';
import {
  TEST_CONFIG,
  generateTestOrgName,
  generateTestProjectName,
  generateTestEpicTitle,
  generateTestTicketTitle,
} from '../utils/test-config';

interface SetupFixture {
  username: string;
  password: string;
  projectId: string;
  projectName: string;
  epicId: string;
  epicName: string;
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
    data: { name: generateTestOrgName('TicketStatus'), description: 'Scenario test org' },
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

  const projectName = generateTestProjectName('TicketScenario');
  const projectRes = await request.post(
    `${TEST_CONFIG.API_BASE_URL}/api/projects?organization_id=${org.id}`,
    {
      headers: { Authorization: `Bearer ${pmToken}`, 'Content-Type': 'application/json' },
      data: { name: projectName, description: 'Project for ticket scenario' },
    },
  );
  const project = (await projectRes.json()) as { id: string };

  const epicName = generateTestEpicTitle('TicketEpic');
  const epicRes = await request.post(`${TEST_CONFIG.API_BASE_URL}/api/epics`, {
    headers: { Authorization: `Bearer ${pmToken}`, 'Content-Type': 'application/json' },
    data: { name: epicName, description: 'Epic for ticket scenario' },
  });
  const epic = (await epicRes.json()) as { id: string };

  setup = {
    username: pmUsername,
    password,
    projectId: project.id,
    projectName,
    epicId: epic.id,
    epicName,
  };
});

scenarioTest('scenario_create_ticket_and_change_status', async ({ page, step }) => {
  const ticketTitle = generateTestTicketTitle('ShipIt');

  await step('login as project manager', async () => {
    await page.goto('/login');
    await page.getByRole('textbox', { name: 'Username' }).fill(setup.username);
    await page.getByRole('textbox', { name: 'Password' }).fill(setup.password);
    await page.getByRole('button', { name: 'Login' }).click();
    await expect(page).toHaveURL('/projects');
  });

  await step('open project details', async () => {
    await page.goto(`/projects/${setup.projectId}`);
    await expect(page.getByRole('heading', { name: 'Tickets', exact: true })).toBeVisible();
  });

  await step('open new ticket modal', async () => {
    await page.getByRole('button', { name: 'New Ticket' }).click();
    await expect(page.getByRole('heading', { name: 'Create New Ticket' })).toBeVisible();
  });

  await step('fill ticket form', async () => {
    await page.locator('#ticket-title').fill(ticketTitle);
    await page.locator('#ticket-description').fill('Scenario-created ticket');
    await page.locator('#ticket-priority').selectOption('MEDIUM');
    await expect(page.locator('#ticket-title')).toHaveValue(ticketTitle);
  });

  await step('submit ticket form', async () => {
    await page.getByRole('button', { name: 'Create Ticket' }).click();
    await expect(page.getByRole('heading', { name: 'Create New Ticket' })).not.toBeVisible();
    await expect(page.getByText(ticketTitle)).toBeVisible();
  });

  await step('open ticket details', async () => {
    await page.getByText(ticketTitle).click();
    await expect(page).toHaveURL(/\/tickets\/[a-f0-9-]+/);
    await expect(page.locator('.status-select')).toBeVisible();
  });

  await step('change ticket status', async () => {
    await page.locator('.status-select').selectOption('IN_PROGRESS');
  });

  await step('verify status updated', async () => {
    await expect(page.locator('.status-select')).toHaveValue('IN_PROGRESS');
  });
});

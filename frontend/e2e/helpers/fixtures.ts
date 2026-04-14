/**
 * Shared API-level fixture helpers for scenario tests.
 *
 * Only callable from `scenarioTest.beforeAll` / `beforeEach` — never inside
 * a scenario body (UI-only inside the body is the scenario authoring rule).
 */

import type { APIRequestContext } from '@playwright/test';
import { TEST_CONFIG, generateTestOrgName, generateTestProjectName } from '../utils/test-config';

export interface PMContext {
  orgId: string;
  orgName: string;
  username: string;
  password: string;
  token: string;
}

export interface PMProjectContext extends PMContext {
  projectId: string;
  projectName: string;
}

async function adminToken(request: APIRequestContext): Promise<string> {
  const res = await request.post(`${TEST_CONFIG.API_BASE_URL}/auth/login`, {
    headers: { 'Content-Type': 'application/json' },
    data: { username: 'admin', password: 'SuperAdmin123!' },
  });
  if (!res.ok()) throw new Error(`admin login failed: ${res.status()}`);
  const body = (await res.json()) as { access_token: string };
  return body.access_token;
}

export async function createOrgAndPM(
  request: APIRequestContext,
  baseName: string,
): Promise<PMContext> {
  const token = await adminToken(request);

  const orgName = generateTestOrgName(baseName);
  const orgRes = await request.post(`${TEST_CONFIG.API_BASE_URL}/api/organizations`, {
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    data: { name: orgName, description: `scenario fixture org: ${baseName}` },
  });
  if (!orgRes.ok()) throw new Error(`org create failed: ${orgRes.status()}`);
  const org = (await orgRes.json()) as { id: string };

  const username = `pm${Date.now()}${Math.random().toString(36).slice(2, 6)}`;
  const userRes = await request.post(
    `${TEST_CONFIG.API_BASE_URL}/api/users?organization_id=${org.id}&role=project_manager`,
    {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      data: { username, email: `${username}@example.com`, full_name: `PM ${baseName}` },
    },
  );
  if (!userRes.ok()) throw new Error(`pm create failed: ${userRes.status()}`);
  const userBody = (await userRes.json()) as { generated_password: string };
  const password = userBody.generated_password;

  const pmLogin = await request.post(`${TEST_CONFIG.API_BASE_URL}/auth/login`, {
    headers: { 'Content-Type': 'application/json' },
    data: { username, password },
  });
  if (!pmLogin.ok()) throw new Error(`pm login failed: ${pmLogin.status()}`);
  const pmToken = ((await pmLogin.json()) as { access_token: string }).access_token;

  return { orgId: org.id, orgName, username, password, token: pmToken };
}

export async function createProjectForPM(
  request: APIRequestContext,
  pm: PMContext,
  baseName: string,
): Promise<PMProjectContext> {
  const projectName = generateTestProjectName(baseName);
  const res = await request.post(
    `${TEST_CONFIG.API_BASE_URL}/api/projects?organization_id=${pm.orgId}`,
    {
      headers: { Authorization: `Bearer ${pm.token}`, 'Content-Type': 'application/json' },
      data: { name: projectName, description: `scenario project: ${baseName}` },
    },
  );
  if (!res.ok()) throw new Error(`project create failed: ${res.status()}`);
  const project = (await res.json()) as { id: string };
  return { ...pm, projectId: project.id, projectName };
}

export interface EpicRef {
  id: string;
  name: string;
}

export async function createEpicForProject(
  request: APIRequestContext,
  ctx: PMProjectContext,
  name: string,
): Promise<EpicRef> {
  const res = await request.post(`${TEST_CONFIG.API_BASE_URL}/api/epics`, {
    headers: { Authorization: `Bearer ${ctx.token}`, 'Content-Type': 'application/json' },
    data: { name, description: 'scenario epic' },
  });
  if (!res.ok()) throw new Error(`epic create failed: ${res.status()} ${await res.text()}`);
  const body = (await res.json()) as { id: string; name: string };
  return { id: body.id, name: body.name };
}

export interface TicketRef {
  id: string;
  title: string;
}

export async function createTicket(
  request: APIRequestContext,
  ctx: PMProjectContext,
  opts: { title: string; priority?: string; assigneeId?: string; status?: string },
): Promise<TicketRef> {
  const params = new URLSearchParams({ project_id: ctx.projectId });
  if (opts.assigneeId) params.set('assignee_id', opts.assigneeId);
  const res = await request.post(
    `${TEST_CONFIG.API_BASE_URL}/api/tickets?${params.toString()}`,
    {
      headers: { Authorization: `Bearer ${ctx.token}`, 'Content-Type': 'application/json' },
      data: {
        title: opts.title,
        description: 'scenario ticket',
        priority: opts.priority,
      },
    },
  );
  if (!res.ok()) throw new Error(`ticket create failed: ${res.status()} ${await res.text()}`);
  const body = (await res.json()) as { id: string; title: string };

  if (opts.status && opts.status !== 'TODO') {
    const patch = await request.put(
      `${TEST_CONFIG.API_BASE_URL}/api/tickets/${body.id}/status`,
      {
        headers: { Authorization: `Bearer ${ctx.token}`, 'Content-Type': 'application/json' },
        data: { status: opts.status },
      },
    );
    if (!patch.ok()) throw new Error(`ticket status patch failed: ${patch.status()}`);
  }

  return { id: body.id, title: body.title };
}

export async function addTicketToEpic(
  request: APIRequestContext,
  ctx: PMProjectContext,
  epicId: string,
  ticketId: string,
): Promise<void> {
  const res = await request.post(
    `${TEST_CONFIG.API_BASE_URL}/api/epics/${epicId}/tickets?ticket_id=${ticketId}`,
    { headers: { Authorization: `Bearer ${ctx.token}` } },
  );
  if (!res.ok()) throw new Error(`link ticket->epic failed: ${res.status()}`);
}

export async function loginViaUI(
  page: import('@playwright/test').Page,
  username: string,
  password: string,
): Promise<void> {
  await page.goto('/login');
  await page.getByRole('textbox', { name: 'Username' }).fill(username);
  await page.getByRole('textbox', { name: 'Password' }).fill(password);
  await page.getByRole('button', { name: 'Login' }).click();
}

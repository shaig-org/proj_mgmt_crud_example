/**
 * E2E auth helpers — bypass UI login by seeding the auth state Playwright
 * understands the AuthContext to read from localStorage.
 *
 * Why: every test used to do a UI login in beforeEach. UI login → POST
 * /auth/login → bcrypt on the backend. Under high parallelism (≥6 workers
 * or even ~4 workers in some cases), the bcrypt waves cause cascading
 * "Logging in..." timeouts. The DB is fine; bcrypt is the bottleneck.
 *
 * Strategy: per-worker token cache. The first call for a given username in
 * a Playwright worker pays one API login (one bcrypt). Subsequent calls in
 * the same worker reuse the cached `{access_token, user_id, role,
 * organization_id}` and just seed the localStorage on the page. The page
 * boots already-authed; no UI login, no extra bcrypt.
 *
 * This module is loaded fresh per Playwright worker (each worker is its own
 * Node process), so the Map is automatically worker-scoped.
 */

import type { Page, APIRequestContext } from '@playwright/test';
import { TEST_CONFIG } from './test-config';

interface CachedAuth {
  access_token: string;
  user_id: string;
  role: string;
  organization_id: string | null;
}

const tokenCache = new Map<string, CachedAuth>();

/**
 * Log in via API (cached per worker per username) and seed localStorage on
 * the page so the AuthContext picks it up on first render — no UI login.
 *
 * Returns the access token (handy when the test also needs to call API
 * endpoints directly via `page.request`).
 *
 * Pair this with `await page.goto('/')` (or any non-login route). DO NOT
 * navigate to `/login` after calling — the AuthContext will redirect away
 * before you can interact with the form.
 */
export async function loginViaApi(
  page: Page,
  username: string,
  password: string,
): Promise<string> {
  let auth = tokenCache.get(username);
  if (!auth) {
    const res = await page.request.post(`${TEST_CONFIG.API_BASE_URL}/auth/login`, {
      headers: { 'Content-Type': 'application/json' },
      data: { username, password },
    });
    if (!res.ok()) {
      throw new Error(
        `loginViaApi failed for ${username}: ${res.status()} ${await res.text()}`,
      );
    }
    auth = (await res.json()) as CachedAuth;
    tokenCache.set(username, auth);
  }

  // Match the exact shape AuthContext.tsx writes to localStorage.
  const authState = {
    user: {
      id: auth.user_id,
      username,
      role: auth.role,
      organizationId: auth.organization_id,
    },
    token: auth.access_token,
  };

  // addInitScript fires before any page script on every navigation in this
  // page's context, so localStorage is set before AuthProvider's useEffect
  // reads it. The result: the app boots already authenticated.
  await page.addInitScript((state) => {
    window.localStorage.setItem('auth_state', JSON.stringify(state));
  }, authState);

  return auth.access_token;
}

/**
 * Same as `loginViaApi` but takes an APIRequestContext directly (e.g. from
 * a `request` fixture) — useful in `beforeAll` blocks that don't have a
 * `page` yet but need a token. Also caches per-worker per-username.
 */
export async function loginViaApiRequest(
  request: APIRequestContext,
  username: string,
  password: string,
): Promise<string> {
  let auth = tokenCache.get(username);
  if (!auth) {
    const res = await request.post(`${TEST_CONFIG.API_BASE_URL}/auth/login`, {
      headers: { 'Content-Type': 'application/json' },
      data: { username, password },
    });
    if (!res.ok()) {
      throw new Error(
        `loginViaApiRequest failed for ${username}: ${res.status()} ${await res.text()}`,
      );
    }
    auth = (await res.json()) as CachedAuth;
    tokenCache.set(username, auth);
  }
  return auth.access_token;
}

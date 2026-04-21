// Pure port-resolution logic for the dev-dashboard Vite server. Extracted
// from vite.config.ts so it can be unit-tested without evaluating the full
// config (which performs filesystem I/O at import time).
//
// The "where does the port value come from" seam lives in vite.config.ts;
// this file only answers "given a raw string, what numeric port do we use?".

export const DASHBOARD_PORT_DEFAULT = 5179;

export function pickDashboardPort(raw: string | undefined): number {
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? n : DASHBOARD_PORT_DEFAULT;
}

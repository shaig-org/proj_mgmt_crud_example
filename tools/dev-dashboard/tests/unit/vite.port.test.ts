// @vitest-environment node
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import path from 'node:path';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';

// Tests for the DASHBOARD_PORT env wiring in tools/dev-dashboard/vite.config.ts
// per docs/tasks/per-worktree-ports/plan.md §4.5.
//
// The dashboard's vite.config.ts default-exports a Promise (the resolved config)
// rather than a factory. To test different env values we bust the module cache
// with vi.resetModules() between tests, and run under the node environment so
// esbuild/rolldown (transitively imported by `vite`) works.

interface ResolvedConfig {
  server: { port: number };
}

async function loadConfig(): Promise<ResolvedConfig> {
  vi.resetModules();
  const mod = (await import('../../vite.config')) as { default: Promise<ResolvedConfig> };
  return mod.default;
}

const ORIGINAL_CWD = process.cwd();
let sandboxDir: string | undefined;

beforeEach(() => {
  delete process.env.DASHBOARD_PORT;
  sandboxDir = mkdtempSync(path.join(tmpdir(), 'dashboard-vite-port-'));
  process.chdir(sandboxDir);
});

afterEach(() => {
  process.chdir(ORIGINAL_CWD);
  if (sandboxDir) {
    rmSync(sandboxDir, { recursive: true, force: true });
    sandboxDir = undefined;
  }
  delete process.env.DASHBOARD_PORT;
});

describe('dev-dashboard vite.config.ts — server.port', () => {
  it('test_dashboard_vite_port_defaults_to_5179_when_env_unset', async () => {
    const cfg = await loadConfig();
    expect(cfg.server.port).toBe(5179);
  });

  it('test_dashboard_vite_port_reads_dashboard_port_env', async () => {
    process.env.DASHBOARD_PORT = '5189';
    const cfg = await loadConfig();
    expect(cfg.server.port).toBe(5189);
  });

  it('test_dashboard_vite_port_falls_back_on_non_numeric_env', async () => {
    process.env.DASHBOARD_PORT = 'abc';
    const cfg = await loadConfig();
    expect(cfg.server.port).toBe(5179);
  });

  it('test_dashboard_vite_port_falls_back_on_zero_env', async () => {
    process.env.DASHBOARD_PORT = '0';
    const cfg = await loadConfig();
    expect(cfg.server.port).toBe(5179);
  });
});

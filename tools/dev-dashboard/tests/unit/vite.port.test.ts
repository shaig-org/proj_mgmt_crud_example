import { describe, it, expect } from 'vitest';
import { pickDashboardPort, DASHBOARD_PORT_DEFAULT } from '../../vite.port';

// Unit tests for the pure port-resolution function used by vite.config.ts
// (per-worktree ports, docs/tasks/per-worktree-ports/plan.md §4.5).
//
// These tests deliberately avoid importing vite.config.ts — doing so would
// trigger `loadEnv` against the worktree's real .env.local at module-load
// time, producing false failures whenever DASHBOARD_PORT is set in the
// environment. The seam between "read the env" and "decide the port" lives
// at the vite.config.ts callsite; this file tests only the decision half.

describe('pickDashboardPort', () => {
  it('test_picks_default_when_input_is_undefined', () => {
    expect(pickDashboardPort(undefined)).toBe(DASHBOARD_PORT_DEFAULT);
  });

  it('test_picks_default_when_input_is_empty_string', () => {
    expect(pickDashboardPort('')).toBe(DASHBOARD_PORT_DEFAULT);
  });

  it('test_picks_numeric_env_value', () => {
    expect(pickDashboardPort('5189')).toBe(5189);
  });

  it('test_falls_back_on_non_numeric', () => {
    expect(pickDashboardPort('abc')).toBe(DASHBOARD_PORT_DEFAULT);
  });

  it('test_falls_back_on_zero', () => {
    expect(pickDashboardPort('0')).toBe(DASHBOARD_PORT_DEFAULT);
  });

  it('test_falls_back_on_negative', () => {
    expect(pickDashboardPort('-42')).toBe(DASHBOARD_PORT_DEFAULT);
  });
});

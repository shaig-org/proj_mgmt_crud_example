/**
 * Meta-test for the scenarioTest fixture itself.
 *
 * The first `scenarioTest` runs a trivial UI flow and records its slug +
 * observed correlation ID into a module-local `shared` object. Subsequent
 * plain `test` blocks (in the same serial describe) read those artifacts
 * from disk and assert the fixture's contract.
 */

import { test, expect } from '@playwright/test';
import { promises as fs } from 'node:fs';
import * as path from 'node:path';
import { scenarioTest, WALKTHROUGHS_DIR, type ScenarioMetadata } from '../helpers/scenario';

interface SharedState {
  slug: string;
  correlationIdSeen: string;
}

const shared: SharedState = { slug: '', correlationIdSeen: '' };

test.describe.configure({ mode: 'serial' });

test.describe('scenarioTest fixture contract', () => {
  scenarioTest(
    'fixture smoketest scenario with two steps',
    async ({ page, step, correlationId, scenarioSlug }) => {
      shared.slug = scenarioSlug;
      await step('open login page', async () => {
        await page.goto('/login');
        await expect(page.getByRole('textbox', { name: 'Username' })).toBeVisible();
      });
      await step('read correlation id from window', async () => {
        const cid = await page.evaluate(() => {
          return (window as unknown as { __CORRELATION_ID?: string }).__CORRELATION_ID ?? '';
        });
        shared.correlationIdSeen = cid;
        expect(cid).toBe(correlationId);
        expect(cid.length).toBeGreaterThan(0);
      });
    },
  );

  test('scenario_fixture_produces_numbered_screenshots_per_step', async () => {
    expect(shared.slug.length).toBeGreaterThan(0);
    const dir = path.join(WALKTHROUGHS_DIR, 'screenshots', shared.slug);
    const files = await fs.readdir(dir);
    const pngs = files.filter((f) => /^\d{2}-.+\.png$/.test(f)).sort();
    expect(pngs.length).toBe(2);
    expect(pngs[0]).toMatch(/^01-/);
    expect(pngs[1]).toMatch(/^02-/);
  });

  test('scenario_fixture_writes_metadata_json_with_expected_fields', async () => {
    const metadataPath = path.join(WALKTHROUGHS_DIR, 'metadata', `${shared.slug}.json`);
    const raw = await fs.readFile(metadataPath, 'utf8');
    const meta = JSON.parse(raw) as ScenarioMetadata;
    expect(meta.name.length).toBeGreaterThan(0);
    expect(meta.slug).toBe(shared.slug);
    expect(meta.correlationId.length).toBeGreaterThan(0);
    expect(Array.isArray(meta.steps)).toBe(true);
    expect(meta.steps.length).toBe(2);
    expect(meta.status).toBeDefined();
    expect(Object.prototype.hasOwnProperty.call(meta, 'videoPath')).toBe(true);
    expect(Object.prototype.hasOwnProperty.call(meta, 'tracePath')).toBe(true);
  });

  test('scenario_fixture_injects_correlation_id_into_window', () => {
    expect(shared.correlationIdSeen.length).toBeGreaterThan(0);
    expect(shared.correlationIdSeen).toMatch(/-w\d+$/);
  });

  test('scenario_fixture_copies_video_and_trace_to_stable_paths', async () => {
    const videoPath = path.join(WALKTHROUGHS_DIR, 'videos', `${shared.slug}.webm`);
    const tracePath = path.join(WALKTHROUGHS_DIR, 'traces', `${shared.slug}.zip`);
    const videoStat = await fs.stat(videoPath);
    const traceStat = await fs.stat(tracePath);
    expect(videoStat.size).toBeGreaterThan(0);
    expect(traceStat.size).toBeGreaterThan(0);
  });

  test('scenario_fixture_slug_is_parallel_safe', () => {
    expect(shared.slug).toMatch(/-w\d+$/);
    expect(shared.slug).toMatch(/-\d{10,}-w\d+$/);
  });
});

/**
 * Scenario test fixture.
 *
 * Wraps Playwright `test` with a `step(name, fn)` helper that auto-numbers
 * and captures a screenshot after each step, and emits one metadata JSON
 * per scenario run under `frontend/walkthroughs/metadata/<slug>.json`.
 *
 * Outputs (all under `frontend/walkthroughs/`):
 *   screenshots/<slug>/NN-<step>.png
 *   videos/<slug>.webm
 *   traces/<slug>.zip
 *   metadata/<slug>.json
 */

import { test as base, expect, type Page, type TestInfo } from '@playwright/test';
import { promises as fs } from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export const WALKTHROUGHS_DIR = path.resolve(__dirname, '..', '..', 'walkthroughs');

export interface ScenarioStepRecord {
  index: number;
  name: string;
  slug: string;
  screenshot: string;
  startedAt: string;
  durationMs: number;
  status: 'passed' | 'failed';
  url: string;
}

export interface ScenarioMetadata {
  name: string;
  slug: string;
  specFile: string;
  correlationId: string;
  startedAt: string;
  endedAt: string;
  durationMs: number;
  status: 'passed' | 'failed' | 'timedout' | 'skipped' | 'interrupted';
  steps: ScenarioStepRecord[];
  videoPath: string | null;
  tracePath: string | null;
}

export type ScenarioStepFn = (name: string, fn: () => Promise<void>) => Promise<void>;

export interface ScenarioFixtures {
  step: ScenarioStepFn;
  correlationId: string;
  scenarioSlug: string;
  /**
   * Automatic fixture that flushes metadata/video/trace AFTER Playwright
   * finalizes its attachments. Do not reference this from test bodies.
   */
  _scenarioArtifactWriter: void;
}

export function slugify(input: string): string {
  return input
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80) || 'scenario';
}

async function ensureDir(dir: string): Promise<void> {
  await fs.mkdir(dir, { recursive: true });
}

async function copyIfExists(from: string, to: string): Promise<boolean> {
  try {
    await fs.copyFile(from, to);
    return true;
  } catch {
    return false;
  }
}

async function waitForFile(filePath: string, timeoutMs: number): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const stat = await fs.stat(filePath);
      if (stat.size > 0) return true;
    } catch {
      // not yet
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  return false;
}

interface StepCollectorState {
  steps: ScenarioStepRecord[];
  startedAt: number;
}

class StepCollector {
  readonly state: StepCollectorState;
  constructor(
    private readonly page: Page,
    private readonly scenarioSlug: string,
  ) {
    this.state = { steps: [], startedAt: Date.now() };
  }

  async run(name: string, fn: () => Promise<void>): Promise<void> {
    const index = this.state.steps.length + 1;
    const stepSlug = slugify(name);
    const nn = String(index).padStart(2, '0');
    const screenshotRel = path.posix.join('screenshots', this.scenarioSlug, `${nn}-${stepSlug}.png`);
    const screenshotAbs = path.join(WALKTHROUGHS_DIR, 'screenshots', this.scenarioSlug, `${nn}-${stepSlug}.png`);
    const startedAtMs = Date.now();
    const startedAt = new Date(startedAtMs).toISOString();
    let status: 'passed' | 'failed' = 'passed';

    // Inject / update a fixed banner showing the step name. Persists during
    // the step's actions (so the recorded video shows it) and gets overwritten
    // by the next step. The label is rendered via a `::before` pseudo-element
    // reading `content: attr(data-label)` rather than as a real text node, so
    // page.getByText() and other DOM-text selectors used by tests cannot
    // accidentally match the banner's caption. Tolerate the rare case where
    // the page hasn't loaded a document yet (very first step before the
    // first goto) — best effort.
    try {
      await this.page.evaluate(
        ({ index: i, name: n }: { index: number; name: string }) => {
          const BANNER_ID = '__scenario-step-banner';
          const STYLE_ID = '__scenario-step-banner-style';
          let style = document.getElementById(STYLE_ID) as HTMLStyleElement | null;
          if (!style) {
            style = document.createElement('style');
            style.id = STYLE_ID;
            // The pseudo-element renders the data-label, so no text node
            // exists in the document tree for Playwright text selectors to
            // hit. The banner div itself stays empty.
            style.textContent =
              `#${BANNER_ID}{position:fixed;top:0;left:0;right:0;` +
              `background:rgba(15,23,42,0.92);color:#fff;` +
              `padding:8px 16px;font:600 16px/1.35 system-ui,sans-serif;` +
              `z-index:2147483647;pointer-events:none;` +
              `box-shadow:0 1px 4px rgba(0,0,0,0.3);}` +
              `#${BANNER_ID}::before{content:attr(data-label);}`;
            document.head.appendChild(style);
          }
          let el = document.getElementById(BANNER_ID);
          if (!el) {
            el = document.createElement('div');
            el.id = BANNER_ID;
            el.setAttribute('aria-hidden', 'true');
            document.body.appendChild(el);
          }
          el.setAttribute('data-label', `Step ${i}: ${n}`);
        },
        { index, name },
      );
    } catch {
      // No live document yet (or page closed); not fatal — caption will appear
      // on subsequent steps once the test navigates.
    }

    try {
      await base.step(name, fn);
    } catch (err) {
      status = 'failed';
      let url = '';
      try {
        url = this.page.url();
      } catch {
        // best effort
      }
      try {
        await ensureDir(path.dirname(screenshotAbs));
        await this.page.screenshot({ path: screenshotAbs, fullPage: false });
      } catch {
        // best effort
      }
      this.state.steps.push({
        index,
        name,
        slug: stepSlug,
        screenshot: screenshotRel,
        startedAt,
        durationMs: Date.now() - startedAtMs,
        status,
        url,
      });
      throw err;
    }
    let url = '';
    try {
      url = this.page.url();
    } catch {
      // best effort
    }
    try {
      await ensureDir(path.dirname(screenshotAbs));
      await this.page.screenshot({ path: screenshotAbs, fullPage: false });
    } catch {
      // best effort
    }
    this.state.steps.push({
      index,
      name,
      slug: stepSlug,
      screenshot: screenshotRel,
      startedAt,
      durationMs: Date.now() - startedAtMs,
      status,
      url,
    });
  }
}

async function collectVideoAndTrace(
  page: Page,
  testInfo: TestInfo,
  scenarioSlug: string,
): Promise<{ videoPath: string | null; tracePath: string | null }> {
  const videosDir = path.join(WALKTHROUGHS_DIR, 'videos');
  const tracesDir = path.join(WALKTHROUGHS_DIR, 'traces');
  await ensureDir(videosDir);
  await ensureDir(tracesDir);

  let videoPath: string | null = null;
  try {
    const video = page.video();
    if (video) {
      const srcPath = await video.path();
      const destPath = path.join(videosDir, `${scenarioSlug}.webm`);
      if (await copyIfExists(srcPath, destPath)) {
        videoPath = path.posix.join('videos', `${scenarioSlug}.webm`);
      }
    }
  } catch {
    // tolerate missing video
  }

  let tracePath: string | null = null;
  const destPath = path.join(tracesDir, `${scenarioSlug}.zip`);
  const traceAttachment = testInfo.attachments.find((a) => a.name === 'trace' && typeof a.path === 'string');
  const candidates: string[] = [];
  if (traceAttachment?.path) candidates.push(traceAttachment.path);
  candidates.push(path.join(testInfo.outputDir, 'trace.zip'));
  // Playwright may still be flushing the trace when our teardown runs.
  // Poll briefly for the first candidate path that appears.
  for (const src of candidates) {
    if (await waitForFile(src, 5000)) {
      if (await copyIfExists(src, destPath)) {
        tracePath = path.posix.join('traces', `${scenarioSlug}.zip`);
        break;
      }
    }
  }

  return { videoPath, tracePath };
}

async function writeMetadata(metadata: ScenarioMetadata): Promise<void> {
  const metadataDir = path.join(WALKTHROUGHS_DIR, 'metadata');
  await ensureDir(metadataDir);
  const outPath = path.join(metadataDir, `${metadata.slug}.json`);
  await fs.writeFile(outPath, JSON.stringify(metadata, null, 2), 'utf8');
}

interface PendingScenario {
  slug: string;
  correlationId: string;
  startedAt: string;
  startedAtMs: number;
  collector: StepCollector;
  page: Page;
  flushedTracePath: string | null;
}

// Keyed by testInfo.testId; populated during fixture setup, consumed in afterEach.
// Module-level but safe under Playwright parallelism: each worker runs in its
// own Node process, so this Map is per-worker (not shared across workers).
const PENDING: Map<string, PendingScenario> = new Map();

export const scenarioTest = base.extend<ScenarioFixtures>({
  // eslint-disable-next-line no-empty-pattern
  correlationId: async ({}, use, testInfo) => {
    const titleSlug = slugify(testInfo.title);
    const cid = `${titleSlug}-${Date.now()}-w${testInfo.workerIndex}`;
    // eslint-disable-next-line react-hooks/rules-of-hooks
    await use(cid);
  },
  scenarioSlug: async ({ correlationId }, use) => {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    await use(correlationId);
  },
  // Automatic fixture declared BEFORE `step` in the dependency graph so that
  // its teardown runs LAST — after Playwright has finalized the trace.zip
  // attachment on context close.
  _scenarioArtifactWriter: [
    // eslint-disable-next-line no-empty-pattern
    async ({}, use, testInfo) => {
      await use();
      // Teardown: look up the pending entry populated by the `step` fixture.
      const pending = PENDING.get(testInfo.testId);
      if (!pending) return;
      PENDING.delete(testInfo.testId);

      const endedAtMs = Date.now();
      const endedAt = new Date(endedAtMs).toISOString();

      const { videoPath, tracePath: fallbackTracePath } = await collectVideoAndTrace(pending.page, testInfo, pending.slug);
      const tracePath = pending.flushedTracePath ?? fallbackTracePath;
      const status = testInfo.status ?? 'passed';
      const metadata: ScenarioMetadata = {
        name: testInfo.title,
        slug: pending.slug,
        specFile: path.relative(path.resolve(__dirname, '..', '..'), testInfo.file),
        correlationId: pending.correlationId,
        startedAt: pending.startedAt,
        endedAt,
        durationMs: endedAtMs - pending.startedAtMs,
        status,
        steps: pending.collector.state.steps,
        videoPath,
        tracePath,
      };
      await writeMetadata(metadata);
    },
    { auto: true },
  ],
  step: async ({ page, correlationId, scenarioSlug, _scenarioArtifactWriter }, use, testInfo) => {
    void _scenarioArtifactWriter;
    // Start tracing manually so we can flush to a stable path on teardown.
    try {
      await page.context().tracing.start({ screenshots: true, snapshots: true, sources: true });
    } catch {
      // already started / not supported
    }
    // Inject correlation ID into window before any navigation.
    await page.addInitScript((cid: string) => {
      (window as unknown as { __CORRELATION_ID: string }).__CORRELATION_ID = cid;
    }, correlationId);

    // Inject a click-ripple effect on every mousedown so synthetic Playwright
    // clicks are visible in the recorded video and the per-step screenshots.
    // Uses capture phase + addEventListener so we observe every click,
    // pointer-events:none and a near-max z-index so the ripple never
    // intercepts test interactions or hides the click target.
    await page.addInitScript(() => {
      document.addEventListener(
        'mousedown',
        (e: MouseEvent) => {
          const r = document.createElement('div');
          r.style.cssText = [
            'position:fixed',
            `left:${e.clientX}px`,
            `top:${e.clientY}px`,
            'width:0', 'height:0',
            'border-radius:50%',
            'background:rgba(239,68,68,0.55)',
            'border:2px solid rgba(239,68,68,0.9)',
            'transform:translate(-50%,-50%)',
            'pointer-events:none',
            'z-index:2147483646',
            'transition:width 0.45s ease-out, height 0.45s ease-out, opacity 0.45s ease-out',
          ].join(';');
          document.body.appendChild(r);
          requestAnimationFrame(() => {
            r.style.width = '64px';
            r.style.height = '64px';
            r.style.opacity = '0';
          });
          setTimeout(() => r.remove(), 600);
        },
        true,
      );
    });

    const collector = new StepCollector(page, scenarioSlug);
    const startedAtMs = Date.now();
    const startedAt = new Date(startedAtMs).toISOString();

    PENDING.set(testInfo.testId, {
      slug: scenarioSlug,
      correlationId,
      startedAt,
      startedAtMs,
      collector,
      page,
      flushedTracePath: null,
    });

    const stepFn: ScenarioStepFn = (name, fn) => collector.run(name, fn);
    // eslint-disable-next-line react-hooks/rules-of-hooks
    await use(stepFn);

    // Stop tracing and flush to stable path BEFORE context close / fixture
    // teardown so `walkthroughs/traces/<slug>.zip` is available for in-run
    // assertions and downstream tooling.
    try {
      const tracesDir = path.join(WALKTHROUGHS_DIR, 'traces');
      await ensureDir(tracesDir);
      const traceDest = path.join(tracesDir, `${scenarioSlug}.zip`);
      await page.context().tracing.stop({ path: traceDest });
      const pending = PENDING.get(testInfo.testId);
      if (pending) pending.flushedTracePath = path.posix.join('traces', `${scenarioSlug}.zip`);
    } catch {
      // tolerate tracing failures
    }
    try {
      await page.context().close();
    } catch {
      // already closed / test failed
    }
  },
});


export { expect };

import { test as base, expect } from '@playwright/test';
import { promises as fs } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const DASHBOARD_DIR = path.resolve(here, '..', '..');
const FIXTURES = path.resolve(here, '..', 'fixtures');
const TMP_REPO = path.resolve(here, '..', '.tmp-repo');

export type AspectId = 'scenarios' | 'capabilities' | 'traces';

export interface Layout {
  scenarios: boolean;
  capabilities: boolean;
  /** 'none' | 'baseline-only' | 'full' */
  capabilitiesMode?: 'none' | 'baseline-only' | 'full';
  traces: boolean;
}

async function copyDir(src: string, dst: string): Promise<void> {
  await fs.mkdir(dst, { recursive: true });
  const entries = await fs.readdir(src, { withFileTypes: true });
  for (const e of entries) {
    const a = path.join(src, e.name);
    const b = path.join(dst, e.name);
    if (e.isDirectory()) await copyDir(a, b);
    else await fs.copyFile(a, b);
  }
}

async function rmrf(p: string): Promise<void> {
  await fs.rm(p, { recursive: true, force: true });
}

/**
 * Prepare a tmp "repo-root" under the dashboard dir whose
 *   frontend/walkthroughs/gallery,
 *   backend/evidence/capabilities,
 *   backend/.trace-artifacts
 * dirs are populated (or not) from fixtures. Writes a valid .staleness.json.
 */
export async function withArtifacts(
  layout: Layout,
  staleAspect?: AspectId,
): Promise<void> {
  await rmrf(TMP_REPO);
  await fs.mkdir(TMP_REPO, { recursive: true });
  // Mark as a fake repo so resolveRepoRoot stops here.
  await fs.mkdir(path.join(TMP_REPO, '.git'), { recursive: true });

  // Also create the source root dirs so staleness has something to walk.
  await fs.mkdir(path.join(TMP_REPO, 'frontend/e2e/scenarios'), { recursive: true });
  await fs.mkdir(
    path.join(TMP_REPO, 'backend/project_management_crud_example/routers'),
    { recursive: true },
  );
  await fs.mkdir(path.join(TMP_REPO, 'backend/tests'), { recursive: true });

  // Always write at least one source file per aspect so mtimes are computable.
  const now = Date.now();
  const oldMs = now - 10 * 60 * 1000;
  const scenSrc = path.join(TMP_REPO, 'frontend/e2e/scenarios/org_create.scenario.spec.ts');
  await fs.writeFile(scenSrc, '// stub\n');
  await fs.utimes(scenSrc, new Date(oldMs) as unknown as Date, new Date(oldMs) as unknown as Date);

  const capSrc = path.join(
    TMP_REPO,
    'backend/project_management_crud_example/routers/stub_router.py',
  );
  await fs.writeFile(capSrc, '# stub\n');
  await fs.utimes(capSrc, new Date(oldMs) as unknown as Date, new Date(oldMs) as unknown as Date);

  const traceSrc = path.join(TMP_REPO, 'backend/tests/test_stub.py');
  await fs.writeFile(traceSrc, '# stub\n');
  await fs.utimes(traceSrc, new Date(oldMs) as unknown as Date, new Date(oldMs) as unknown as Date);

  if (layout.scenarios) {
    const dst = path.join(TMP_REPO, 'frontend/walkthroughs/gallery');
    await copyDir(path.join(FIXTURES, 'scenarios'), dst);
  }
  if (layout.capabilities) {
    const dst = path.join(TMP_REPO, 'backend/evidence/capabilities');
    await fs.mkdir(dst, { recursive: true });
    await fs.copyFile(
      path.join(FIXTURES, 'capabilities/baseline.json'),
      path.join(dst, 'baseline.json'),
    );
    if ((layout.capabilitiesMode ?? 'full') === 'full') {
      await fs.copyFile(
        path.join(FIXTURES, 'capabilities/report.json'),
        path.join(dst, 'report.json'),
      );
    }
  }
  if (layout.traces) {
    const dst = path.join(TMP_REPO, 'backend/.trace-artifacts');
    await copyDir(path.join(FIXTURES, 'traces'), dst);
  }

  // Build and write .staleness.json using the real script logic, then optionally
  // bump one source mtime to trigger stale for that aspect.
  if (staleAspect === 'scenarios') {
    await fs.utimes(scenSrc, new Date() as unknown as Date, new Date(now + 60_000) as unknown as Date);
  } else if (staleAspect === 'capabilities') {
    await fs.utimes(capSrc, new Date() as unknown as Date, new Date(now + 60_000) as unknown as Date);
  } else if (staleAspect === 'traces') {
    await fs.utimes(traceSrc, new Date() as unknown as Date, new Date(now + 60_000) as unknown as Date);
  }

  const mod = (await import('../../scripts/check-staleness.mjs')) as {
    computeStaleness: (repoRoot: string) => Promise<unknown>;
  };
  const doc = await mod.computeStaleness(TMP_REPO);
  await fs.writeFile(
    path.join(DASHBOARD_DIR, '.staleness.json'),
    JSON.stringify(doc, null, 2),
  );
}

/**
 * Prepare the tmp repo with a subset of REAL pytest-tracer artifacts
 * copied from `<repo>/backend/.trace-artifacts/`. Validates that the
 * dashboard works against the actual producer schema (notably the
 * `folded-compact.txt` filename vs the legacy `folded.txt`).
 *
 * Locates the real repo by walking up from the dashboard dir looking
 * for a sibling `backend/.trace-artifacts` directory with at least one
 * per-scenario subdirectory.
 */
export async function withRealTraceArtifacts(): Promise<string[]> {
  await rmrf(TMP_REPO);
  await fs.mkdir(TMP_REPO, { recursive: true });
  await fs.mkdir(path.join(TMP_REPO, '.git'), { recursive: true });
  await fs.mkdir(path.join(TMP_REPO, 'frontend/e2e/scenarios'), {
    recursive: true,
  });
  await fs.mkdir(
    path.join(TMP_REPO, 'backend/project_management_crud_example/routers'),
    { recursive: true },
  );
  await fs.mkdir(path.join(TMP_REPO, 'backend/tests'), { recursive: true });

  // Walk up to find the real repo's backend/.trace-artifacts.
  let realRoot = DASHBOARD_DIR;
  let realTraces: string | null = null;
  for (let i = 0; i < 10; i++) {
    const candidate = path.join(realRoot, 'backend/.trace-artifacts');
    try {
      const s = await fs.stat(candidate);
      if (s.isDirectory()) {
        realTraces = candidate;
        break;
      }
    } catch {
      /* walk */
    }
    const parent = path.dirname(realRoot);
    if (parent === realRoot) break;
    realRoot = parent;
  }
  if (!realTraces) {
    throw new Error(
      'Could not locate real backend/.trace-artifacts under parents of the dashboard dir.',
    );
  }
  const entries = await fs.readdir(realTraces, { withFileTypes: true });
  const dirs = entries.filter((e) => e.isDirectory()).map((e) => e.name);
  if (dirs.length === 0) {
    throw new Error(
      `Real ${realTraces} contains no per-scenario subdirectories.`,
    );
  }
  const dst = path.join(TMP_REPO, 'backend/.trace-artifacts');
  await fs.mkdir(dst, { recursive: true });
  // Copy up to 3 scenarios to keep the smoke fast.
  const picked = dirs.slice(0, 3);
  for (const name of picked) {
    await copyDir(path.join(realTraces, name), path.join(dst, name));
  }

  // Minimal stub sources for staleness.
  const traceSrc = path.join(TMP_REPO, 'backend/tests/test_stub.py');
  await fs.writeFile(traceSrc, '# stub\n');

  const mod = (await import('../../scripts/check-staleness.mjs')) as {
    computeStaleness: (repoRoot: string) => Promise<unknown>;
  };
  const doc = await mod.computeStaleness(TMP_REPO);
  await fs.writeFile(
    path.join(DASHBOARD_DIR, '.staleness.json'),
    JSON.stringify(doc, null, 2),
  );
  return picked;
}

export const test = base.extend({});
export { expect };

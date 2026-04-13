#!/usr/bin/env node
// Walks each aspect's sourceRoots and primary artifact, writes
// tools/dev-dashboard/.staleness.json.
//
// Run via:  npm --prefix tools/dev-dashboard run dashboard:check
// Invoked automatically as predashboard.

import { promises as fs } from 'node:fs';
import path from 'node:path';
import url from 'node:url';
import { aspectsConfig } from './aspects.config.mjs';

const IGNORED_DIRS = new Set([
  'node_modules',
  '.git',
  'dist',
  '__pycache__',
  '.trace-index',
  '.venv',
  '.pytest_cache',
  'playwright-report',
  'test-results',
]);

/**
 * Walk up from `start` until a `.git` entry exists. Return the directory
 * containing it, or fall back to `<start>/../..`.
 * @param {string} start
 * @returns {Promise<string>}
 */
export async function resolveRepoRoot(start) {
  let dir = path.resolve(start);
  for (let i = 0; i < 10; i++) {
    try {
      await fs.stat(path.join(dir, '.git'));
      return dir;
    } catch {
      /* keep walking */
    }
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return path.resolve(start, '..', '..');
}

/**
 * Recursively walk `root`, returning {mtimeMs, file} for the newest file.
 * Returns null if root does not exist or contains no files.
 * @param {string} root absolute path
 * @returns {Promise<{mtimeMs: number, file: string} | null>}
 */
export async function newestFileUnder(root) {
  let best = null;
  async function walk(dir) {
    let entries;
    try {
      entries = await fs.readdir(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const e of entries) {
      if (IGNORED_DIRS.has(e.name)) continue;
      const full = path.join(dir, e.name);
      if (e.isDirectory()) {
        await walk(full);
      } else if (e.isFile()) {
        try {
          const s = await fs.stat(full);
          if (!best || s.mtimeMs > best.mtimeMs) {
            best = { mtimeMs: s.mtimeMs, file: full };
          }
        } catch {
          /* ignore */
        }
      }
    }
  }
  await walk(root);
  return best;
}

/**
 * Stat the primary artifact. Returns mtime (ms) or null if missing.
 * For dir-typed primary artifacts (traces), returns mtime of the directory
 * itself (newest child). Missing is distinct from stale.
 * @param {string} fsAbs
 * @returns {Promise<{mtimeMs: number, exists: true} | {mtimeMs: null, exists: false}>}
 */
export async function statPrimaryArtifact(fsAbs) {
  try {
    const s = await fs.stat(fsAbs);
    if (s.isDirectory()) {
      const newest = await newestFileUnder(fsAbs);
      if (!newest) return { mtimeMs: s.mtimeMs, exists: true };
      return { mtimeMs: newest.mtimeMs, exists: true };
    }
    return { mtimeMs: s.mtimeMs, exists: true };
  } catch {
    return { mtimeMs: null, exists: false };
  }
}

/**
 * Compute staleness for a single aspect.
 * @param {import('./aspects.config.mjs').AspectConfig} aspect
 * @param {string} repoRoot absolute
 */
export async function computeAspectStaleness(aspect, repoRoot) {
  const primary = aspect.artifacts[0];
  const artifactAbs = path.resolve(repoRoot, primary.fsPath);
  const artifactStat = await statPrimaryArtifact(artifactAbs);

  let newestSourceMtime = null;
  let newestSourceFile = null;
  for (const root of aspect.sourceRoots) {
    const rootAbs = path.resolve(repoRoot, root);
    const n = await newestFileUnder(rootAbs);
    if (n && (newestSourceMtime === null || n.mtimeMs > newestSourceMtime)) {
      newestSourceMtime = n.mtimeMs;
      newestSourceFile = path.relative(repoRoot, n.file);
    }
  }

  const stale =
    artifactStat.exists &&
    newestSourceMtime !== null &&
    artifactStat.mtimeMs !== null &&
    newestSourceMtime > artifactStat.mtimeMs;

  return {
    primaryArtifactExists: artifactStat.exists,
    primaryArtifactMtime:
      artifactStat.mtimeMs === null ? null : new Date(artifactStat.mtimeMs).toISOString(),
    newestSourceMtime:
      newestSourceMtime === null ? null : new Date(newestSourceMtime).toISOString(),
    newestSourceFile,
    stale,
  };
}

/**
 * Compute the full staleness document.
 * @param {string} repoRoot
 * @param {import('./aspects.config.mjs').AspectConfig[]} aspects
 */
export async function computeStaleness(repoRoot, aspects = aspectsConfig) {
  /** @type {Record<string, unknown>} */
  const out = {};
  for (const aspect of aspects) {
    out[aspect.id] = await computeAspectStaleness(aspect, repoRoot);
  }
  return {
    generatedAt: new Date().toISOString(),
    repoRoot,
    aspects: out,
  };
}

async function main() {
  const thisFile = url.fileURLToPath(import.meta.url);
  const scriptDir = path.dirname(thisFile);
  const dashboardDir = path.resolve(scriptDir, '..');
  const repoRoot = await resolveRepoRoot(dashboardDir);
  const doc = await computeStaleness(repoRoot);
  const outPath = path.resolve(dashboardDir, '.staleness.json');
  await fs.writeFile(outPath, JSON.stringify(doc, null, 2) + '\n', 'utf8');
  console.warn(`[dev-dashboard] staleness written to ${outPath}`);
}

if (import.meta.url === url.pathToFileURL(process.argv[1]).href) {
  main().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}

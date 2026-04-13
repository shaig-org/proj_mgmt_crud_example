#!/usr/bin/env tsx
/**
 * Evidence generator — dev-time tooling.
 *
 * Reads per-scenario metadata JSONs from `frontend/evidence/metadata/`,
 * videos from `frontend/evidence/videos/`, and produces:
 *   - `frontend/evidence/gallery/gifs/<slug>.gif` (5–8 s target, 640px, 10 fps)
 *   - `frontend/evidence/gallery/manifest.json`
 *   - `frontend/evidence/gallery/index.html`, `viewer.js`, `viewer.css`
 *     (copied from `frontend/src-evidence-gallery/`)
 *
 * Requires `ffmpeg` and `ffprobe` on PATH. Exits 1 on ffmpeg failure.
 */

import { execFile } from 'node:child_process';
import { promises as fs } from 'node:fs';
import * as path from 'node:path';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';

const execFileP = promisify(execFile);

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const FRONTEND_ROOT = path.resolve(__dirname, '..');
const EVIDENCE_DIR = path.join(FRONTEND_ROOT, 'evidence');
const METADATA_DIR = path.join(EVIDENCE_DIR, 'metadata');
const SCREENSHOTS_DIR = path.join(EVIDENCE_DIR, 'screenshots');
const GALLERY_DIR = path.join(EVIDENCE_DIR, 'gallery');
const GALLERY_GIFS_DIR = path.join(GALLERY_DIR, 'gifs');
const GALLERY_SCREENSHOTS_DIR = path.join(GALLERY_DIR, 'screenshots');
const VIEWER_SOURCE_DIR = path.join(FRONTEND_ROOT, 'src-evidence-gallery');

interface StepRecord {
  index: number;
  name: string;
  slug: string;
  screenshot: string;
  startedAt: string;
  durationMs: number;
  status: string;
}

interface RawMetadata {
  name: string;
  slug: string;
  specFile: string;
  correlationId: string;
  startedAt: string;
  endedAt: string;
  durationMs: number;
  status: string;
  steps: StepRecord[];
  videoPath: string | null;
  tracePath: string | null;
}

interface ManifestEntry extends RawMetadata {
  gifPath: string | null;
  feature: string;
}

async function ensureDir(dir: string): Promise<void> {
  await fs.mkdir(dir, { recursive: true });
}

async function rmDir(dir: string): Promise<void> {
  await fs.rm(dir, { recursive: true, force: true });
}

async function readMetadataFiles(): Promise<RawMetadata[]> {
  let files: string[] = [];
  try {
    files = await fs.readdir(METADATA_DIR);
  } catch {
    return [];
  }
  const jsons = files.filter((f) => f.endsWith('.json'));
  const results: RawMetadata[] = [];
  for (const f of jsons) {
    const raw = await fs.readFile(path.join(METADATA_DIR, f), 'utf8');
    try {
      results.push(JSON.parse(raw) as RawMetadata);
    } catch (err) {
      console.warn(`[evidence] skipping malformed metadata ${f}: ${String(err)}`);
    }
  }
  return results;
}

async function probeVideoDurationSec(videoPath: string): Promise<number | null> {
  try {
    const { stdout } = await execFileP('ffprobe', [
      '-v', 'error',
      '-show_entries', 'format=duration',
      '-of', 'default=noprint_wrappers=1:nokey=1',
      videoPath,
    ]);
    const secs = parseFloat(stdout.trim());
    return Number.isFinite(secs) && secs > 0 ? secs : null;
  } catch {
    return null;
  }
}

async function renderGif(videoAbsPath: string, gifAbsPath: string): Promise<boolean> {
  const duration = await probeVideoDurationSec(videoAbsPath);
  let speedFilter = '';
  if (duration !== null && duration > 8) {
    const mult = duration / 8;
    speedFilter = `setpts=PTS/${mult.toFixed(4)},`;
  }
  // else: keep natural speed (short or mid-length videos)
  const vf = `${speedFilter}fps=10,scale=640:-1:flags=lanczos`;
  try {
    await execFileP('ffmpeg', [
      '-y',
      '-i', videoAbsPath,
      '-vf', vf,
      '-loop', '0',
      gifAbsPath,
    ]);
    return true;
  } catch (err) {
    const e = err as NodeJS.ErrnoException & { stderr?: string };
    if (e.code === 'ENOENT') {
      console.error('[evidence] ffmpeg not found on PATH. Install ffmpeg; this is a dev-only tool.');
      process.exit(1);
    }
    console.warn(`[evidence] ffmpeg failed for ${videoAbsPath}: ${e.stderr ?? e.message}`);
    return false;
  }
}

function inferFeature(specFile: string): string {
  const base = path.basename(specFile).replace(/\.scenario\.spec\.ts$/, '');
  return base.replace(/[-_]/g, ' ');
}

async function copyDirContents(src: string, dest: string): Promise<void> {
  await ensureDir(dest);
  const entries = await fs.readdir(src, { withFileTypes: true });
  for (const e of entries) {
    const s = path.join(src, e.name);
    const d = path.join(dest, e.name);
    if (e.isDirectory()) {
      await copyDirContents(s, d);
    } else {
      await fs.copyFile(s, d);
    }
  }
}

async function main(): Promise<void> {
  const metadataEntries = await readMetadataFiles();
  if (metadataEntries.length === 0) {
    console.error('[evidence] No metadata found under evidence/metadata/. Run `npm run e2e:scenarios` first.');
    process.exit(1);
  }

  // Reset gallery output (but NOT metadata/videos/screenshots inputs)
  await rmDir(GALLERY_DIR);
  await ensureDir(GALLERY_DIR);
  await ensureDir(GALLERY_GIFS_DIR);
  await ensureDir(GALLERY_SCREENSHOTS_DIR);

  // Copy viewer source
  try {
    await copyDirContents(VIEWER_SOURCE_DIR, GALLERY_DIR);
  } catch (err) {
    console.error(`[evidence] failed to copy viewer source from ${VIEWER_SOURCE_DIR}: ${String(err)}`);
    process.exit(1);
  }

  // Copy screenshots into gallery so viewer can reference relative URLs
  try {
    await copyDirContents(SCREENSHOTS_DIR, GALLERY_SCREENSHOTS_DIR);
  } catch {
    // no screenshots yet; tolerate
  }

  const manifest: ManifestEntry[] = [];
  let gifsRendered = 0;
  let gifsSkipped = 0;
  for (const meta of metadataEntries) {
    let gifRel: string | null = null;
    if (meta.videoPath) {
      const videoAbs = path.join(EVIDENCE_DIR, meta.videoPath);
      const gifAbs = path.join(GALLERY_GIFS_DIR, `${meta.slug}.gif`);
      try {
        await fs.access(videoAbs);
        const ok = await renderGif(videoAbs, gifAbs);
        if (ok) {
          gifRel = path.posix.join('gifs', `${meta.slug}.gif`);
          gifsRendered += 1;
        } else {
          gifsSkipped += 1;
        }
      } catch {
        console.warn(`[evidence] video missing for slug ${meta.slug}, skipping GIF`);
        gifsSkipped += 1;
      }
    } else {
      console.warn(`[evidence] no video recorded for slug ${meta.slug}, skipping GIF`);
      gifsSkipped += 1;
    }

    manifest.push({
      ...meta,
      gifPath: gifRel,
      feature: inferFeature(meta.specFile),
    });
  }

  manifest.sort((a, b) => a.startedAt.localeCompare(b.startedAt));
  await fs.writeFile(
    path.join(GALLERY_DIR, 'manifest.json'),
    JSON.stringify({ generatedAt: new Date().toISOString(), scenarios: manifest }, null, 2),
    'utf8',
  );

  console.log(`[evidence] wrote manifest with ${manifest.length} scenario(s) to ${GALLERY_DIR}`);
  console.log(`[evidence] ${gifsRendered} GIFs rendered, ${gifsSkipped} skipped`);
  console.log(`[evidence] open ${path.join(GALLERY_DIR, 'index.html')} or run \`npm run evidence:serve\``);
}

main().catch((err: unknown) => {
  console.error('[evidence] fatal:', err);
  process.exit(1);
});

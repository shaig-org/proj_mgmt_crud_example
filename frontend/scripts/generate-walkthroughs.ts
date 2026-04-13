#!/usr/bin/env tsx
/**
 * Walkthroughs generator — dev-time tooling.
 *
 * Reads per-scenario metadata JSONs from `frontend/walkthroughs/metadata/`,
 * videos from `frontend/walkthroughs/videos/`, and produces:
 *   - `frontend/walkthroughs/gallery/gifs/<slug>.gif`         (flipbook, 5 fps, one frame per step)
 *   - `frontend/walkthroughs/gallery/gifs/<slug>-motion.gif`  (video-derived, 5 fps, slowed down)
 *   - `frontend/walkthroughs/gallery/videos/<slug>.webm`      (original Playwright recording)
 *   - `frontend/walkthroughs/gallery/manifest.json`
 *   - `frontend/walkthroughs/gallery/index.html`, `viewer.js`, `viewer.css`
 *     (copied from `frontend/src-walkthroughs-dashboard/`)
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
const WALKTHROUGHS_DIR = path.join(FRONTEND_ROOT, 'walkthroughs');
const METADATA_DIR = path.join(WALKTHROUGHS_DIR, 'metadata');
const SCREENSHOTS_DIR = path.join(WALKTHROUGHS_DIR, 'screenshots');
const GALLERY_DIR = path.join(WALKTHROUGHS_DIR, 'gallery');
const GALLERY_GIFS_DIR = path.join(GALLERY_DIR, 'gifs');
const GALLERY_SCREENSHOTS_DIR = path.join(GALLERY_DIR, 'screenshots');
const GALLERY_VIDEOS_DIR = path.join(GALLERY_DIR, 'videos');
const VIEWER_SOURCE_DIR = path.join(FRONTEND_ROOT, 'src-walkthroughs-dashboard');

// GIF rendering constants — tune here for comfort.
// Motion GIF: output frame rate and real-time slowdown factor.
// MOTION_SLOWDOWN=2.0 stretches wall-clock time 2x (setpts=2.0*PTS) so
// reviewers can actually follow what happened. MOTION_FPS=3 yields
// ~333ms per frame, comfortable for reading short scenarios.
const MOTION_FPS = 3; // 333ms / frame
const MOTION_SLOWDOWN = 2.0; // 2x slower than real time (setpts multiplier)
// Flipbook GIF: 1.5 s per step screenshot (~0.67 fps) — comfortable scan.
const FLIPBOOK_HOLD_SECONDS = 1.5;
const FLIPBOOK_FPS = 5; // output frame rate for palette/render step
const GIF_WIDTH = 640;

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
  motionGifPath: string | null;
  videoGalleryPath: string | null;
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
      console.warn(`[walkthroughs] skipping malformed metadata ${f}: ${String(err)}`);
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

function handleFfmpegMissing(err: NodeJS.ErrnoException): void {
  if (err.code === 'ENOENT') {
    console.error('[walkthroughs] ffmpeg not found on PATH. Install ffmpeg; this is a dev-only tool.');
    process.exit(1);
  }
}

/**
 * Render a "motion" GIF from the recorded video — slowed down to GIF_FPS so a
 * reviewer can actually see what happened. No total-duration cap.
 */
async function renderMotionGif(videoAbsPath: string, gifAbsPath: string, slug: string): Promise<boolean> {
  const sourceDuration = await probeVideoDurationSec(videoAbsPath);
  // Stretch time by MOTION_SLOWDOWN (setpts=<N>*PTS), then resample to MOTION_FPS.
  // Order matters: setpts first so fps sees the slowed stream.
  const vf =
    `setpts=${MOTION_SLOWDOWN.toFixed(2)}*PTS,fps=${MOTION_FPS},` +
    `scale=${GIF_WIDTH}:-1:flags=lanczos,split[a][b];` +
    `[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5`;
  try {
    await execFileP('ffmpeg', [
      '-y',
      '-i', videoAbsPath,
      '-filter_complex', vf,
      '-loop', '0',
      gifAbsPath,
    ]);
    const renderedDuration = await probeVideoDurationSec(gifAbsPath);
    console.log(
      `[walkthroughs] motion GIF ${slug}: ${MOTION_FPS} fps, ${MOTION_SLOWDOWN}x slowdown, ` +
      `source=${sourceDuration ? sourceDuration.toFixed(2) : '?'}s, ` +
      `gif=${renderedDuration ? renderedDuration.toFixed(2) : '?'}s`
    );
    return true;
  } catch (err) {
    const e = err as NodeJS.ErrnoException & { stderr?: string };
    handleFfmpegMissing(e);
    console.warn(`[walkthroughs] motion ffmpeg failed for ${videoAbsPath}: ${e.stderr ?? e.message}`);
    return false;
  }
}

/**
 * Render a "flipbook" GIF from per-step screenshots — one frame per step,
 * holding each frame for ~1s (5 fps loop with frame duplication via -loop and
 * concat demuxer). This is the primary GIF: a step-by-step comprehension aid.
 */
async function renderFlipbookGif(
  screenshotAbsPaths: string[],
  gifAbsPath: string,
  slug: string,
): Promise<boolean> {
  if (screenshotAbsPaths.length === 0) return false;
  // Use ffmpeg's concat demuxer with explicit per-frame durations (1s each).
  // This is more reliable than relying on input -framerate alone for stills.
  const concatLines: string[] = [];
  for (const p of screenshotAbsPaths) {
    concatLines.push(`file '${p.replace(/'/g, "'\\''")}'`);
    concatLines.push(`duration ${FLIPBOOK_HOLD_SECONDS.toFixed(3)}`);
  }
  // Concat demuxer requires the last file to be repeated without a duration.
  concatLines.push(`file '${screenshotAbsPaths[screenshotAbsPaths.length - 1].replace(/'/g, "'\\''")}'`);
  const concatFile = gifAbsPath + '.concat.txt';
  await fs.writeFile(concatFile, concatLines.join('\n'), 'utf8');
  const vf = `fps=${FLIPBOOK_FPS},scale=${GIF_WIDTH}:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5`;
  try {
    await execFileP('ffmpeg', [
      '-y',
      '-f', 'concat',
      '-safe', '0',
      '-i', concatFile,
      '-filter_complex', vf,
      '-loop', '0',
      gifAbsPath,
    ]);
    const renderedDuration = await probeVideoDurationSec(gifAbsPath);
    console.log(
      `[walkthroughs] flipbook GIF ${slug}: ${FLIPBOOK_FPS} fps, ` +
      `${screenshotAbsPaths.length} steps × ${FLIPBOOK_HOLD_SECONDS}s, ` +
      `gif=${renderedDuration ? renderedDuration.toFixed(2) : '?'}s`
    );
    return true;
  } catch (err) {
    const e = err as NodeJS.ErrnoException & { stderr?: string };
    handleFfmpegMissing(e);
    console.warn(`[walkthroughs] flipbook ffmpeg failed for ${slug}: ${e.stderr ?? e.message}`);
    return false;
  } finally {
    await fs.rm(concatFile, { force: true });
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
    console.error('[walkthroughs] No metadata found under walkthroughs/metadata/. Run `npm run e2e:scenarios` first.');
    process.exit(1);
  }

  // Reset gallery output (but NOT metadata/videos/screenshots inputs)
  await rmDir(GALLERY_DIR);
  await ensureDir(GALLERY_DIR);
  await ensureDir(GALLERY_GIFS_DIR);
  await ensureDir(GALLERY_SCREENSHOTS_DIR);
  await ensureDir(GALLERY_VIDEOS_DIR);

  // Copy viewer source
  try {
    await copyDirContents(VIEWER_SOURCE_DIR, GALLERY_DIR);
  } catch (err) {
    console.error(`[walkthroughs] failed to copy viewer source from ${VIEWER_SOURCE_DIR}: ${String(err)}`);
    process.exit(1);
  }

  // Copy screenshots into gallery so viewer can reference relative URLs
  try {
    await copyDirContents(SCREENSHOTS_DIR, GALLERY_SCREENSHOTS_DIR);
  } catch {
    // no screenshots yet; tolerate
  }

  const manifest: ManifestEntry[] = [];
  let flipbooksRendered = 0;
  let motionRendered = 0;
  let videosCopied = 0;
  for (const meta of metadataEntries) {
    let flipbookRel: string | null = null;
    let motionRel: string | null = null;
    let videoRel: string | null = null;

    // Copy original video into gallery for direct playback.
    if (meta.videoPath) {
      const videoSrcAbs = path.join(WALKTHROUGHS_DIR, meta.videoPath);
      const videoDestAbs = path.join(GALLERY_VIDEOS_DIR, `${meta.slug}.webm`);
      try {
        await fs.access(videoSrcAbs);
        await fs.copyFile(videoSrcAbs, videoDestAbs);
        videoRel = path.posix.join('videos', `${meta.slug}.webm`);
        videosCopied += 1;

        // Motion GIF (video-derived, slowed to 5 fps).
        const motionAbs = path.join(GALLERY_GIFS_DIR, `${meta.slug}-motion.gif`);
        if (await renderMotionGif(videoSrcAbs, motionAbs, meta.slug)) {
          motionRel = path.posix.join('gifs', `${meta.slug}-motion.gif`);
          motionRendered += 1;
        }
      } catch {
        console.warn(`[walkthroughs] video missing for slug ${meta.slug}, skipping motion GIF`);
      }
    } else {
      console.warn(`[walkthroughs] no video recorded for slug ${meta.slug}`);
    }

    // Flipbook GIF (built from per-step screenshots — primary comprehension aid).
    if (meta.steps && meta.steps.length > 0) {
      const screenshotAbsPaths = meta.steps.map((st) => path.join(WALKTHROUGHS_DIR, st.screenshot));
      // Verify all exist; drop those that don't.
      const existing: string[] = [];
      for (const p of screenshotAbsPaths) {
        try {
          await fs.access(p);
          existing.push(p);
        } catch {
          // skip missing
        }
      }
      if (existing.length > 0) {
        const flipbookAbs = path.join(GALLERY_GIFS_DIR, `${meta.slug}.gif`);
        if (await renderFlipbookGif(existing, flipbookAbs, meta.slug)) {
          flipbookRel = path.posix.join('gifs', `${meta.slug}.gif`);
          flipbooksRendered += 1;
        }
      }
    }

    manifest.push({
      ...meta,
      gifPath: flipbookRel,
      motionGifPath: motionRel,
      videoGalleryPath: videoRel,
      feature: inferFeature(meta.specFile),
    });
  }

  manifest.sort((a, b) => a.startedAt.localeCompare(b.startedAt));
  await fs.writeFile(
    path.join(GALLERY_DIR, 'manifest.json'),
    JSON.stringify({ generatedAt: new Date().toISOString(), scenarios: manifest }, null, 2),
    'utf8',
  );

  console.log(`[walkthroughs] wrote manifest with ${manifest.length} scenario(s) to ${GALLERY_DIR}`);
  console.log(`[walkthroughs] ${flipbooksRendered} flipbook GIFs, ${motionRendered} motion GIFs, ${videosCopied} videos copied`);
  console.log(`[walkthroughs] open ${path.join(GALLERY_DIR, 'index.html')} or run \`npm run walkthroughs:serve\``);
}

main().catch((err: unknown) => {
  console.error('[walkthroughs] fatal:', err);
  process.exit(1);
});

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

/**
 * Scenario slugs embed a per-run suffix: `<stable-prefix>-<epoch-ms>-w<workerIndex>`.
 * We keep only the latest run per stable prefix so the dashboard shows one card
 * per scenario (the most recent), not N cards accumulated across runs. Older
 * metadata JSONs and their sibling screenshots/videos/traces are deleted so
 * regeneration starts from a clean, per-scenario-latest state.
 */
const SLUG_RUN_SUFFIX = /-\d{10,}-w\d+$/;

function stableScenarioKey(slug: string): string {
  return slug.replace(SLUG_RUN_SUFFIX, '');
}

async function pruneStaleScenarioArtifacts(): Promise<void> {
  let files: string[] = [];
  try {
    files = await fs.readdir(METADATA_DIR);
  } catch {
    return;
  }
  const jsons = files.filter((f) => f.endsWith('.json'));
  // Parse minimal fields from each metadata to group by stable key and find latest.
  interface MetaRef { file: string; slug: string; startedAt: string; key: string; }
  const refs: MetaRef[] = [];
  for (const f of jsons) {
    try {
      const raw = await fs.readFile(path.join(METADATA_DIR, f), 'utf8');
      const parsed = JSON.parse(raw) as Partial<RawMetadata>;
      if (typeof parsed.slug !== 'string' || typeof parsed.startedAt !== 'string') continue;
      refs.push({ file: f, slug: parsed.slug, startedAt: parsed.startedAt, key: stableScenarioKey(parsed.slug) });
    } catch {
      // skip malformed; will be cleaned up by rmDir on subsequent steps if orphaned
    }
  }
  const latestByKey: Map<string, MetaRef> = new Map();
  for (const r of refs) {
    const prev = latestByKey.get(r.key);
    if (!prev || r.startedAt > prev.startedAt) latestByKey.set(r.key, r);
  }
  const keepSlugs = new Set<string>();
  for (const r of latestByKey.values()) keepSlugs.add(r.slug);

  let removedMeta = 0;
  for (const r of refs) {
    if (keepSlugs.has(r.slug)) continue;
    await fs.rm(path.join(METADATA_DIR, r.file), { force: true });
    await rmDir(path.join(SCREENSHOTS_DIR, r.slug));
    await fs.rm(path.join(WALKTHROUGHS_DIR, 'videos', `${r.slug}.webm`), { force: true });
    await fs.rm(path.join(WALKTHROUGHS_DIR, 'traces', `${r.slug}.zip`), { force: true });
    removedMeta += 1;
  }
  if (removedMeta > 0) {
    console.log(`[walkthroughs] pruned ${removedMeta} stale scenario run(s); kept ${latestByKey.size} latest.`);
  }
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

async function probeImageSize(imagePath: string): Promise<{ width: number; height: number } | null> {
  try {
    const { stdout } = await execFileP('ffprobe', [
      '-v', 'error',
      '-select_streams', 'v:0',
      '-show_entries', 'stream=width,height',
      '-of', 'csv=p=0',
      imagePath,
    ]);
    const [w, h] = stdout.trim().split(',').map((s) => parseInt(s, 10));
    if (Number.isFinite(w) && Number.isFinite(h) && w > 0 && h > 0) return { width: w, height: h };
    return null;
  } catch {
    return null;
  }
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
 * holding each frame for FLIPBOOK_HOLD_SECONDS.
 *
 * Why we do NOT use the concat demuxer here: Playwright `fullPage: true`
 * screenshots have variable heights (the page can grow between steps when
 * new rows/modals appear). Feeding variable-size stills through the concat
 * demuxer causes ffmpeg to reconfigure the filter graph mid-stream and the
 * GIF encoder silently collapses the output into a tiny clip where every
 * frame matches the FIRST input's geometry — producing a "constant frame"
 * flipbook even though the source PNGs are all distinct.
 *
 * Instead: load each screenshot as its own looped image input, scale + pad
 * every input to a shared (width, height) box computed from the max scaled
 * height across inputs, then concat the normalized streams. All inputs now
 * share identical SAR/PAR/resolution, so the GIF encoder produces one
 * distinct frame per step as intended.
 */
async function renderFlipbookGif(
  screenshotAbsPaths: string[],
  gifAbsPath: string,
  slug: string,
): Promise<boolean> {
  if (screenshotAbsPaths.length === 0) return false;

  // Probe every input so we can compute a common output box.
  const sizes: Array<{ path: string; width: number; height: number }> = [];
  for (const p of screenshotAbsPaths) {
    const s = await probeImageSize(p);
    if (!s) {
      console.warn(`[walkthroughs] could not probe size of ${p}, skipping flipbook for ${slug}`);
      return false;
    }
    sizes.push({ path: p, ...s });
  }

  // Target width: GIF_WIDTH. For each input compute its scaled height (width=GIF_WIDTH,
  // preserving aspect). Use the maximum scaled height (rounded to even) as the output
  // canvas height; pad shorter frames with black bars top/bottom.
  const scaledHeights = sizes.map((s) => Math.round((GIF_WIDTH * s.height) / s.width));
  const rawMaxH = Math.max(...scaledHeights);
  const outH = rawMaxH % 2 === 0 ? rawMaxH : rawMaxH + 1; // even for GIF/palette filters
  const outW = GIF_WIDTH;

  // Build a single ffmpeg invocation: one -loop 1 -t DUR -i FILE per screenshot,
  // then a filter_complex that normalizes each to outW x outH and concats.
  const inputArgs: string[] = [];
  for (const s of sizes) {
    inputArgs.push('-loop', '1', '-t', FLIPBOOK_HOLD_SECONDS.toFixed(3), '-i', s.path);
  }

  const normChains: string[] = [];
  const concatLabels: string[] = [];
  for (let i = 0; i < sizes.length; i++) {
    const label = `v${i}`;
    // scale to fit outW x outH preserving aspect, then pad to exactly outW x outH centered.
    normChains.push(
      `[${i}:v]scale=${outW}:${outH}:force_original_aspect_ratio=decrease:flags=lanczos,` +
      `pad=${outW}:${outH}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps=${FLIPBOOK_FPS},format=rgba[${label}]`,
    );
    concatLabels.push(`[${label}]`);
  }
  const concatFilter =
    `${concatLabels.join('')}concat=n=${sizes.length}:v=1:a=0[cat];` +
    `[cat]split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5`;
  const fc = normChains.join(';') + ';' + concatFilter;

  try {
    await execFileP('ffmpeg', [
      '-y',
      ...inputArgs,
      '-filter_complex', fc,
      '-loop', '0',
      gifAbsPath,
    ]);
    const renderedDuration = await probeVideoDurationSec(gifAbsPath);
    console.log(
      `[walkthroughs] flipbook GIF ${slug}: ${FLIPBOOK_FPS} fps, ` +
      `${screenshotAbsPaths.length} steps × ${FLIPBOOK_HOLD_SECONDS}s, ` +
      `canvas=${outW}x${outH}, gif=${renderedDuration ? renderedDuration.toFixed(2) : '?'}s`
    );
    return true;
  } catch (err) {
    const e = err as NodeJS.ErrnoException & { stderr?: string };
    handleFfmpegMissing(e);
    console.warn(`[walkthroughs] flipbook ffmpeg failed for ${slug}: ${e.stderr ?? e.message}`);
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
  // Prune stale runs first so downstream work only touches the latest per scenario.
  await pruneStaleScenarioArtifacts();
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

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
// Caption + title overlay sizes. Caption was previously rendered too small to
// read at 640px wide, so we bumped it ~50% (12 -> 18) and added a top header
// strip carrying the scenario title on every frame for context.
const FLIPBOOK_CAPTION_FONT_SIZE = 18;
const FLIPBOOK_TITLE_FONT_SIZE = 24;
// Pad the strips generously so descenders + multi-line wraps stay inside the
// strip even when titles or step names get long.
const FLIPBOOK_TITLE_STRIP_HEIGHT = 44;
const FLIPBOOK_CAPTION_STRIP_HEIGHT = 36;
// Resolve a font file once. macOS dev workstations always ship Arial; fall
// back to common Linux paths so CI and Docker runs still render text.
const FLIPBOOK_FONT_CANDIDATES = [
  '/System/Library/Fonts/Supplemental/Arial.ttf',
  '/Library/Fonts/Arial.ttf',
  '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
  '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
  '/usr/share/fonts/TTF/DejaVuSans.ttf',
];

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

let cachedFontPath: string | null | undefined;
async function resolveFlipbookFont(): Promise<string | null> {
  if (cachedFontPath !== undefined) return cachedFontPath;
  for (const candidate of FLIPBOOK_FONT_CANDIDATES) {
    try {
      await fs.access(candidate);
      cachedFontPath = candidate;
      return candidate;
    } catch {
      // try next
    }
  }
  cachedFontPath = null;
  return null;
}

/**
 * Escape a string for use as the literal `text` argument inside ffmpeg's
 * `drawtext` filter. ffmpeg's filter syntax treats `:` as an option separator
 * and `\` as an escape lead, and the surrounding single-quote in our value
 * needs guarding too.
 */
function escapeDrawtext(value: string): string {
  return value
    .replace(/\\/g, '\\\\')
    .replace(/:/g, '\\:')
    .replace(/'/g, "\\\\\\'")
    .replace(/%/g, '\\%');
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
  inputs: Array<{ path: string; stepName: string; index: number }>,
  scenarioTitle: string,
  gifAbsPath: string,
  slug: string,
): Promise<boolean> {
  if (inputs.length === 0) return false;

  // Probe every input so we can compute a common output box.
  const sizes: Array<{ path: string; width: number; height: number; stepName: string; index: number }> = [];
  for (const inp of inputs) {
    const s = await probeImageSize(inp.path);
    if (!s) {
      console.warn(`[walkthroughs] could not probe size of ${inp.path}, skipping flipbook for ${slug}`);
      return false;
    }
    sizes.push({ path: inp.path, ...s, stepName: inp.stepName, index: inp.index });
  }

  // Target width: GIF_WIDTH. For each input compute its scaled height (width=GIF_WIDTH,
  // preserving aspect). Use the maximum scaled height (rounded to even) as the output
  // image-area height; pad shorter frames with black bars top/bottom. The final GIF
  // canvas adds a title strip at the top and a caption strip at the bottom so each
  // frame stands on its own out of context.
  const scaledHeights = sizes.map((s) => Math.round((GIF_WIDTH * s.height) / s.width));
  const rawMaxH = Math.max(...scaledHeights);
  const imgH = rawMaxH % 2 === 0 ? rawMaxH : rawMaxH + 1; // even for GIF/palette filters
  const outW = GIF_WIDTH;
  const titleH = FLIPBOOK_TITLE_STRIP_HEIGHT;
  const captionH = FLIPBOOK_CAPTION_STRIP_HEIGHT;
  const outH = imgH + titleH + captionH;

  const fontPath = await resolveFlipbookFont();
  if (!fontPath) {
    console.warn('[walkthroughs] no usable TTF found for drawtext; flipbook will render without captions');
  }

  // Pre-escape the scenario title since it appears on every frame.
  const titleText = escapeDrawtext(scenarioTitle);

  // Build a single ffmpeg invocation: one -loop 1 -t DUR -i FILE per screenshot,
  // then a filter_complex that normalizes each into the layout (title strip on top,
  // image in the middle, caption strip on the bottom), draws text, and concats.
  const inputArgs: string[] = [];
  for (const s of sizes) {
    inputArgs.push('-loop', '1', '-t', FLIPBOOK_HOLD_SECONDS.toFixed(3), '-i', s.path);
  }

  const normChains: string[] = [];
  const concatLabels: string[] = [];
  for (let i = 0; i < sizes.length; i++) {
    const label = `v${i}`;
    const s = sizes[i]!;
    // 1. Scale screenshot into the image-area (outW x imgH) preserving aspect, pad to fit.
    // 2. Pad the canvas to outW x outH adding `titleH` of dark space on top and `captionH`
    //    of dark space on the bottom — this is where the title and caption strips render.
    let chain =
      `[${i}:v]scale=${outW}:${imgH}:force_original_aspect_ratio=decrease:flags=lanczos,` +
      `pad=${outW}:${imgH}:(ow-iw)/2:(oh-ih)/2:color=black,` +
      `pad=${outW}:${outH}:0:${titleH}:color=0x0f172a,setsar=1`;

    if (fontPath) {
      const captionText = escapeDrawtext(`Step ${s.index}: ${s.stepName}`);
      // Title strip: scenario title centered at the top.
      chain +=
        `,drawtext=fontfile='${fontPath}':text='${titleText}':` +
        `fontcolor=white:fontsize=${FLIPBOOK_TITLE_FONT_SIZE}:` +
        `x=(w-text_w)/2:y=(${titleH}-text_h)/2`;
      // Caption strip: per-step caption centered at the bottom.
      chain +=
        `,drawtext=fontfile='${fontPath}':text='${captionText}':` +
        `fontcolor=white:fontsize=${FLIPBOOK_CAPTION_FONT_SIZE}:` +
        `x=(w-text_w)/2:y=h-${captionH}+(${captionH}-text_h)/2`;
    }

    chain += `,fps=${FLIPBOOK_FPS},format=rgba[${label}]`;
    normChains.push(chain);
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
      `${inputs.length} steps × ${FLIPBOOK_HOLD_SECONDS}s, ` +
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
      // Verify each step's screenshot exists; drop any that don't but keep
      // step name + index alignment so captions match the visible frame.
      const existing: Array<{ path: string; stepName: string; index: number }> = [];
      for (const st of meta.steps) {
        const absPath = path.join(WALKTHROUGHS_DIR, st.screenshot);
        try {
          await fs.access(absPath);
          existing.push({ path: absPath, stepName: st.name, index: st.index });
        } catch {
          // skip missing
        }
      }
      if (existing.length > 0) {
        const flipbookAbs = path.join(GALLERY_GIFS_DIR, `${meta.slug}.gif`);
        if (await renderFlipbookGif(existing, meta.name, flipbookAbs, meta.slug)) {
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

import React, { useEffect, useMemo, useRef, useState } from 'react';
import type { Aspect } from '../types';
import { ArtifactSchemaError, loadArtifact } from '../../lib/loadArtifact';
import type { ScenarioEntry, ScenariosManifest } from './types';
import {
  groupByFeature,
  parseScenariosHash,
  type FeatureGroup,
} from './grouping';
import { ScenarioTracePanel } from './ScenarioTracePanel';
import {
  GALLERY_VIEW_DEFAULT,
  TILE_SIZE_DEFAULT,
  TILE_SIZE_MAX,
  TILE_SIZE_MIN,
  TILE_SIZE_STOPS,
  clampTileSize,
  readGalleryView,
  readTileSize,
  writeGalleryView,
  writeTileSize,
  type GalleryView,
} from '../../lib/gallery';
import {
  VIDEO_SPEEDS,
  readVideoSpeed,
  writeVideoSpeed,
  type VideoSpeed,
} from '../../lib/videoSpeed';

const ARTIFACT_URL = '/artifacts/scenarios/gallery/manifest.json';

export function resolveMediaUrl(rel: string | undefined): string | undefined {
  if (!rel) return undefined;
  if (rel.startsWith('/') || rel.startsWith('http')) return rel;
  return `/artifacts/scenarios/gallery/${rel.replace(/^\.?\//, '')}`;
}

export function validate(doc: unknown): ScenariosManifest {
  if (typeof doc !== 'object' || doc === null) {
    throw new ArtifactSchemaError(ARTIFACT_URL, 'root');
  }
  const d = doc as { scenarios?: unknown };
  if (!Array.isArray(d.scenarios)) {
    throw new ArtifactSchemaError(ARTIFACT_URL, 'scenarios');
  }
  const scenarios: ScenarioEntry[] = [];
  for (let i = 0; i < d.scenarios.length; i++) {
    const raw = d.scenarios[i];
    if (typeof raw !== 'object' || raw === null) {
      throw new ArtifactSchemaError(ARTIFACT_URL, `scenarios[${i}]`);
    }
    const r = raw as Record<string, unknown>;
    const id =
      typeof r.id === 'string'
        ? r.id
        : typeof r.slug === 'string'
          ? r.slug
          : null;
    if (id === null) {
      throw new ArtifactSchemaError(ARTIFACT_URL, `scenarios[${i}].id|slug`);
    }
    const title =
      typeof r.title === 'string'
        ? r.title
        : typeof r.name === 'string'
          ? r.name
          : null;
    if (title === null) {
      throw new ArtifactSchemaError(ARTIFACT_URL, `scenarios[${i}].title|name`);
    }
    const rawStatus = typeof r.status === 'string' ? r.status : undefined;
    const normalizedStatus =
      rawStatus === 'passing' || rawStatus === 'passed'
        ? 'passing'
        : rawStatus === 'failing' || rawStatus === 'failed'
          ? 'failing'
          : undefined;
    const gif =
      typeof r.gif === 'string'
        ? r.gif
        : typeof r.gifPath === 'string'
          ? r.gifPath
          : undefined;
    const video =
      typeof r.video === 'string'
        ? r.video
        : typeof r.videoGalleryPath === 'string'
          ? r.videoGalleryPath
          : typeof r.videoPath === 'string'
            ? r.videoPath
            : undefined;
    const steps = Array.isArray(r.steps)
      ? (r.steps as Record<string, unknown>[]).map((s, idx) => {
          const sStatus = typeof s.status === 'string' ? s.status : undefined;
          const normStatus =
            sStatus === 'passing' || sStatus === 'passed'
              ? ('passing' as const)
              : sStatus === 'failing' || sStatus === 'failed'
                ? ('failing' as const)
                : undefined;
          return {
            index: typeof s.index === 'number' ? s.index : idx,
            label:
              typeof s.label === 'string'
                ? s.label
                : typeof s.name === 'string'
                  ? s.name
                  : '',
            screenshot: resolveMediaUrl(
              typeof s.screenshot === 'string' ? s.screenshot : undefined,
            ),
            durationMs:
              typeof s.durationMs === 'number' ? s.durationMs : undefined,
            status: normStatus,
            url: typeof s.url === 'string' ? s.url : undefined,
          };
        })
      : undefined;
    const firstShot = steps?.find((s) => s.screenshot)?.screenshot;
    scenarios.push({
      id,
      title,
      tags: Array.isArray(r.tags) ? (r.tags as string[]) : undefined,
      status: normalizedStatus,
      correlationId:
        typeof r.correlationId === 'string' ? r.correlationId : undefined,
      gif: resolveMediaUrl(gif),
      motionGif: resolveMediaUrl(
        typeof r.motionGifPath === 'string'
          ? r.motionGifPath
          : typeof r.motionGif === 'string'
            ? r.motionGif
            : undefined,
      ),
      video: resolveMediaUrl(video),
      durationMs: typeof r.durationMs === 'number' ? r.durationMs : undefined,
      startedAt: typeof r.startedAt === 'string' ? r.startedAt : undefined,
      thumbnail:
        resolveMediaUrl(typeof r.thumbnail === 'string' ? r.thumbnail : undefined) ??
        firstShot,
      steps,
      specFile: typeof r.specFile === 'string' ? r.specFile : undefined,
      feature: typeof r.feature === 'string' ? r.feature : undefined,
    });
  }
  const generatedAt =
    typeof (doc as { generatedAt?: unknown }).generatedAt === 'string'
      ? ((doc as { generatedAt: string }).generatedAt)
      : undefined;
  return { scenarios, generatedAt };
}

export interface ScenariosData extends ScenariosManifest {
  traceScenarioIds: Set<string>;
  groups: FeatureGroup[];
}

async function fetchTraceIndex(): Promise<Set<string>> {
  try {
    const resp = await fetch('/artifacts/traces/');
    if (!resp.ok) return new Set();
    const body = (await resp.json()) as {
      entries?: Array<{ name: string; type: string }>;
    };
    const ids = (body.entries ?? [])
      .filter((e) => e.type === 'dir')
      .map((e) => slugify(e.name));
    return new Set(ids);
  } catch {
    return new Set();
  }
}

function slugify(id: string): string {
  return id.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

function Breadcrumb({
  entry,
  extra,
}: {
  entry: ScenarioEntry;
  extra?: { label: string } | null;
}) {
  return (
    <nav
      className="scen-breadcrumb"
      data-testid="breadcrumb"
      aria-label="breadcrumb"
    >
      <a
        href="#/scenarios"
        data-testid="breadcrumb-gallery"
        className="scen-breadcrumb__link"
      >
        ← back to gallery
      </a>
      <span className="scen-breadcrumb__sep">/</span>
      {extra ? (
        <a
          href={`#/scenarios/${entry.id}`}
          data-testid="breadcrumb-scenario"
          className="scen-breadcrumb__link"
        >
          {entry.title}
        </a>
      ) : (
        <span data-testid="breadcrumb-scenario" className="scen-breadcrumb__current">
          {entry.title}
        </span>
      )}
      {extra && (
        <>
          <span className="scen-breadcrumb__sep">/</span>
          <span
            data-testid="breadcrumb-leaf"
            className="scen-breadcrumb__current"
          >
            {extra.label}
          </span>
        </>
      )}
    </nav>
  );
}

function ScreenshotsPage({ entry }: { entry: ScenarioEntry }) {
  const screenshots = (entry.steps ?? [])
    .map((s) => s.screenshot)
    .filter((s): s is string => Boolean(s));
  const [active, setActive] = useState<number | null>(null);
  return (
    <div data-testid="screenshots-page">
      <Breadcrumb entry={entry} extra={{ label: 'screenshots' }} />
      <div className="detail__page-links">
        <a href={`#/scenarios/${entry.id}`} data-testid="page-link-detail">
          detail
        </a>
        <a href={`#/scenarios/${entry.id}/flow`} data-testid="page-link-flow">
          flow
        </a>
      </div>
      <div className="screenshots-grid" data-testid="screenshots-grid">
        {screenshots.map((src, i) => (
          <button
            key={`${src}-${i}`}
            type="button"
            className="screenshots-grid__cell"
            data-testid={`screenshots-cell-${i}`}
            onClick={() => setActive(i)}
          >
            <img src={src} alt={`screenshot ${i + 1}`} />
          </button>
        ))}
      </div>
      <Lightbox
        state={active === null ? { kind: 'closed' } : { kind: 'screenshot', index: active }}
        screenshots={screenshots}
        onClose={() => setActive(null)}
        onIndex={(i) => setActive(i)}
      />
    </div>
  );
}

function FlowPage({ entry }: { entry: ScenarioEntry }) {
  const screenshots = (entry.steps ?? [])
    .map((s) => s.screenshot)
    .filter((s): s is string => Boolean(s));
  return (
    <div data-testid="flow-page">
      <Breadcrumb entry={entry} extra={{ label: 'flow' }} />
      <div className="detail__page-links">
        <a href={`#/scenarios/${entry.id}`} data-testid="page-link-detail">
          detail
        </a>
        <a
          href={`#/scenarios/${entry.id}/screenshots`}
          data-testid="page-link-screenshots"
        >
          screenshots
        </a>
      </div>
      <div className="flow-strip" data-testid="flow-strip">
        {(entry.steps ?? []).map((step, i) => (
          <figure key={step.index} className="flow-strip__cell">
            <img
              src={screenshots[i] ?? ''}
              alt={step.label}
              data-testid={`flow-cell-${step.index}`}
            />
            <figcaption>
              <span className="flow-strip__idx">{step.index}.</span>
              {step.label}
            </figcaption>
          </figure>
        ))}
      </div>
    </div>
  );
}

type LightboxState =
  | { kind: 'closed' }
  | { kind: 'screenshot'; index: number }
  | { kind: 'gif'; src: string; alt: string }
  | { kind: 'video'; src: string };

function ScreenshotStrip({
  screenshots,
  entryId,
  onOpen,
}: {
  screenshots: string[];
  entryId: string;
  onOpen: (index: number) => void;
}) {
  if (screenshots.length === 0) return null;
  const total = screenshots.length;
  return (
    <div
      className="scen-strip scen-strip--detail"
      data-testid="screenshot-strip"
    >
      <div className="scen-strip__frames">
        {screenshots.map((src, i) => (
          <button
            key={`${src}-${i}`}
            type="button"
            className="scen-strip__frame"
            data-testid={`strip-thumb-${i}`}
            onClick={() => onOpen(i)}
          >
            <img
              src={src}
              alt={`screenshot ${i + 1} of ${total}`}
              loading={i < 3 ? 'eager' : 'lazy'}
              decoding="async"
              width={320}
              height={180}
            />
            <span className="strip-n">{i + 1}</span>
          </button>
        ))}
      </div>
      <a
        href={`#/scenarios/${entryId}/screenshots`}
        className="detail__strip-more"
        data-testid="view-all-screenshots"
      >
        view all ({total}) →
      </a>
    </div>
  );
}

function VideoBlock({ src }: { src: string }) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [speed, setSpeed] = useState<VideoSpeed>(() =>
    typeof window === 'undefined' ? 0.25 : readVideoSpeed(),
  );

  useEffect(() => {
    if (videoRef.current) videoRef.current.playbackRate = speed;
  }, [speed, src]);

  function onSpeedChange(e: React.ChangeEvent<HTMLSelectElement>): void {
    const rate = Number(e.currentTarget.value) as VideoSpeed;
    setSpeed(rate);
    writeVideoSpeed(rate);
    if (videoRef.current) videoRef.current.playbackRate = rate;
  }
  return (
    <div className="detail__video" data-testid="video-block">
      <video
        ref={videoRef}
        data-testid="scenario-video"
        src={src}
        controls
        style={{ maxWidth: '100%' }}
        onLoadedMetadata={() => {
          if (videoRef.current) videoRef.current.playbackRate = speed;
        }}
      />
      <div className="detail__video-controls detail__video-controls--prominent">
        <label className="detail__video-speed-label">
          <span className="detail__video-speed-heading">Playback speed:</span>{' '}
          <select
            data-testid="video-speed"
            value={String(speed)}
            onChange={onSpeedChange}
          >
            {VIDEO_SPEEDS.map((s) => (
              <option key={s} value={String(s)}>
                {s}x
              </option>
            ))}
          </select>
        </label>
        <span
          className="pill pill--speed"
          data-testid="video-speed-current"
        >
          {speed}x
        </span>
        <a
          href={src}
          download
          data-testid="download-webm"
          className="detail__download"
        >
          download .webm
        </a>
      </div>
    </div>
  );
}

function MetadataKV({
  entry,
  hasTrace,
  onViewTrace,
}: {
  entry: ScenarioEntry;
  hasTrace: boolean;
  onViewTrace: () => void;
}) {
  const featureLabel =
    (entry.feature ?? '').trim() ||
    (entry.specFile?.split(/[\\/]/).pop() ?? '—');
  const statusLabel = entry.status ?? 'unknown';
  return (
    <dl className="detail__kv" data-testid="metadata-kv">
      <dt>Status</dt>
      <dd>
        <span
          className={`pill pill--${statusLabel}`}
          data-testid="metadata-status"
        >
          {statusLabel}
        </span>
      </dd>
      <dt>Feature</dt>
      <dd data-testid="metadata-feature">{featureLabel}</dd>
      <dt>Correlation ID</dt>
      <dd>
        <code data-testid="metadata-correlation-id">
          {entry.correlationId ?? '—'}
        </code>
      </dd>
      <dt>Started</dt>
      <dd data-testid="metadata-started">{entry.startedAt ?? '—'}</dd>
      <dt>Duration</dt>
      <dd data-testid="metadata-duration">
        {typeof entry.durationMs === 'number' ? `${entry.durationMs} ms` : '—'}
      </dd>
      <dt>Spec</dt>
      <dd data-testid="metadata-spec">
        <code>{entry.specFile ?? '—'}</code>
      </dd>
      <dt>Trace</dt>
      <dd>
        {hasTrace ? (
          <button
            type="button"
            data-testid="metadata-trace-link"
            className="detail__trace-link"
            onClick={onViewTrace}
          >
            view trace →
          </button>
        ) : (
          <span data-testid="metadata-trace-link">—</span>
        )}
      </dd>
    </dl>
  );
}

function StepList({ entry }: { entry: ScenarioEntry }) {
  if (!entry.steps || entry.steps.length === 0) return null;
  return (
    <ol className="detail__steps" data-testid="scenario-steps">
      {entry.steps.map((s) => (
        <li key={s.index} data-testid={`step-${s.index}`}>
          <span
            className={`pill pill--${s.status ?? 'unknown'}`}
            data-testid={`step-status-${s.index}`}
          />
          <span className="detail__step-label">{s.label}</span>
          {typeof s.durationMs === 'number' && (
            <span
              className="detail__step-ms"
              data-testid={`step-ms-${s.index}`}
            >
              {s.durationMs} ms
            </span>
          )}
        </li>
      ))}
    </ol>
  );
}

function LightboxVideo({ src }: { src: string }) {
  const ref = useRef<HTMLVideoElement | null>(null);
  const [speed, setSpeed] = useState<VideoSpeed>(() =>
    typeof window === 'undefined' ? 0.25 : readVideoSpeed(),
  );

  useEffect(() => {
    if (ref.current) ref.current.playbackRate = speed;
  }, [speed, src]);

  return (
    <div className="lightbox__video-wrap">
      <video
        ref={ref}
        className="lightbox__video"
        data-testid="lightbox-video"
        src={src}
        controls
        autoPlay
        onLoadedMetadata={() => {
          if (ref.current) ref.current.playbackRate = speed;
        }}
      />
      <div className="lightbox__video-controls">
        <label className="detail__video-speed-label">
          <span className="detail__video-speed-heading">Playback speed:</span>{' '}
          <select
            data-testid="lightbox-video-speed"
            value={String(speed)}
            onChange={(e) => {
              const rate = Number(e.currentTarget.value) as VideoSpeed;
              setSpeed(rate);
              writeVideoSpeed(rate);
              if (ref.current) ref.current.playbackRate = rate;
            }}
          >
            {VIDEO_SPEEDS.map((s) => (
              <option key={s} value={String(s)}>
                {s}x
              </option>
            ))}
          </select>
        </label>
        <span
          className="pill pill--speed"
          data-testid="lightbox-video-speed-current"
        >
          {speed}x
        </span>
        <a href={src} download data-testid="lightbox-download-webm">
          download .webm
        </a>
      </div>
    </div>
  );
}

function Lightbox({
  state,
  screenshots,
  onClose,
  onIndex,
}: {
  state: LightboxState;
  screenshots: string[];
  onClose: () => void;
  onIndex: (i: number) => void;
}) {
  useEffect(() => {
    if (state.kind === 'closed') return;
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
      if (state.kind === 'screenshot') {
        if (e.key === 'ArrowRight') {
          onIndex((state.index + 1) % screenshots.length);
        } else if (e.key === 'ArrowLeft') {
          onIndex(
            (state.index - 1 + screenshots.length) % screenshots.length,
          );
        }
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [state, screenshots.length, onClose, onIndex]);

  if (state.kind === 'closed') return null;
  const total = screenshots.length;
  return (
    <div
      className="lightbox"
      data-testid="lightbox"
      data-kind={state.kind}
      role="dialog"
      aria-modal="true"
    >
      <button
        type="button"
        className="lightbox__close"
        data-testid="lightbox-close"
        onClick={onClose}
        aria-label="close"
      >
        ×
      </button>
      {state.kind === 'screenshot' && (
        <>
          <button
            type="button"
            className="lightbox__nav lightbox__nav--prev"
            data-testid="lightbox-prev"
            onClick={() =>
              onIndex((state.index - 1 + total) % total)
            }
            aria-label="previous"
          >
            ‹
          </button>
          <img
            className="lightbox__img"
            data-testid="lightbox-img"
            src={screenshots[state.index]}
            alt={`screenshot ${state.index + 1} of ${total}`}
          />
          <div className="lightbox__counter" data-testid="lightbox-counter">
            {state.index + 1} of {total}
          </div>
          <button
            type="button"
            className="lightbox__nav lightbox__nav--next"
            data-testid="lightbox-next"
            onClick={() => onIndex((state.index + 1) % total)}
            aria-label="next"
          >
            ›
          </button>
        </>
      )}
      {state.kind === 'gif' && (
        <img
          className="lightbox__img"
          data-testid="lightbox-gif"
          src={state.src}
          alt={state.alt}
        />
      )}
      {state.kind === 'video' && (
        <LightboxVideo src={state.src} />
      )}
    </div>
  );
}

function Detail({
  entry,
  traceScenarioIds,
  onViewTrace,
}: {
  entry: ScenarioEntry;
  traceScenarioIds: Set<string>;
  onViewTrace: (slug: string) => void;
}) {
  const traceSlug = slugify(entry.id);
  const hasTrace = traceScenarioIds.has(traceSlug);
  const screenshots = useMemo(
    () =>
      (entry.steps ?? [])
        .map((s) => s.screenshot)
        .filter((s): s is string => Boolean(s)),
    [entry],
  );
  const [lightbox, setLightbox] = useState<LightboxState>({ kind: 'closed' });

  return (
    <div data-testid="scenario-detail">
      <Breadcrumb entry={entry} />
      <h3 className="detail__title">{entry.title}</h3>

      <div data-testid="scenario-metadata">
        <MetadataKV
          entry={entry}
          hasTrace={hasTrace}
          onViewTrace={() => onViewTrace(traceSlug)}
        />
      </div>

      <div data-testid="scenario-media">
        <div className="detail__media-row">
          {entry.gif && (
            <button
              type="button"
              className="detail__media detail__media--flipbook"
              data-testid="detail-flipbook"
              title="Flipbook — one frame per step, 1.5s hold — good for scanning"
              onClick={() =>
                setLightbox({ kind: 'gif', src: entry.gif!, alt: entry.title })
              }
            >
              <img src={entry.gif} alt={`${entry.title} flipbook`} />
              <figcaption>flipbook</figcaption>
            </button>
          )}
          {entry.motionGif && (
            <button
              type="button"
              className="detail__media detail__media--motion"
              data-testid="detail-motion"
              title="Motion — video-derived, slowed 2x — good for watching the flow"
              onClick={() =>
                setLightbox({
                  kind: 'gif',
                  src: entry.motionGif!,
                  alt: `${entry.title} motion`,
                })
              }
            >
              <img src={entry.motionGif} alt={`${entry.title} motion`} />
              <figcaption>motion</figcaption>
            </button>
          )}
        </div>

        <ScreenshotStrip
          screenshots={screenshots}
          entryId={entry.id}
          onOpen={(i) => setLightbox({ kind: 'screenshot', index: i })}
        />

        {entry.video && (
          <button
            type="button"
            className="detail__video-trigger"
            data-testid="video-lightbox-open"
            onClick={() =>
              entry.video
                ? setLightbox({ kind: 'video', src: entry.video })
                : undefined
            }
          >
            open video in lightbox
          </button>
        )}
        {entry.video && <VideoBlock src={entry.video} />}
      </div>

      <StepList entry={entry} />

      {entry.correlationId && (
        <section className="detail__traces" data-testid="detail-traces">
          <h4>Backend Requests</h4>
          <ScenarioTracePanel correlationId={entry.correlationId} />
        </section>
      )}

      {hasTrace && (
        <button
          type="button"
          data-testid="view-trace-link"
          className="detail__view-trace"
          onClick={() => onViewTrace(traceSlug)}
        >
          View trace →
        </button>
      )}
      <Lightbox
        state={lightbox}
        screenshots={screenshots}
        onClose={() => setLightbox({ kind: 'closed' })}
        onIndex={(i) => setLightbox({ kind: 'screenshot', index: i })}
      />
    </div>
  );
}

function StripRow({
  entry,
  isFirst,
  onOpenAt,
}: {
  entry: ScenarioEntry;
  isFirst: boolean;
  onOpenAt: (scenarioId: string, stepIndex: number) => void;
}) {
  const frames = (entry.steps ?? [])
    .map((s) => s.screenshot)
    .filter((s): s is string => Boolean(s));
  const framesRef = useRef<HTMLDivElement | null>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  useEffect(() => {
    const el = framesRef.current;
    if (!el) return;
    function update() {
      if (!el) return;
      setCanScrollLeft(el.scrollLeft > 4);
      setCanScrollRight(
        el.scrollLeft + el.clientWidth < el.scrollWidth - 4,
      );
    }
    // Re-check after layout settles (images may still be 0×0 on first paint).
    const raf = requestAnimationFrame(update);
    update();
    el.addEventListener('scroll', update, { passive: true });
    const ro = new ResizeObserver(update);
    ro.observe(el);
    // Every image load changes scrollWidth; recompute on each.
    const imgs = Array.from(el.querySelectorAll('img')) as HTMLImageElement[];
    const onImgLoad = () => update();
    for (const img of imgs) {
      if (img.complete) continue;
      img.addEventListener('load', onImgLoad);
      img.addEventListener('error', onImgLoad);
    }
    return () => {
      cancelAnimationFrame(raf);
      el.removeEventListener('scroll', update);
      ro.disconnect();
      for (const img of imgs) {
        img.removeEventListener('load', onImgLoad);
        img.removeEventListener('error', onImgLoad);
      }
    };
  }, [frames.length]);

  function scrollByPage(dir: 1 | -1): void {
    const el = framesRef.current;
    if (!el) return;
    el.scrollBy({ left: dir * Math.max(200, el.clientWidth * 0.8), behavior: 'smooth' });
  }

  return (
    <a
      className="scen-strip"
      data-testid={`scenario-strip-${entry.id}`}
      href={`#/scenarios/${entry.id}`}
    >
      <div className="scen-strip__title">{entry.title}</div>
      <div className="scen-strip__body">
        <div className="scen-strip__scroller">
          <button
            type="button"
            className="scen-strip__chevron scen-strip__chevron--prev"
            data-testid={`strip-chevron-prev-${entry.id}`}
            aria-label="scroll left"
            hidden={!canScrollLeft}
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              scrollByPage(-1);
            }}
          >
            ‹
          </button>
          <div className="scen-strip__frames" ref={framesRef}>
            {frames.map((src, i) => {
              // Eager-load the first row's first few frames for above-the-fold
              // rendering; lazy-load everything else so vertical scroll is smooth.
              const eager = isFirst && i < 6;
              return (
                <button
                  key={`${src}-${i}`}
                  type="button"
                  className="scen-strip__frame"
                  data-testid={`strip-frame-${entry.id}-${i}`}
                  onClick={(e) => {
                    // Frame is inside an <a> row. Prevent the anchor from
                    // navigating so clicking a screenshot opens the lightbox
                    // in place rather than jumping to the detail page.
                    e.preventDefault();
                    e.stopPropagation();
                    onOpenAt(entry.id, i);
                  }}
                >
                  <img
                    src={src}
                    alt={`${entry.title} step ${i + 1}`}
                    loading={eager ? 'eager' : 'lazy'}
                    decoding="async"
                    width={320}
                    height={180}
                  />
                  <span className="strip-n">{i + 1}</span>
                </button>
              );
            })}
          </div>
          <button
            type="button"
            className="scen-strip__chevron scen-strip__chevron--next"
            data-testid={`strip-chevron-next-${entry.id}`}
            aria-label="scroll right"
            hidden={!canScrollRight}
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              scrollByPage(1);
            }}
          >
            ›
          </button>
        </div>
      </div>
    </a>
  );
}

function Grid({
  manifest,
  traceScenarioIds,
  groupFilter,
  groups,
  onSelect,
}: {
  manifest: ScenariosManifest;
  traceScenarioIds: Set<string>;
  groupFilter: string | null;
  groups: FeatureGroup[];
  onSelect: (id: string) => void;
}) {
  const [query, setQuery] = useState('');
  const [tileSize, setTileSize] = useState<number>(() =>
    typeof window === 'undefined' ? TILE_SIZE_DEFAULT : readTileSize(),
  );
  const [view, setView] = useState<GalleryView>(() =>
    typeof window === 'undefined' ? GALLERY_VIEW_DEFAULT : readGalleryView(),
  );
  const [stripLightbox, setStripLightbox] = useState<{
    scenarioId: string;
    index: number;
  } | null>(null);

  const filtered = useMemo(() => {
    let items = manifest.scenarios;
    if (groupFilter) {
      const match = groups.find((g) => g.slug === groupFilter);
      const allowed = new Set(match?.scenarioIds ?? []);
      items = items.filter((s) => allowed.has(s.id));
    }
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (s) =>
        s.title.toLowerCase().includes(q) ||
        s.id.toLowerCase().includes(q) ||
        (s.tags ?? []).some((t) => t.toLowerCase().includes(q)),
    );
  }, [manifest, query, groupFilter, groups]);

  void traceScenarioIds;

  function onTileSizeChange(e: React.ChangeEvent<HTMLInputElement>): void {
    const next = clampTileSize(Number(e.currentTarget.value));
    setTileSize(next);
    writeTileSize(next);
  }

  function pickView(next: GalleryView): void {
    setView(next);
    writeGalleryView(next);
  }

  const stripScenario =
    stripLightbox !== null
      ? manifest.scenarios.find((s) => s.id === stripLightbox.scenarioId) ??
        null
      : null;
  const stripScreenshots =
    stripScenario !== null
      ? (stripScenario.steps ?? [])
          .map((s) => s.screenshot)
          .filter((s): s is string => Boolean(s))
      : [];

  return (
    <div>
      <div className="scen-toolbar" data-testid="scenario-toolbar">
        <input
          data-testid="scenario-search"
          placeholder="search scenarios"
          value={query}
          onChange={(e) => setQuery(e.currentTarget.value)}
        />
        <label className="scen-toolbar__size">
          tile size{' '}
          <input
            type="range"
            min={TILE_SIZE_MIN}
            max={TILE_SIZE_MAX}
            step={10}
            list="tile-size-stops"
            value={tileSize}
            onChange={onTileSizeChange}
            data-testid="tile-size-slider"
          />
          <datalist id="tile-size-stops">
            {TILE_SIZE_STOPS.map((s) => (
              <option key={s} value={String(s)} />
            ))}
          </datalist>
          <span className="scen-toolbar__readout" data-testid="tile-size-readout">
            {tileSize}px
          </span>
        </label>
        <div className="scen-toolbar__view" role="group" aria-label="view">
          <button
            type="button"
            data-testid="view-toggle-gif"
            aria-pressed={view === 'gif'}
            className={view === 'gif' ? 'is-active' : ''}
            onClick={() => pickView('gif')}
          >
            GIF cards
          </button>
          <button
            type="button"
            data-testid="view-toggle-strip"
            aria-pressed={view === 'strip'}
            className={view === 'strip' ? 'is-active' : ''}
            onClick={() => pickView('strip')}
          >
            Screenshot strips
          </button>
        </div>
      </div>
      {view === 'gif' ? (
        <div
          className="scen-grid"
          data-testid="scenario-grid"
          style={{ ['--tile-size' as string]: `${tileSize}px` }}
        >
          {filtered.map((s) => {
            const media = s.gif ?? s.thumbnail;
            return (
              <button
                key={s.id}
                type="button"
                className="scen-card"
                data-testid={`scenario-card-${s.id}`}
                onClick={() => onSelect(s.id)}
              >
                {media ? (
                  <img
                    src={media}
                    alt={s.title}
                    className="scen-card__media"
                    loading="lazy"
                    decoding="async"
                    width={320}
                    height={180}
                  />
                ) : (
                  <div className="scen-card__media" />
                )}
                <div
                  className="scen-card__title"
                  data-testid={`scenario-card-title-${s.id}`}
                  title={s.title}
                >
                  {s.title}
                </div>
              </button>
            );
          })}
        </div>
      ) : (
        <div
          className="scen-strips"
          data-testid="scenario-strips"
          style={{ ['--tile-size' as string]: `${tileSize}px` }}
        >
          {filtered.map((s, i) => (
            <StripRow
              key={s.id}
              entry={s}
              isFirst={i === 0}
              onOpenAt={(id, idx) =>
                setStripLightbox({ scenarioId: id, index: idx })
              }
            />
          ))}
        </div>
      )}
      <Lightbox
        state={
          stripLightbox === null
            ? { kind: 'closed' }
            : { kind: 'screenshot', index: stripLightbox.index }
        }
        screenshots={stripScreenshots}
        onClose={() => setStripLightbox(null)}
        onIndex={(i) =>
          setStripLightbox((prev) =>
            prev === null ? prev : { scenarioId: prev.scenarioId, index: i },
          )
        }
      />
    </div>
  );
}

function useScenariosHash() {
  const [state, setState] = useState(() =>
    typeof window === 'undefined'
      ? parseScenariosHash('')
      : parseScenariosHash(window.location.hash),
  );
  useEffect(() => {
    function onHash() {
      setState(parseScenariosHash(window.location.hash));
    }
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);
  return state;
}

function ScenariosBody({ data }: { data: ScenariosData }) {
  const { group, slug, view } = useScenariosHash();
  const selected =
    slug !== null
      ? data.scenarios.find((s) => slugify(s.id) === slug || s.id === slug) ??
        null
      : null;

  function onSelect(id: string) {
    window.location.hash = `#/scenarios/${id}`;
  }

  function onViewTrace(traceSlug: string) {
    window.location.hash = `#/traces?select=${encodeURIComponent(traceSlug)}`;
  }

  if (selected) {
    if (view === 'screenshots') {
      return <ScreenshotsPage entry={selected} />;
    }
    if (view === 'flow') {
      return <FlowPage entry={selected} />;
    }
    return (
      <Detail
        entry={selected}
        traceScenarioIds={data.traceScenarioIds}
        onViewTrace={onViewTrace}
      />
    );
  }
  return (
    <Grid
      manifest={data}
      traceScenarioIds={data.traceScenarioIds}
      groupFilter={group}
      groups={data.groups}
      onSelect={onSelect}
    />
  );
}

export const scenariosAspect: Aspect<ScenariosData> = {
  id: 'scenarios',
  title: 'Scenarios',
  icon: '▣',
  sourceRoots: ['frontend/e2e/scenarios'],
  artifacts: [
    {
      url: ARTIFACT_URL,
      label: 'manifest.json',
      repoPath: 'frontend/walkthroughs/gallery/manifest.json',
    },
  ],
  refreshCommand: 'npm --prefix frontend run walkthroughs:generate',
  refreshCwd: '<repo-root>',
  refreshDescription:
    're-runs scenario tests headed and captures GIFs, screenshots, and step transcripts.',
  suppressRefresh: (hash: string) => {
    // Hide refresh trigger on scenario detail drill-downs
    // (#/scenarios/<slug>, #/scenarios/<slug>/screenshots, etc.)
    return /^#\/?scenarios\/[^?]+/.test(hash);
  },
  load: async () => {
    const { data } = await loadArtifact<unknown>(ARTIFACT_URL);
    const manifest = validate(data);
    const traceScenarioIds = await fetchTraceIndex();
    const groups = groupByFeature(manifest.scenarios);
    // Warn once on unmatched ids.
    const unmatched = manifest.scenarios
      .map((s) => slugify(s.id))
      .filter((slug) => !traceScenarioIds.has(slug));
    if (traceScenarioIds.size > 0 && unmatched.length > 0) {
      console.warn(
        '[dev-dashboard] scenarios without matching trace dirs:',
        unmatched,
      );
    }
    return { ...manifest, traceScenarioIds, groups };
  },
  render: (data) => <ScenariosBody data={data} />,
};

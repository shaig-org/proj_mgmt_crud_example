import React, { useEffect, useMemo, useRef, useState } from 'react';
import type { Aspect } from '../types';
import { ArtifactSchemaError, loadArtifact } from '../../lib/loadArtifact';
import type { ScenarioEntry, ScenariosManifest } from './types';
import {
  groupByFeature,
  parseScenariosHash,
  type FeatureGroup,
} from './grouping';

const ARTIFACT_URL = '/artifacts/scenarios/manifest.json';

function resolveMediaUrl(rel: string | undefined): string | undefined {
  if (!rel) return undefined;
  if (rel.startsWith('/') || rel.startsWith('http')) return rel;
  return `/artifacts/scenarios/${rel.replace(/^\.?\//, '')}`;
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

const VIDEO_SPEEDS = [0.1, 0.15, 0.25, 0.5, 1, 1.5, 2] as const;

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
  const shown = screenshots.slice(0, 5);
  const total = screenshots.length;
  return (
    <div className="detail__strip" data-testid="screenshot-strip">
      {shown.map((src, i) => (
        <button
          key={`${src}-${i}`}
          type="button"
          className="detail__strip-thumb"
          data-testid={`strip-thumb-${i}`}
          onClick={() => onOpen(i)}
        >
          <img src={src} alt={`screenshot ${i + 1} of ${total}`} />
        </button>
      ))}
      <a
        href={`#/scenarios/${entryId}/screenshots`}
        className="detail__strip-more"
        data-testid="view-all-screenshots"
      >
        view all ({total})
      </a>
    </div>
  );
}

function VideoBlock({ src }: { src: string }) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  function onSpeedChange(e: React.ChangeEvent<HTMLSelectElement>): void {
    const rate = Number(e.currentTarget.value);
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
      />
      <div className="detail__video-controls">
        <label>
          speed{' '}
          <select
            data-testid="video-speed"
            defaultValue="1"
            onChange={onSpeedChange}
          >
            {VIDEO_SPEEDS.map((s) => (
              <option key={s} value={String(s)}>
                {s}x
              </option>
            ))}
          </select>
        </label>
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
  return (
    <div className="lightbox__video-wrap">
      <video
        ref={ref}
        className="lightbox__video"
        data-testid="lightbox-video"
        src={src}
        controls
        autoPlay
      />
      <div className="lightbox__video-controls">
        <label>
          speed{' '}
          <select
            data-testid="lightbox-video-speed"
            defaultValue="1"
            onChange={(e) => {
              const rate = Number(e.currentTarget.value);
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

      <div className="detail__media-row">
        {entry.gif && (
          <button
            type="button"
            className="detail__media detail__media--flipbook"
            data-testid="detail-flipbook"
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

      <MetadataKV
        entry={entry}
        hasTrace={hasTrace}
        onViewTrace={() => onViewTrace(traceSlug)}
      />
      <StepList entry={entry} />

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

  void traceScenarioIds; // used in detail view
  return (
    <div>
      <div style={{ marginBottom: 'var(--space-3)' }}>
        <input
          data-testid="scenario-search"
          placeholder="search scenarios"
          value={query}
          onChange={(e) => setQuery(e.currentTarget.value)}
        />
      </div>
      <div className="scen-grid" data-testid="scenario-grid">
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
                <img src={media} alt={s.title} className="scen-card__media" />
              ) : (
                <div className="scen-card__media" />
              )}
              <div className="scen-card__title">{s.title}</div>
            </button>
          );
        })}
      </div>
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

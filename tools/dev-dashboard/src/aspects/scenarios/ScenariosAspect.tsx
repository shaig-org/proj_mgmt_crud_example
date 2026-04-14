import { useEffect, useMemo, useState } from 'react';
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
      ? (r.steps as Record<string, unknown>[]).map((s, idx) => ({
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
        }))
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
      video: resolveMediaUrl(video),
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

function Detail({
  entry,
  traceScenarioIds,
  onViewTrace,
}: {
  entry: ScenarioEntry;
  traceScenarioIds: Set<string>;
  onViewTrace: (slug: string) => void;
}) {
  const slug = slugify(entry.id);
  const hasTrace = traceScenarioIds.has(slug);
  return (
    <div data-testid="scenario-detail">
      <Breadcrumb entry={entry} />
      <h3>{entry.title}</h3>
      {entry.video ? (
        <video
          data-testid="scenario-video"
          src={entry.video}
          controls
          style={{ maxWidth: '100%' }}
        />
      ) : entry.thumbnail ? (
        <img src={entry.thumbnail} alt={entry.title} style={{ maxWidth: '100%' }} />
      ) : null}
      {entry.steps && entry.steps.length > 0 && (
        <ol data-testid="scenario-steps">
          {entry.steps.map((s) => (
            <li key={s.index}>{s.label}</li>
          ))}
        </ol>
      )}
      {entry.correlationId && (
        <div>
          Correlation ID: <code>{entry.correlationId}</code>
        </div>
      )}
      {hasTrace && (
        <button
          type="button"
          data-testid="view-trace-link"
          onClick={() => onViewTrace(slug)}
        >
          View trace →
        </button>
      )}
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
    // For now all sub-views (detail, screenshots, flow) render Detail; the
    // dedicated screenshots/flow pages arrive in a later slice. `view` is
    // still parsed so deep links round-trip correctly.
    void view;
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

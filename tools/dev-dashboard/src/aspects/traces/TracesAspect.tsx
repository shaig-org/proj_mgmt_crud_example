import { useEffect, useMemo, useState } from 'react';
import type { Aspect } from '../types';
import {
  ArtifactMissingError,
  loadArtifact,
  loadArtifactText,
} from '../../lib/loadArtifact';
import type { TraceEntry, TracesData } from './types';

const BASE = '/artifacts/traces';

interface DirListing {
  entries: Array<{ name: string; type: 'dir' | 'file' }>;
}

async function listDir(url: string): Promise<DirListing | null> {
  try {
    const resp = await fetch(url);
    if (!resp.ok) return null;
    return (await resp.json()) as DirListing;
  } catch {
    return null;
  }
}

async function loadEntry(id: string): Promise<TraceEntry> {
  const listing = await listDir(`${BASE}/${id}/`);
  const names = new Set(listing?.entries.map((e) => e.name) ?? []);
  let summary: TraceEntry['summary'] = null;
  if (names.has('summary.json')) {
    try {
      const { data } = await loadArtifact<Record<string, unknown>>(
        `${BASE}/${id}/summary.json`,
      );
      const s: TraceEntry['summary'] = {
        scenarioId: typeof data.scenarioId === 'string' ? data.scenarioId : id,
        title: typeof data.title === 'string' ? data.title : undefined,
        coveredFiles: Array.isArray(data.coveredFiles)
          ? (data.coveredFiles as unknown[]).filter(
              (x): x is string => typeof x === 'string',
            )
          : undefined,
      };
      summary = s;
    } catch (e) {
      if (!(e instanceof ArtifactMissingError)) throw e;
    }
  }
  return {
    id,
    hasMermaid: names.has('mermaid.md'),
    hasFlame: names.has('flame.html'),
    hasFolded: names.has('folded.txt'),
    summary,
  };
}

async function loadTraces(): Promise<TracesData> {
  const listing = await listDir(`${BASE}/`);
  if (!listing) throw new ArtifactMissingError(`${BASE}/`);
  const dirEntries = listing.entries.filter((e) => e.type === 'dir');
  if (dirEntries.length === 0) throw new ArtifactMissingError(`${BASE}/`);
  const dirNames = listing.entries
    .filter((e) => e.type === 'dir')
    .map((e) => e.name);
  const entries: TraceEntry[] = [];
  for (const name of dirNames) {
    entries.push(await loadEntry(name));
  }
  return { entries };
}

function MermaidView({ text }: { text: string }) {
  const [svg, setSvg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const mermaid = (await import('mermaid')).default;
        mermaid.initialize({ startOnLoad: false });
        const id = `mmd-${Math.random().toString(36).slice(2)}`;
        const result = await mermaid.render(id, text);
        if (!cancelled) setSvg(result.svg);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [text]);

  if (error) {
    return (
      <div>
        <p>Mermaid render failed: {error}</p>
        <pre>{text}</pre>
      </div>
    );
  }
  if (!svg) return <pre data-testid="mermaid-loading">{text}</pre>;
  return (
    <div
      data-testid="mermaid-svg"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}

function SelectedTrace({ entry }: { entry: TraceEntry }) {
  const [mermaidText, setMermaidText] = useState<string | null>(null);
  const [folded, setFolded] = useState<string | null>(null);
  const [foldedExpanded, setFoldedExpanded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setMermaidText(null);
    setFolded(null);
    setFoldedExpanded(false);
    if (entry.hasMermaid) {
      void loadArtifactText(`${BASE}/${entry.id}/mermaid.md`).then((r) => {
        if (!cancelled) setMermaidText(r.data);
      });
    }
    return () => {
      cancelled = true;
    };
  }, [entry]);

  async function expandFolded() {
    if (folded !== null) {
      setFoldedExpanded(true);
      return;
    }
    const r = await loadArtifactText(`${BASE}/${entry.id}/folded.txt`);
    setFolded(r.data);
    setFoldedExpanded(true);
  }

  return (
    <div data-testid="trace-detail">
      <h3>{entry.summary?.title ?? entry.id}</h3>
      {entry.hasMermaid && mermaidText && <MermaidView text={mermaidText} />}
      {entry.hasFlame && (
        <>
          <h4>Flame graph</h4>
          <iframe
            data-testid="flame-iframe"
            src={`${BASE}/${entry.id}/flame.html`}
            sandbox="allow-scripts allow-same-origin"
            title={`flame graph for ${entry.id}`}
            className="trace-iframe"
          />
          <a
            href={`${BASE}/${entry.id}/flame.html`}
            target="_blank"
            rel="noreferrer"
          >
            open in new tab
          </a>
        </>
      )}
      {entry.hasFolded && (
        <div>
          <button
            type="button"
            data-testid="folded-expand"
            onClick={expandFolded}
            aria-expanded={foldedExpanded}
          >
            {foldedExpanded ? 'Folded stacks ▾' : 'Folded stacks ▸ (expand)'}
          </button>
          {foldedExpanded && folded !== null && (
            <pre data-testid="folded-content">{folded}</pre>
          )}
        </div>
      )}
    </div>
  );
}

function TracesBody({ data }: { data: TracesData }) {
  const [selectedId, setSelectedId] = useState<string | null>(
    data.entries[0]?.id ?? null,
  );

  // Honor ?select=<slug> query in hash for scenarios→trace cross-link.
  useEffect(() => {
    const match = /select=([^&]+)/.exec(window.location.hash);
    if (match) {
      const target = decodeURIComponent(match[1]);
      const found = data.entries.find((e) => e.id === target);
      if (found) setSelectedId(found.id);
    }
  }, [data]);

  const selected = useMemo(
    () => data.entries.find((e) => e.id === selectedId) ?? null,
    [data, selectedId],
  );

  const anyHasCoveredFiles = data.entries.some(
    (e) => (e.summary?.coveredFiles?.length ?? 0) > 0,
  );

  return (
    <div className="trace-layout">
      <div className="trace-list" data-testid="trace-list">
        <input
          data-testid="trace-search"
          placeholder="covering file…"
          disabled={!anyHasCoveredFiles}
          title={
            anyHasCoveredFiles
              ? 'Filter scenarios by covered file path'
              : 'coveredFiles not present in summary.json — search disabled (v2 feature)'
          }
          onChange={(e) => {
            const q = e.currentTarget.value.trim().toLowerCase();
            if (!q) return;
            const hit = data.entries.find((entry) =>
              (entry.summary?.coveredFiles ?? []).some((f) =>
                f.toLowerCase().includes(q),
              ),
            );
            if (hit) setSelectedId(hit.id);
          }}
        />
        {data.entries.length === 0 ? (
          <div className="empty">No trace scenarios found.</div>
        ) : (
          data.entries.map((e) => (
            <button
              key={e.id}
              type="button"
              aria-selected={e.id === selectedId}
              data-testid={`trace-item-${e.id}`}
              onClick={() => setSelectedId(e.id)}
            >
              {e.id}
            </button>
          ))
        )}
      </div>
      <div>
        {selected ? (
          <SelectedTrace entry={selected} />
        ) : (
          <div className="empty">Select a scenario to view its trace.</div>
        )}
      </div>
    </div>
  );
}

export const tracesAspect: Aspect<TracesData> = {
  id: 'traces',
  title: 'Traces',
  icon: '▣',
  sourceRoots: ['backend/project_management_crud_example', 'backend/tests'],
  artifacts: [
    {
      url: `${BASE}/`,
      label: '.trace-artifacts/',
      repoPath: 'backend/.trace-artifacts/',
    },
  ],
  refreshCommand: 'npm --prefix frontend run e2e:scenarios',
  refreshCwd: '<repo-root>',
  refreshDescription:
    're-runs scenario tests; pytest-tracer writes per-scenario trace artifacts under backend/.trace-artifacts/.',
  load: loadTraces,
  render: (data) => <TracesBody data={data} />,
};

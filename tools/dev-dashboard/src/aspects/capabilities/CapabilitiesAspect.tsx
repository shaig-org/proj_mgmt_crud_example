import { useMemo, useState, useCallback } from 'react';
import type { Aspect } from '../types';
import {
  ArtifactMissingError,
  ArtifactSchemaError,
  loadArtifact,
} from '../../lib/loadArtifact';
import type {
  CapabilitiesData,
  CapabilityDocument,
  CapabilityRow,
  CapabilityStatus,
  GitDiffData,
  GitDiffDocument,
  GitDiffSummary,
} from './types';
import { buildRows, parseGitDiff } from './classifier';

const BASELINE_URL = '/artifacts/capabilities/baseline.json';
const REPORT_URL = '/artifacts/capabilities/report.json';
const GIT_DIFF_URL = '/artifacts/capabilities/git-diff.json';

function validate(doc: unknown, url: string): CapabilityDocument {
  if (typeof doc !== 'object' || doc === null) {
    throw new ArtifactSchemaError(url, 'root');
  }
  const d = doc as { routes?: unknown };
  if (!Array.isArray(d.routes)) {
    throw new ArtifactSchemaError(url, 'routes');
  }
  const routes = d.routes.map((r, i) => {
    if (typeof r !== 'object' || r === null) {
      throw new ArtifactSchemaError(url, `routes[${i}]`);
    }
    const obj = r as Record<string, unknown>;
    if (typeof obj.method !== 'string') {
      throw new ArtifactSchemaError(url, `routes[${i}].method`);
    }
    if (typeof obj.path !== 'string') {
      throw new ArtifactSchemaError(url, `routes[${i}].path`);
    }
    if (typeof obj.handler !== 'string') {
      throw new ArtifactSchemaError(url, `routes[${i}].handler`);
    }
    if (!Array.isArray(obj.capabilities)) {
      throw new ArtifactSchemaError(url, `routes[${i}].capabilities`);
    }
    return {
      method: obj.method,
      path: obj.path,
      handler: obj.handler,
      capabilities: obj.capabilities.filter(
        (c): c is string => typeof c === 'string',
      ),
    };
  });
  return { routes };
}

function validateGitDiff(doc: unknown, url: string): GitDiffDocument {
  if (typeof doc !== 'object' || doc === null) {
    throw new ArtifactSchemaError(url, 'root');
  }
  const d = doc as Record<string, unknown>;
  if (typeof d.from_ref !== 'string') throw new ArtifactSchemaError(url, 'from_ref');
  if (typeof d.to_ref !== 'string') throw new ArtifactSchemaError(url, 'to_ref');
  if (typeof d.from_commit !== 'string') throw new ArtifactSchemaError(url, 'from_commit');
  if (typeof d.to_commit !== 'string') throw new ArtifactSchemaError(url, 'to_commit');
  if (typeof d.generated_at !== 'string') throw new ArtifactSchemaError(url, 'generated_at');
  if (!Array.isArray(d.routes)) throw new ArtifactSchemaError(url, 'routes');
  if (typeof d.summary !== 'object' || d.summary === null) {
    throw new ArtifactSchemaError(url, 'summary');
  }
  return doc as GitDiffDocument;
}

const STATUS_ORDER: CapabilityStatus[] = [
  'expanded',
  'reduced',
  'new',
  'removed',
  'unchanged',
];

type FilterMode = 'all' | CapabilityStatus;
type DiffMode = 'current' | 'baseline' | 'diff';

/**
 * Render capability names without the trailing `Capability` suffix, which is
 * boilerplate on every concrete capability class name. Raw strings stay
 * untouched in the data model so search can still match either form.
 */
export function formatCapability(raw: string): string {
  return raw.replace(/Capability$/, '');
}

function CapabilitiesBody({ data }: { data: CapabilitiesData }) {
  const [filter, setFilter] = useState<FilterMode>('all');
  const [diffMode, setDiffMode] = useState<DiffMode>('current');
  const [query, setQuery] = useState<string>('');
  // Live git diff state — starts from loaded data, updated in-place after a run.
  const [gitDiff, setGitDiff] = useState<GitDiffData | null>(data.gitDiff);

  const visible = useMemo(() => {
    let rows = data.rows;
    if (diffMode === 'diff') {
      rows = rows.filter((r) => r.status !== 'unchanged');
    }
    if (filter !== 'all') {
      rows = rows.filter((r) => r.status === filter);
    }
    const q = query.trim().toLowerCase();
    if (q) {
      rows = rows.filter((r) => {
        const caps = [...(r.current ?? []), ...(r.baseline ?? [])];
        return (
          r.method.toLowerCase().includes(q) ||
          r.path.toLowerCase().includes(q) ||
          r.handler.toLowerCase().includes(q) ||
          caps.some((c) => c.toLowerCase().includes(q))
        );
      });
    }
    return rows;
  }, [data, filter, diffMode, query]);

  const handleDiffComplete = useCallback((updated: GitDiffData) => {
    setGitDiff(updated);
  }, []);

  return (
    <div>
      {!data.hasReport && (
        <div
          className="badge badge--stale"
          data-testid="baseline-only-banner"
          style={{ display: 'block', marginBottom: 'var(--space-3)' }}
        >
          report.json missing — showing baseline only. Diff toggle disabled.
        </div>
      )}
      <div style={{ display: 'flex', gap: 'var(--space-3)', marginBottom: 'var(--space-3)', flexWrap: 'wrap', alignItems: 'center' }}>
        <input
          data-testid="cap-search"
          placeholder="search by method, path, handler, or capability…"
          value={query}
          onChange={(e) => setQuery(e.currentTarget.value)}
          style={{ minWidth: '280px' }}
        />
        <label>
          Filter:{' '}
          <select
            data-testid="cap-filter"
            value={filter}
            onChange={(e) => setFilter(e.currentTarget.value as FilterMode)}
          >
            <option value="all">all</option>
            {STATUS_ORDER.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label>
          Diff:{' '}
          <select
            data-testid="cap-diff"
            value={diffMode}
            disabled={!data.hasReport}
            onChange={(e) => setDiffMode(e.currentTarget.value as DiffMode)}
          >
            <option value="current">current</option>
            <option value="baseline">baseline</option>
            <option value="diff">diff</option>
          </select>
        </label>
      </div>
      <table className="cap-table" data-testid="cap-table">
        <thead>
          <tr>
            <th>Method</th>
            <th>Path</th>
            <th>Capabilities</th>
            <th>Status</th>
            <th>Handler</th>
          </tr>
        </thead>
        <tbody>
          {visible.length === 0 ? (
            <tr>
              <td colSpan={5} className="empty">
                No routes match the current filter.
              </td>
            </tr>
          ) : (
            visible.map((r) => <Row key={`${r.method} ${r.path}`} row={r} diffMode={diffMode} />)
          )}
        </tbody>
      </table>

      <GitDiffPanel gitDiff={gitDiff} onComplete={handleDiffComplete} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Git diff panel (trigger form + optional results)
// ---------------------------------------------------------------------------

const STATUS_COLORS: Record<CapabilityStatus, string> = {
  expanded: 'var(--expanded, #c0392b)',
  new: 'var(--new, #b7950b)',
  reduced: 'var(--reduced, #2e7d32)',
  removed: 'var(--removed, #666)',
  unchanged: 'var(--text-muted, #888)',
};

function SummaryChip({ status, count }: { status: CapabilityStatus; count: number }) {
  if (count === 0) return null;
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        padding: '2px 8px',
        borderRadius: '12px',
        fontSize: '12px',
        fontWeight: 500,
        background: 'var(--surface-2, #f4f4f4)',
        color: STATUS_COLORS[status],
        border: `1px solid currentColor`,
      }}
    >
      {status}: {count}
    </span>
  );
}

function GitDiffSummaryBar({ summary }: { summary: GitDiffSummary }) {
  return (
    <div
      data-testid="git-diff-summary"
      style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap', alignItems: 'center' }}
    >
      <SummaryChip status="expanded" count={summary.expanded} />
      <SummaryChip status="new" count={summary.new} />
      <SummaryChip status="reduced" count={summary.reduced} />
      <SummaryChip status="removed" count={summary.removed} />
      <span style={{ fontSize: '12px', color: 'var(--text-muted, #888)' }}>
        {summary.unchanged} unchanged · {summary.total} total
      </span>
    </div>
  );
}

async function fetchGitDiff(): Promise<GitDiffData | null> {
  try {
    const { data: raw } = await loadArtifact<unknown>(GIT_DIFF_URL);
    return parseGitDiff(validateGitDiff(raw, GIT_DIFF_URL));
  } catch {
    return null;
  }
}

// Special sentinel — reads the on-disk baseline.json (includes uncommitted edits).
const WORKING_TREE_REF = 'WORKING';

const PRESETS: Array<{ label: string; from: string; to: string; title: string }> = [
  { label: 'main → HEAD', from: 'main', to: 'HEAD', title: 'Committed changes on this branch vs main' },
  { label: 'main → working tree', from: 'main', to: WORKING_TREE_REF, title: 'Everything since main, incl. uncommitted baseline edits' },
  { label: 'HEAD → working tree', from: 'HEAD', to: WORKING_TREE_REF, title: 'Only uncommitted changes to baseline.json' },
];

type RunState =
  | { phase: 'idle' }
  | { phase: 'running' }
  | { phase: 'error'; message: string };

function GitDiffPanel({
  gitDiff: initialGitDiff,
  onComplete,
}: {
  gitDiff: GitDiffData | null;
  onComplete: (updated: GitDiffData) => void;
}) {
  const [fromRef, setFromRef] = useState(initialGitDiff?.fromRef ?? 'main');
  const [toRef, setToRef] = useState(initialGitDiff?.toRef ?? 'HEAD');
  const [run, setRun] = useState<RunState>({ phase: 'idle' });
  const [showAll, setShowAll] = useState(false);
  const [query, setQuery] = useState('');

  const gitDiff = initialGitDiff; // driven from parent state via onComplete

  const handleRun = useCallback(async () => {
    setRun({ phase: 'running' });
    try {
      const resp = await fetch('/api/run-diff/capabilities', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ from: fromRef, to: toRef }),
      });
      const result = (await resp.json()) as { ok: boolean; error?: string; stdout?: string };
      if (!result.ok) {
        setRun({ phase: 'error', message: result.error ?? 'Unknown error' });
        return;
      }
      // Re-fetch the artifact and bubble it up.
      const updated = await fetchGitDiff();
      if (updated) {
        onComplete(updated);
        setRun({ phase: 'idle' });
      } else {
        setRun({ phase: 'error', message: 'Diff ran but artifact could not be loaded.' });
      }
    } catch (e) {
      setRun({ phase: 'error', message: String(e) });
    }
  }, [fromRef, toRef, onComplete]);

  const rows = useMemo(() => {
    if (!gitDiff) return [];
    let result = showAll
      ? gitDiff.rows
      : gitDiff.rows.filter((r) => r.status !== 'unchanged');
    const q = query.trim().toLowerCase();
    if (q) {
      result = result.filter((r) => {
        const caps = [...(r.current ?? []), ...(r.baseline ?? [])];
        return (
          r.method.toLowerCase().includes(q) ||
          r.path.toLowerCase().includes(q) ||
          r.handler.toLowerCase().includes(q) ||
          caps.some((c) => c.toLowerCase().includes(q))
        );
      });
    }
    return result;
  }, [gitDiff, showAll, query]);

  const shortFrom = gitDiff?.fromCommit.slice(0, 8);
  const shortTo = gitDiff?.toCommit.slice(0, 8);

  return (
    <div
      data-testid="git-diff-section"
      style={{
        marginTop: 'var(--space-5)',
        paddingTop: 'var(--space-4)',
        borderTop: '1px solid var(--border, #e0e0e0)',
      }}
    >
      {/* Header */}
      <div style={{ marginBottom: 'var(--space-3)' }}>
        <h3 style={{ margin: '0 0 var(--space-3) 0', fontSize: '15px', fontWeight: 600 }}>
          Git Diff
        </h3>

        {/* Presets */}
        <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap', marginBottom: 'var(--space-2)' }}>
          {PRESETS.map((p) => {
            const active = fromRef === p.from && toRef === p.to;
            return (
              <button
                key={p.label}
                title={p.title}
                disabled={run.phase === 'running'}
                onClick={() => { setFromRef(p.from); setToRef(p.to); }}
                style={{
                  fontSize: '12px',
                  padding: '2px 10px',
                  borderRadius: '12px',
                  fontFamily: 'var(--font-mono, monospace)',
                  background: active ? 'var(--accent, #1a73e8)' : undefined,
                  color: active ? '#fff' : undefined,
                  cursor: 'pointer',
                }}
              >
                {p.label}
              </button>
            );
          })}
        </div>

        {/* Trigger form */}
        <div
          data-testid="git-diff-trigger"
          style={{
            display: 'flex',
            gap: 'var(--space-2)',
            alignItems: 'center',
            flexWrap: 'wrap',
            marginBottom: 'var(--space-3)',
          }}
        >
          <label style={{ fontSize: '13px', display: 'flex', alignItems: 'center', gap: 'var(--space-1)' }}>
            From
            <input
              data-testid="git-diff-from"
              value={fromRef}
              onChange={(e) => setFromRef(e.currentTarget.value)}
              style={{ width: '140px', fontFamily: 'var(--font-mono, monospace)', fontSize: '12px' }}
              disabled={run.phase === 'running'}
            />
          </label>
          <label style={{ fontSize: '13px', display: 'flex', alignItems: 'center', gap: 'var(--space-1)' }}>
            To
            <input
              data-testid="git-diff-to"
              value={toRef}
              onChange={(e) => setToRef(e.currentTarget.value)}
              style={{ width: '140px', fontFamily: 'var(--font-mono, monospace)', fontSize: '12px' }}
              disabled={run.phase === 'running'}
            />
          </label>
          <button
            data-testid="git-diff-run"
            onClick={() => void handleRun()}
            disabled={run.phase === 'running' || !fromRef || !toRef}
          >
            {run.phase === 'running' ? 'Running…' : 'Run diff'}
          </button>
          {run.phase === 'error' && (
            <span
              data-testid="git-diff-error"
              style={{ fontSize: '12px', color: STATUS_COLORS.expanded }}
            >
              {run.message}
            </span>
          )}
        </div>

        {/* Results header */}
        {gitDiff && (
          <>
            <div style={{ fontSize: '13px', color: 'var(--text-muted, #666)', marginBottom: 'var(--space-2)', fontFamily: 'var(--font-mono, monospace)' }}>
              <span style={{ color: STATUS_COLORS.removed }}>{gitDiff.fromRef}</span>
              {' '}({shortFrom})
              {' → '}
              <span style={{ color: STATUS_COLORS.new }}>{gitDiff.toRef}</span>
              {' '}({shortTo})
              <span style={{ marginLeft: 'var(--space-2)', fontFamily: 'inherit' }}>
                · generated {new Date(gitDiff.generatedAt).toLocaleString()}
              </span>
            </div>
            <GitDiffSummaryBar summary={gitDiff.summary} />
          </>
        )}
      </div>

      {/* Results table */}
      {gitDiff ? (
        <>
          <div style={{ display: 'flex', gap: 'var(--space-3)', marginBottom: 'var(--space-3)', flexWrap: 'wrap', alignItems: 'center' }}>
            <input
              data-testid="git-diff-search"
              placeholder="search routes…"
              value={query}
              onChange={(e) => setQuery(e.currentTarget.value)}
              style={{ minWidth: '240px' }}
            />
            <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-1)', fontSize: '13px' }}>
              <input
                type="checkbox"
                data-testid="git-diff-show-all"
                checked={showAll}
                onChange={(e) => setShowAll(e.currentTarget.checked)}
              />
              {' '}show unchanged
            </label>
          </div>
          <table className="cap-table" data-testid="git-diff-table">
            <thead>
              <tr>
                <th>Method</th>
                <th>Path</th>
                <th>From → To capabilities</th>
                <th>Status</th>
                <th>Handler</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={5} className="empty">
                    {gitDiff.summary.unchanged === gitDiff.summary.total
                      ? 'No capability changes between these refs.'
                      : 'No routes match the search.'}
                  </td>
                </tr>
              ) : (
                rows.map((r) => (
                  <Row key={`${r.method} ${r.path}`} row={r} diffMode="diff" />
                ))
              )}
            </tbody>
          </table>
        </>
      ) : (
        <p style={{ fontSize: '13px', color: 'var(--text-muted, #888)', margin: 0 }}>
          Enter refs above and click <strong>Run diff</strong> to compare capability surfaces.
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared row component
// ---------------------------------------------------------------------------

function Row({ row, diffMode }: { row: CapabilityRow; diffMode: DiffMode }) {
  const shown =
    diffMode === 'baseline'
      ? row.baseline
      : diffMode === 'current'
        ? row.current
        : row.current;
  const added = row.added ?? [];
  const removed = row.removed ?? [];
  return (
    <tr
      data-status={row.status}
      data-testid={`cap-row-${row.method}-${row.path}`}
    >
      <td className="mono">{row.method}</td>
      <td className="mono">{row.path}</td>
      <td className="mono">
        {(shown ?? []).map(formatCapability).join(', ')}
        {added.length > 0 && (
          <span style={{ color: 'var(--new)' }}>
            {' '}
            +{added.map(formatCapability).join(',')}
          </span>
        )}
        {removed.length > 0 && (
          <span style={{ color: 'var(--removed)' }}>
            {' '}
            -{removed.map(formatCapability).join(',')}
          </span>
        )}
      </td>
      <td>{row.status}</td>
      <td className="mono">{row.handler}</td>
    </tr>
  );
}

export const capabilitiesAspect: Aspect<CapabilitiesData> = {
  id: 'capabilities',
  title: 'Capabilities',
  icon: '●',
  sourceRoots: ['backend/project_management_crud_example/routers'],
  artifacts: [
    {
      url: REPORT_URL,
      label: 'report.json',
      repoPath: 'backend/evidence/capabilities/report.json',
    },
    {
      url: BASELINE_URL,
      label: 'baseline.json',
      repoPath: 'backend/evidence/capabilities/baseline.json',
    },
    {
      url: GIT_DIFF_URL,
      label: 'git-diff.json',
      repoPath: 'backend/evidence/capabilities/git-diff.json',
    },
  ],
  refreshCommand:
    'uv --project backend run python -m project_management_crud_example.tools.analyze_capabilities',
  refreshCwd: '<repo-root>',
  refreshDescription:
    're-runs capability analysis against the current route handlers and writes report.json.',
  load: async () => {
    const { data: baselineRaw } = await loadArtifact<unknown>(BASELINE_URL);
    const baseline = validate(baselineRaw, BASELINE_URL);
    let report: CapabilityDocument | null = null;
    try {
      const { data: reportRaw } = await loadArtifact<unknown>(REPORT_URL);
      report = validate(reportRaw, REPORT_URL);
    } catch (e) {
      if (!(e instanceof ArtifactMissingError)) throw e;
    }
    let gitDiff: GitDiffData | null = null;
    try {
      const { data: gitDiffRaw } = await loadArtifact<unknown>(GIT_DIFF_URL);
      gitDiff = parseGitDiff(validateGitDiff(gitDiffRaw, GIT_DIFF_URL));
    } catch (e) {
      if (!(e instanceof ArtifactMissingError)) throw e;
    }
    return {
      rows: buildRows(baseline, report),
      hasReport: report !== null,
      gitDiff,
    };
  },
  render: (data) => <CapabilitiesBody data={data} />,
};

import { useMemo, useState } from 'react';
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
} from './types';
import { buildRows } from './classifier';

const BASELINE_URL = '/artifacts/capabilities/baseline.json';
const REPORT_URL = '/artifacts/capabilities/report.json';

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

const STATUS_ORDER: CapabilityStatus[] = [
  'expanded',
  'reduced',
  'new',
  'removed',
  'unchanged',
];

type FilterMode = 'all' | CapabilityStatus;
type DiffMode = 'current' | 'baseline' | 'diff';

function CapabilitiesBody({ data }: { data: CapabilitiesData }) {
  const [filter, setFilter] = useState<FilterMode>('all');
  const [diffMode, setDiffMode] = useState<DiffMode>('current');

  const visible = useMemo(() => {
    let rows = data.rows;
    if (diffMode === 'diff') {
      rows = rows.filter((r) => r.status !== 'unchanged');
    }
    if (filter !== 'all') {
      rows = rows.filter((r) => r.status === filter);
    }
    return rows;
  }, [data, filter, diffMode]);

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
      <div style={{ display: 'flex', gap: 'var(--space-3)', marginBottom: 'var(--space-3)' }}>
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
            <th>Status</th>
            <th>Handler</th>
            <th>Capabilities</th>
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
    </div>
  );
}

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
      <td>{row.status}</td>
      <td className="mono">{row.handler}</td>
      <td className="mono">
        {(shown ?? []).join(', ')}
        {added.length > 0 && (
          <span style={{ color: 'var(--new)' }}> +{added.join(',')}</span>
        )}
        {removed.length > 0 && (
          <span style={{ color: 'var(--removed)' }}> -{removed.join(',')}</span>
        )}
      </td>
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
    return {
      rows: buildRows(baseline, report),
      hasReport: report !== null,
    };
  },
  render: (data) => <CapabilitiesBody data={data} />,
};

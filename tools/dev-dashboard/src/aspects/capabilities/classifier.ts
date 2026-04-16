import type {
  CapabilityDocument,
  CapabilityRoute,
  CapabilityRow,
  CapabilityStatus,
  GitDiffDocument,
  GitDiffData,
} from './types';

function routeKey(r: Pick<CapabilityRoute, 'method' | 'path'>): string {
  return `${r.method.toUpperCase()} ${r.path}`;
}

function sortedUnique(xs: string[]): string[] {
  return Array.from(new Set(xs)).sort();
}

function diff(a: string[], b: string[]): { added: string[]; removed: string[] } {
  const setA = new Set(a);
  const setB = new Set(b);
  const added: string[] = [];
  const removed: string[] = [];
  for (const x of b) if (!setA.has(x)) added.push(x);
  for (const x of a) if (!setB.has(x)) removed.push(x);
  return { added: sortedUnique(added), removed: sortedUnique(removed) };
}

/**
 * Classify a single (baseline, current) pair for one route.
 *
 *  - baseline === null && current !== null → `new`
 *  - baseline !== null && current === null → `removed`
 *  - sets equal → `unchanged`
 *  - current ⊋ baseline → `expanded`
 *  - current ⊊ baseline → `reduced`
 *  - otherwise (both added and removed items) → `expanded` (precedence rule)
 */
export function classifyRoute(
  baseline: string[] | null,
  current: string[] | null,
): { status: CapabilityStatus; added: string[]; removed: string[] } {
  if (baseline === null && current !== null) {
    return { status: 'new', added: sortedUnique(current), removed: [] };
  }
  if (baseline !== null && current === null) {
    return { status: 'removed', added: [], removed: sortedUnique(baseline) };
  }
  if (baseline === null && current === null) {
    return { status: 'unchanged', added: [], removed: [] };
  }
  const { added, removed } = diff(baseline!, current!);
  if (added.length === 0 && removed.length === 0) {
    return { status: 'unchanged', added, removed };
  }
  if (added.length > 0 && removed.length === 0) {
    return { status: 'expanded', added, removed };
  }
  if (removed.length > 0 && added.length === 0) {
    return { status: 'reduced', added, removed };
  }
  return { status: 'expanded', added, removed };
}

/**
 * Join baseline.json and report.json by (method, path); produce one row per
 * unique route. If `report` is null, every baseline row becomes a row with
 * current === baseline (status: unchanged) — callers set a "baseline-only"
 * banner and disable the diff toggle.
 */
export function buildRows(
  baseline: CapabilityDocument,
  report: CapabilityDocument | null,
): CapabilityRow[] {
  const byKey = new Map<
    string,
    { baseline?: CapabilityRoute; current?: CapabilityRoute }
  >();

  for (const r of baseline.routes) {
    byKey.set(routeKey(r), { baseline: r });
  }
  if (report) {
    for (const r of report.routes) {
      const k = routeKey(r);
      const slot = byKey.get(k) ?? {};
      slot.current = r;
      byKey.set(k, slot);
    }
  } else {
    // Baseline-only: treat current as a copy of baseline for display.
    for (const r of baseline.routes) {
      byKey.get(routeKey(r))!.current = r;
    }
  }

  const rows: CapabilityRow[] = [];
  for (const [, { baseline: b, current: c }] of byKey.entries()) {
    const bCaps = b ? sortedUnique(b.capabilities) : null;
    const cCaps = c ? sortedUnique(c.capabilities) : null;
    const cls = classifyRoute(bCaps, cCaps);
    const representative = (c ?? b)!;
    rows.push({
      method: representative.method,
      path: representative.path,
      handler: representative.handler,
      baseline: bCaps,
      current: cCaps,
      status: cls.status,
      added: cls.added,
      removed: cls.removed,
    });
  }

  rows.sort((a, b) => {
    if (a.path !== b.path) return a.path.localeCompare(b.path);
    return a.method.localeCompare(b.method);
  });
  return rows;
}

/**
 * Convert a parsed git-diff.json document into the CapabilityRow format used
 * by the capabilities table. Each git diff route maps directly: from_capabilities
 * → baseline, to_capabilities → current.
 */
export function parseGitDiff(doc: GitDiffDocument): GitDiffData {
  const rows: CapabilityRow[] = doc.routes.map((r) => ({
    method: r.method,
    path: r.path,
    handler: r.handler,
    baseline: r.from_capabilities ? sortedUnique(r.from_capabilities) : null,
    current: r.to_capabilities ? sortedUnique(r.to_capabilities) : null,
    status: r.status,
    added: sortedUnique(r.added),
    removed: sortedUnique(r.removed),
  }));

  return {
    rows,
    fromRef: doc.from_ref,
    toRef: doc.to_ref,
    fromCommit: doc.from_commit,
    toCommit: doc.to_commit,
    generatedAt: doc.generated_at,
    summary: doc.summary,
  };
}

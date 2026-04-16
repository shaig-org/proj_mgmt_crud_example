export interface ScenarioLike {
  id: string;
  title: string;
  specFile?: string;
  feature?: string;
}

export interface FeatureGroup {
  /** Kebab-slug used in URL + test ids. */
  slug: string;
  /** Human-readable label shown in the rail. */
  label: string;
  /** Scenario ids (ordered, stable with input). */
  scenarioIds: string[];
}

const UNCATEGORIZED_SLUG = 'uncategorized';
const UNCATEGORIZED_LABEL = 'uncategorized';

function slugify(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
}

/**
 * Derive a feature label from a `specFile` path.
 *
 * Directory-based grouping relative to `e2e/scenarios/`:
 *   `e2e/scenarios/foo.scenario.spec.ts`          → `foo`              (top-level, standalone)
 *   `e2e/scenarios/auth/login.scenario.spec.ts`   → `auth`             (nested → dir path)
 *   `e2e/scenarios/auth/x/y.scenario.spec.ts`     → `auth/x`           (full dir path)
 *
 * Returns null when we cannot derive one (so callers can fall back to
 * the uncategorized bucket).
 */
export function deriveFeature(specFile: string | undefined): string | null {
  if (typeof specFile !== 'string') return null;
  const trimmed = specFile.trim();
  if (!trimmed) return null;
  // Normalize separators.
  const normalized = trimmed.replace(/\\/g, '/');
  // Find the scenarios root; everything after it is the grouping-relevant path.
  const marker = 'scenarios/';
  const markerIdx = normalized.indexOf(marker);
  const relative = markerIdx >= 0
    ? normalized.slice(markerIdx + marker.length)
    : normalized.split('/').pop() ?? normalized;
  const parts = relative.split('/').filter(Boolean);
  if (parts.length === 0) return null;
  if (parts.length === 1) {
    // Top-level file: group is the file's base name (one-item standalone group).
    const base = parts[0]!;
    const stripped = base
      .replace(/\.scenario\.spec\.ts$/i, '')
      .replace(/\.spec\.ts$/i, '')
      .replace(/\.tsx?$/i, '');
    return stripped || null;
  }
  // Nested: group is the directory path (all segments except the file).
  return parts.slice(0, -1).join('/') || null;
}

/**
 * Group scenarios by feature. Directory-derived label from `specFile` wins,
 * since file layout is the canonical source of grouping. Explicit `feature`
 * is a fallback for scenarios with no specFile (synthetic / test data).
 * Scenarios with neither fall into the "uncategorized" bucket.
 *
 * Group order follows first-appearance in the input — stable for tests.
 */
export function groupByFeature(
  scenarios: ReadonlyArray<ScenarioLike>,
): FeatureGroup[] {
  const groupsBySlug = new Map<string, FeatureGroup>();
  for (const s of scenarios) {
    const derived = deriveFeature(s.specFile);
    const explicit =
      typeof s.feature === 'string' ? s.feature.trim() : '';
    const label = derived || explicit || UNCATEGORIZED_LABEL;
    const slug = label === UNCATEGORIZED_LABEL ? UNCATEGORIZED_SLUG : slugify(label);
    const existing = groupsBySlug.get(slug);
    if (existing) {
      existing.scenarioIds.push(s.id);
    } else {
      groupsBySlug.set(slug, {
        slug,
        label,
        scenarioIds: [s.id],
      });
    }
  }
  return Array.from(groupsBySlug.values());
}

export type ScenariosView = 'gallery' | 'detail' | 'screenshots' | 'flow';

export interface ScenariosHash {
  aspectId: string;
  group: string | null;
  /** Selected scenario slug (from `#/scenarios/<slug>...`). */
  slug: string | null;
  view: ScenariosView;
}

/**
 * Parse a hash like:
 *   `#/scenarios` — gallery
 *   `#/scenarios?group=org` — gallery filtered to a group
 *   `#/scenarios/<slug>` — detail
 *   `#/scenarios/<slug>/screenshots` — screenshots grid
 *   `#/scenarios/<slug>/flow` — flow (compact)
 */
export function parseScenariosHash(hash: string): ScenariosHash {
  const stripped = hash.replace(/^#\/?/, '');
  const [pathPart = '', query = ''] = stripped.split('?');
  const segs = pathPart.split('/').filter(Boolean);
  const aspectId = segs[0] ?? '';
  const slugRaw = segs[1] ?? null;
  const sub = segs[2] ?? null;
  const params = new URLSearchParams(query);
  const rawGroup = params.get('group');
  const group = rawGroup && rawGroup.trim() ? rawGroup.trim() : null;

  let view: ScenariosView = 'gallery';
  if (slugRaw) {
    if (sub === 'screenshots') view = 'screenshots';
    else if (sub === 'flow') view = 'flow';
    else view = 'detail';
  }
  return { aspectId, group, slug: slugRaw, view };
}

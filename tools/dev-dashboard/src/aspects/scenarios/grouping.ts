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
 * Derive a feature label from a `specFile` path. `e2e/scenarios/org-create.scenario.spec.ts`
 * → `org-create`. Returns null when we cannot derive one (so callers can fall back
 * to the uncategorized bucket).
 */
export function deriveFeature(specFile: string | undefined): string | null {
  if (typeof specFile !== 'string') return null;
  const trimmed = specFile.trim();
  if (!trimmed) return null;
  const base = trimmed.split(/[\\/]/).pop() ?? trimmed;
  // Strip common scenario suffixes: `.scenario.spec.ts`, `.spec.ts`, `.ts`.
  const stripped = base
    .replace(/\.scenario\.spec\.ts$/i, '')
    .replace(/\.spec\.ts$/i, '')
    .replace(/\.tsx?$/i, '');
  if (!stripped) return null;
  return stripped;
}

/**
 * Group scenarios by feature. Explicit `feature` (trimmed) wins over `specFile`.
 * Scenarios with neither fall into the "uncategorized" bucket.
 *
 * Group order follows first-appearance in the input — stable for tests.
 */
export function groupByFeature(
  scenarios: ReadonlyArray<ScenarioLike>,
): FeatureGroup[] {
  const groupsBySlug = new Map<string, FeatureGroup>();
  for (const s of scenarios) {
    const explicit =
      typeof s.feature === 'string' ? s.feature.trim() : '';
    const label = explicit || deriveFeature(s.specFile) || UNCATEGORIZED_LABEL;
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

/**
 * Parse a hash like `#/scenarios?group=org` into `{ aspectId: 'scenarios', group: 'org' }`.
 * Returns `group: null` when the query param is absent or empty.
 */
export function parseScenariosHash(hash: string): {
  aspectId: string;
  group: string | null;
} {
  const stripped = hash.replace(/^#\/?/, '');
  const [aspectId = '', query = ''] = stripped.split('?');
  const params = new URLSearchParams(query);
  const raw = params.get('group');
  const group = raw && raw.trim() ? raw.trim() : null;
  return { aspectId, group };
}

import type { AspectStalenessState, StalenessDocument } from '../aspects/types';

export interface StalenessInputs {
  primaryArtifactMtimeMs: number | null;
  primaryArtifactExists: boolean;
  newestSourceMtimeMs: number | null;
  newestSourceFile: string | null;
}

/**
 * Pure classifier used by both the Node script (through a thin adapter) and
 * the frontend unit tests. Rules:
 *
 *  - If primary artifact does not exist: `stale = false`, existence is false.
 *    Missing is its own state, not stale.
 *  - If there are zero source files (`newestSourceMtimeMs === null`):
 *    not stale.
 *  - Otherwise: stale iff `newestSourceMtimeMs > primaryArtifactMtimeMs`.
 */
export function classifyStaleness(inputs: StalenessInputs): AspectStalenessState {
  const {
    primaryArtifactMtimeMs,
    primaryArtifactExists,
    newestSourceMtimeMs,
    newestSourceFile,
  } = inputs;

  const isStale =
    primaryArtifactExists &&
    newestSourceMtimeMs !== null &&
    primaryArtifactMtimeMs !== null &&
    newestSourceMtimeMs > primaryArtifactMtimeMs;

  return {
    primaryArtifactExists,
    primaryArtifactMtime:
      primaryArtifactMtimeMs === null ? null : new Date(primaryArtifactMtimeMs).toISOString(),
    newestSourceMtime:
      newestSourceMtimeMs === null ? null : new Date(newestSourceMtimeMs).toISOString(),
    newestSourceFile,
    stale: isStale,
  };
}

/**
 * Read the dashboard's .staleness.json via the artifact mount.
 * Returns null if the file is missing (caller renders a top-bar warning).
 */
export async function fetchStalenessDocument(
  fetcher: typeof fetch = fetch,
): Promise<StalenessDocument | null> {
  try {
    const resp = await fetcher('/artifacts/staleness.json');
    if (resp.status === 404) return null;
    if (!resp.ok) return null;
    return (await resp.json()) as StalenessDocument;
  } catch {
    return null;
  }
}

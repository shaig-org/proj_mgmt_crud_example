import type { ReactNode } from 'react';

export interface ArtifactRef {
  /** URL the dashboard fetches (relative to dev server root). */
  url: string;
  /** Human label, e.g. "manifest.json". */
  label: string;
  /** Repo-relative path, shown in UI for orientation. */
  repoPath: string;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type AnyAspect = Aspect<any>;

export interface Aspect<TData = unknown> {
  /** Stable kebab-case id; used in URL hash (#/scenarios). */
  id: string;
  /** Tab label. */
  title: string;
  /** Inline SVG component or emoji string for the left-rail icon. */
  icon: ReactNode;
  /** Repo-relative directories whose mtimes determine staleness. */
  sourceRoots: string[];
  /** Artifacts this aspect consumes. First entry is the primary. */
  artifacts: ArtifactRef[];
  /** Copy-pasteable command that regenerates the artifacts. */
  refreshCommand: string;
  /** Repo-relative cwd where refreshCommand must run. */
  refreshCwd: string;
  /** One-line description shown above the command block. */
  refreshDescription: string;
  /** Loader: fetches and parses the artifacts. Throws on missing. */
  load: () => Promise<TData>;
  /** Renderer: receives loaded data. */
  render: (data: TData) => ReactNode;
}

export interface AspectStalenessState {
  primaryArtifactExists: boolean;
  primaryArtifactMtime: string | null;
  newestSourceMtime: string | null;
  newestSourceFile: string | null;
  stale: boolean;
}

export interface StalenessDocument {
  generatedAt: string;
  repoRoot: string;
  aspects: Record<string, AspectStalenessState>;
}

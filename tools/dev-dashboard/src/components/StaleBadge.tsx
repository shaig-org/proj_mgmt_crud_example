import type { AspectStalenessState } from '../aspects/types';

export function StaleBadge({ state }: { state: AspectStalenessState }) {
  if (!state.primaryArtifactExists) {
    return null;
  }
  if (state.stale) {
    const tooltip = state.newestSourceFile
      ? `Newest source file: ${state.newestSourceFile} (${state.newestSourceMtime ?? ''}). Run the refresh command to regenerate.`
      : 'Source files are newer than the artifact.';
    return (
      <span
        className="badge badge--stale"
        data-testid="stale-badge"
        title={tooltip}
        aria-label="stale"
      >
        Stale
      </span>
    );
  }
  return (
    <span
      className="badge badge--fresh"
      data-testid="fresh-badge"
      aria-label="fresh"
    >
      Fresh
    </span>
  );
}

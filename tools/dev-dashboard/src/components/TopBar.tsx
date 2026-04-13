import type { StalenessDocument } from '../aspects/types';

interface TopBarProps {
  repoRoot: string;
  staleness: StalenessDocument | null;
  aspectCount: number;
}

export function TopBar({ repoRoot, staleness, aspectCount }: TopBarProps) {
  const staleCount = staleness
    ? Object.values(staleness.aspects).filter((s) => s.stale).length
    : 0;
  return (
    <header className="topbar">
      <div>
        <span className="topbar__title">Dev Dashboard</span>{' '}
        <span className="topbar__path" data-testid="repo-root">
          {repoRoot}
        </span>
      </div>
      <div className="topbar__right">
        <span data-testid="freshness-summary">
          {aspectCount} aspects · {staleCount} stale
        </span>
        {!staleness && (
          <span className="badge badge--stale" data-testid="staleness-warning">
            staleness data not generated
          </span>
        )}
      </div>
    </header>
  );
}

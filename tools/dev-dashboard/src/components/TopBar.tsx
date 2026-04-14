import { useEffect, useState } from 'react';
import type { StalenessDocument } from '../aspects/types';
import {
  applyTheme,
  readStoredTheme,
  toggleTheme,
  writeStoredTheme,
  type Theme,
} from '../lib/theme';

interface TopBarProps {
  repoRoot: string;
  staleness: StalenessDocument | null;
  aspectCount: number;
}

export function TopBar({ repoRoot, staleness, aspectCount }: TopBarProps) {
  const [theme, setTheme] = useState<Theme>(() => readStoredTheme());

  useEffect(() => {
    applyTheme(theme);
    writeStoredTheme(theme);
  }, [theme]);

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
        <button
          type="button"
          data-testid="theme-toggle"
          aria-label={`switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
          data-theme-value={theme}
          onClick={() => setTheme((t) => toggleTheme(t))}
          className="topbar__theme"
        >
          {theme === 'dark' ? '☀' : '☾'}
        </button>
      </div>
    </header>
  );
}

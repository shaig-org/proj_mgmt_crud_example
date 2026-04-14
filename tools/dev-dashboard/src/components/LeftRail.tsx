import { useEffect, useState } from 'react';
import type { AnyAspect, StalenessDocument } from '../aspects/types';
import {
  readStoredRailCollapsed,
  writeStoredRailCollapsed,
} from '../lib/rail';

interface LeftRailProps {
  aspects: ReadonlyArray<AnyAspect>;
  activeId: string;
  onSelect: (id: string) => void;
  staleness: StalenessDocument | null;
}

export function LeftRail({
  aspects,
  activeId,
  onSelect,
  staleness,
}: LeftRailProps) {
  const [collapsed, setCollapsed] = useState<boolean>(() =>
    readStoredRailCollapsed(),
  );

  useEffect(() => {
    writeStoredRailCollapsed(collapsed);
    if (typeof document !== 'undefined') {
      document.documentElement.setAttribute(
        'data-rail-collapsed',
        collapsed ? '1' : '0',
      );
    }
  }, [collapsed]);

  return (
    <nav
      className={`rail${collapsed ? ' rail--collapsed' : ''}`}
      role="tablist"
      aria-label="Aspects"
      data-collapsed={collapsed ? '1' : '0'}
    >
      <button
        type="button"
        className="rail__hamburger"
        data-testid="rail-hamburger"
        aria-label={collapsed ? 'expand rail' : 'collapse rail'}
        aria-expanded={!collapsed}
        onClick={() => setCollapsed((c) => !c)}
      >
        ☰
      </button>
      {aspects.map((a) => {
        const s = staleness?.aspects[a.id];
        const isStale = s?.stale ?? false;
        return (
          <button
            key={a.id}
            role="tab"
            aria-selected={a.id === activeId}
            onClick={() => onSelect(a.id)}
            className="rail__tab"
            data-testid={`rail-${a.id}`}
            title={collapsed ? a.title : undefined}
          >
            <span aria-hidden className="rail__icon">
              {a.icon}
            </span>
            <span className="rail__label">{a.title}</span>
            {isStale && (
              <span
                className="rail__dot"
                data-testid={`rail-dot-${a.id}`}
              />
            )}
          </button>
        );
      })}
    </nav>
  );
}

import { useEffect, useState } from 'react';
import type { AnyAspect, StalenessDocument } from '../aspects/types';
import {
  readStoredRailCollapsed,
  writeStoredRailCollapsed,
} from '../lib/rail';
import type { FeatureGroup } from '../aspects/scenarios/grouping';
import { parseScenariosHash } from '../aspects/scenarios/grouping';

interface LeftRailProps {
  aspects: ReadonlyArray<AnyAspect>;
  activeId: string;
  onSelect: (id: string) => void;
  staleness: StalenessDocument | null;
  scenarioGroups?: FeatureGroup[];
}

export function LeftRail({
  aspects,
  activeId,
  onSelect,
  staleness,
  scenarioGroups,
}: LeftRailProps) {
  const [collapsed, setCollapsed] = useState<boolean>(() =>
    readStoredRailCollapsed(),
  );
  const [activeGroup, setActiveGroup] = useState<string | null>(() =>
    typeof window === 'undefined'
      ? null
      : parseScenariosHash(window.location.hash).group,
  );
  const [scenariosSubOpen, setScenariosSubOpen] = useState<boolean>(
    () => activeId === 'scenarios',
  );

  useEffect(() => {
    function onHash() {
      setActiveGroup(parseScenariosHash(window.location.hash).group);
    }
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  useEffect(() => {
    if (activeId === 'scenarios') setScenariosSubOpen(true);
    else setScenariosSubOpen(false);
  }, [activeId]);

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
        const isActive = a.id === activeId;
        const showSubItems =
          !collapsed &&
          isActive &&
          a.id === 'scenarios' &&
          scenariosSubOpen &&
          (scenarioGroups?.length ?? 0) > 0;
        return (
          <div key={a.id} className="rail__section">
            <button
              role="tab"
              aria-selected={isActive}
              onClick={() => {
                if (a.id === 'scenarios' && activeId === 'scenarios') {
                  // Re-click on active Scenarios tab → toggle sub-items.
                  setScenariosSubOpen((o) => !o);
                  window.location.hash = '#/scenarios';
                  return;
                }
                onSelect(a.id);
                if (a.id === 'scenarios') {
                  window.location.hash = '#/scenarios';
                }
              }}
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
            {showSubItems && (
              <div className="rail__sub" data-testid="rail-subitems-scenarios">
                {scenarioGroups!.map((g) => (
                  <button
                    key={g.slug}
                    type="button"
                    className="rail__subitem"
                    aria-selected={activeGroup === g.slug}
                    data-testid={`rail-group-${g.slug}`}
                    onClick={() => {
                      onSelect('scenarios');
                      window.location.hash = `#/scenarios?group=${encodeURIComponent(g.slug)}`;
                    }}
                  >
                    {g.label}
                    <span className="rail__sub-count">
                      {g.scenarioIds.length}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </nav>
  );
}

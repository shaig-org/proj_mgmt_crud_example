import type { AnyAspect, StalenessDocument } from '../aspects/types';

interface LeftRailProps {
  aspects: ReadonlyArray<AnyAspect>;
  activeId: string;
  onSelect: (id: string) => void;
  staleness: StalenessDocument | null;
}

export function LeftRail({ aspects, activeId, onSelect, staleness }: LeftRailProps) {
  return (
    <nav className="rail" role="tablist" aria-label="Aspects">
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
          >
            <span aria-hidden>{a.icon}</span>
            <span>{a.title}</span>
            {isStale && <span className="rail__dot" data-testid={`rail-dot-${a.id}`} />}
          </button>
        );
      })}
    </nav>
  );
}

import { useEffect, useState } from 'react';
import { aspects } from './aspects';
import { resolveAspectFromHash, getAspect } from './lib/registry';
import { fetchStalenessDocument } from './lib/staleness';
import type { StalenessDocument } from './aspects/types';
import { TopBar } from './components/TopBar';
import { LeftRail } from './components/LeftRail';
import { AspectShell } from './components/AspectShell';

function initialId(): string {
  if (typeof window === 'undefined') return aspects[0].id;
  return resolveAspectFromHash(aspects, window.location.hash).id;
}

export function App() {
  const [activeId, setActiveId] = useState<string>(initialId());
  const [staleness, setStaleness] = useState<StalenessDocument | null>(null);

  // Sync activeId → URL hash.
  useEffect(() => {
    const targetHash = `#/${activeId}`;
    if (window.location.hash !== targetHash) {
      window.location.hash = targetHash;
    }
  }, [activeId]);

  // Sync URL hash → activeId on back/forward navigation.
  useEffect(() => {
    function onHash() {
      const resolved = resolveAspectFromHash(aspects, window.location.hash);
      setActiveId(resolved.id);
    }
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  useEffect(() => {
    void fetchStalenessDocument().then(setStaleness);
  }, []);

  const active = getAspect(aspects, activeId) ?? aspects[0];

  const repoRoot =
    (import.meta.env as { VITE_REPO_ROOT?: string }).VITE_REPO_ROOT ??
    staleness?.repoRoot ??
    '';

  const activeStaleness = staleness?.aspects[active.id] ?? null;

  return (
    <div className="app">
      <TopBar
        repoRoot={repoRoot}
        staleness={staleness}
        aspectCount={aspects.length}
      />
      <LeftRail
        aspects={aspects}
        activeId={active.id}
        onSelect={setActiveId}
        staleness={staleness}
      />
      <main className="main">
        <AspectShell key={active.id} aspect={active} staleness={activeStaleness} />
      </main>
    </div>
  );
}

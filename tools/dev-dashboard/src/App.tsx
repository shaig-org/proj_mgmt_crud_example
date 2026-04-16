import { useEffect, useState } from 'react';
import { aspects } from './aspects';
import { resolveAspectFromHash, getAspect } from './lib/registry';
import { fetchStalenessDocument } from './lib/staleness';
import type { StalenessDocument } from './aspects/types';
import { TopBar } from './components/TopBar';
import { LeftRail } from './components/LeftRail';
import { AspectShell } from './components/AspectShell';
import { validate as validateScenarios } from './aspects/scenarios/ScenariosAspect';
import { groupByFeature, type FeatureGroup } from './aspects/scenarios/grouping';

function initialId(): string {
  if (typeof window === 'undefined') return aspects[0].id;
  return resolveAspectFromHash(aspects, window.location.hash).id;
}

export function App() {
  const [activeId, setActiveId] = useState<string>(initialId());
  const [staleness, setStaleness] = useState<StalenessDocument | null>(null);
  const [scenarioGroups, setScenarioGroups] = useState<FeatureGroup[]>([]);
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void fetch('/artifacts/scenarios/gallery/manifest.json')
      .then(async (r) => (r.ok ? (r.json() as Promise<unknown>) : null))
      .then((doc) => {
        if (cancelled || !doc) return;
        try {
          const manifest = validateScenarios(doc);
          setScenarioGroups(groupByFeature(manifest.scenarios));
          setGeneratedAt(manifest.generatedAt ?? null);
        } catch {
          /* manifest missing/malformed — rail just shows no sub-items. */
        }
      })
      .catch(() => {
        /* ignore */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Sync activeId → URL hash — but preserve existing sub-path / query for the
  // active aspect (e.g. `#/scenarios?group=org` or `#/scenarios/<slug>`).
  useEffect(() => {
    const current = window.location.hash;
    const firstSegment = current.replace(/^#\/?/, '').split('?')[0]!.split('/')[0]!;
    const knownAspect = aspects.some((a) => a.id === firstSegment);
    if (!knownAspect || firstSegment !== activeId) {
      window.location.hash = `#/${activeId}`;
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
        generatedAt={generatedAt}
      />
      <LeftRail
        aspects={aspects}
        activeId={active.id}
        onSelect={setActiveId}
        staleness={staleness}
        scenarioGroups={scenarioGroups}
      />
      <main className="main">
        <AspectShell key={active.id} aspect={active} staleness={activeStaleness} />
      </main>
    </div>
  );
}

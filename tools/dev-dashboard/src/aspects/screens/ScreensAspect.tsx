import React, { useEffect, useState } from 'react';
import type { Aspect } from '../types';
import { loadArtifact } from '../../lib/loadArtifact';
import type { ScenariosManifest } from '../scenarios/types';
import { validate } from '../scenarios/ScenariosAspect';
import { buildScreenIndex, uncoveredScreens } from './screenIndex';
import { KNOWN_ROUTES } from './normalizeUrl';
import { ScreensIndexView } from './ScreensIndexView';
import { ScreenDetailView } from './ScreenDetailView';

const ARTIFACT_URL = '/artifacts/scenarios/manifest.json';

function parseScreensHash(hash: string): { route: string | null } {
  // #/screens/<encoded-route> → detail view
  const match = /^#\/?screens\/(.+)$/.exec(hash);
  if (match) {
    try {
      return { route: decodeURIComponent(match[1]!) };
    } catch {
      return { route: null };
    }
  }
  return { route: null };
}

function useScreensHash(): { route: string | null } {
  const [state, setState] = useState(() =>
    typeof window === 'undefined'
      ? { route: null }
      : parseScreensHash(window.location.hash),
  );
  useEffect(() => {
    function onHash() {
      setState(parseScreensHash(window.location.hash));
    }
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);
  return state;
}

function ScreensBody({ data }: { data: ScenariosManifest }): React.ReactElement {
  const { route } = useScreensHash();
  const index = buildScreenIndex(data.scenarios);
  const uncovered = uncoveredScreens(index, KNOWN_ROUTES);

  if (route !== null) {
    const visits = index.get(route) ?? [];
    return <ScreenDetailView route={route} visits={visits} />;
  }

  return <ScreensIndexView screenIndex={index} uncovered={uncovered} />;
}

export const screensAspect: Aspect<ScenariosManifest> = {
  id: 'screens',
  title: 'Screens',
  icon: '⬜',
  sourceRoots: ['frontend/e2e/scenarios'],
  artifacts: [
    {
      url: ARTIFACT_URL,
      label: 'manifest.json',
      repoPath: 'frontend/walkthroughs/gallery/manifest.json',
    },
  ],
  refreshCommand: 'npm --prefix frontend run walkthroughs:generate',
  refreshCwd: '<repo-root>',
  refreshDescription:
    're-runs scenario tests headed and captures GIFs, screenshots, and step transcripts.',
  suppressRefresh: (hash: string) => {
    // Hide refresh trigger on screen detail drill-downs (#/screens/<route>)
    return /^#\/?screens\/[^?]+/.test(hash);
  },
  load: async () => {
    const { data } = await loadArtifact<unknown>(ARTIFACT_URL);
    return validate(data);
  },
  render: (data) => <ScreensBody data={data} />,
};

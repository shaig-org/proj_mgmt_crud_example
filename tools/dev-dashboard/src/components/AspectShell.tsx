import { useEffect, useState } from 'react';
import type { AnyAspect, AspectStalenessState } from '../aspects/types';
import { RefreshModal } from './RefreshModal';
import { StaleBadge } from './StaleBadge';
import { EmptyState } from './EmptyState';
import {
  ArtifactMalformedError,
  ArtifactMissingError,
  ArtifactSchemaError,
} from '../lib/loadArtifact';

interface AspectShellProps {
  aspect: AnyAspect;
  staleness: AspectStalenessState | null;
}

type LoadState =
  | { kind: 'loading' }
  | { kind: 'ok'; data: unknown }
  | { kind: 'missing' }
  | { kind: 'error'; message: string };

function useHash(): string {
  const [hash, setHash] = useState<string>(
    typeof window === 'undefined' ? '' : window.location.hash,
  );
  useEffect(() => {
    function onHash() {
      setHash(window.location.hash);
    }
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);
  return hash;
}

export function AspectShell({ aspect, staleness }: AspectShellProps) {
  const [state, setState] = useState<LoadState>({ kind: 'loading' });
  const hash = useHash();

  useEffect(() => {
    let cancelled = false;
    setState({ kind: 'loading' });
    aspect
      .load()
      .then((data) => {
        if (cancelled) return;
        setState({ kind: 'ok', data });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof ArtifactMissingError) {
          setState({ kind: 'missing' });
          return;
        }
        const message =
          err instanceof ArtifactMalformedError
            ? `${err.message}`
            : err instanceof ArtifactSchemaError
              ? `${err.message}`
              : err instanceof Error
                ? err.message
                : String(err);
        setState({ kind: 'error', message });
      });
    return () => {
      cancelled = true;
    };
  }, [aspect]);

  const primaryArtifactExists =
    staleness === null ? true : staleness.primaryArtifactExists;
  const showEmpty =
    state.kind === 'missing' || (state.kind !== 'ok' && !primaryArtifactExists);

  const suppressRefresh = aspect.suppressRefresh?.(hash) ?? false;
  // Also force-hide refresh on the empty state — the empty state itself
  // already surfaces the command prominently.
  const showRefresh = !suppressRefresh && !showEmpty;

  return (
    <section aria-labelledby={`aspect-title-${aspect.id}`} data-testid={`aspect-${aspect.id}`}>
      <header className="shell__header">
        <div className="shell__title-row">
          <h2 id={`aspect-title-${aspect.id}`} className="shell__title">
            {aspect.title}
          </h2>
          {staleness && <StaleBadge state={staleness} />}
          {staleness?.primaryArtifactMtime && (
            <span className="shell__last-gen" data-testid="last-generated">
              last generated: {staleness.primaryArtifactMtime}
            </span>
          )}
          {showRefresh && (
            <RefreshModal
              command={aspect.refreshCommand}
              cwd={aspect.refreshCwd}
              description={aspect.refreshDescription}
              output={aspect.artifacts[0].repoPath}
            />
          )}
        </div>
      </header>
      <div className="shell__body">
        {showEmpty ? (
          <EmptyState aspect={aspect} />
        ) : state.kind === 'loading' ? (
          <div className="empty" data-testid="loading">Loading…</div>
        ) : state.kind === 'error' ? (
          <div className="empty" data-testid="aspect-error">
            <p>Could not load {aspect.title}:</p>
            <pre>{state.message}</pre>
          </div>
        ) : (
          aspect.render(state.data)
        )}
      </div>
    </section>
  );
}

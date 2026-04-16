import { useEffect, useState } from 'react';
import type { Aspect } from '../types';
import { ArtifactMissingError, loadArtifact } from '../../lib/loadArtifact';
import type {
  E2eRequestTrace,
  E2eScenarioTraces,
  E2eTracesData,
} from './types';
import { RequestFlameChart } from '../../components/RequestFlameChart';

const BASE = '/artifacts/e2e-traces';

interface DirListing {
  entries: Array<{ name: string; type: 'dir' | 'file' }>;
}

async function listDir(url: string): Promise<DirListing | null> {
  try {
    const resp = await fetch(url);
    if (!resp.ok) return null;
    return (await resp.json()) as DirListing;
  } catch {
    return null;
  }
}

async function loadE2eTraces(): Promise<E2eTracesData> {
  const listing = await listDir(`${BASE}/`);
  if (!listing) throw new ArtifactMissingError(`${BASE}/`);
  const dirEntries = listing.entries.filter((e) => e.type === 'dir');
  if (dirEntries.length === 0) throw new ArtifactMissingError(`${BASE}/`);

  const scenarios: E2eScenarioTraces[] = [];

  for (const dir of dirEntries) {
    const correlationId = dir.name;
    const subListing = await listDir(`${BASE}/${correlationId}/`);
    if (!subListing) continue;

    const reqFiles = subListing.entries
      .filter((e) => e.type === 'file' && e.name.startsWith('req-') && e.name.endsWith('.json'))
      .map((e) => e.name);

    const requests: E2eRequestTrace[] = [];
    for (const filename of reqFiles) {
      try {
        const { data } = await loadArtifact<E2eRequestTrace>(
          `${BASE}/${correlationId}/${filename}`,
        );
        requests.push(data);
      } catch (e) {
        if (!(e instanceof ArtifactMissingError)) throw e;
      }
    }

    requests.sort((a, b) => a.seq - b.seq);
    scenarios.push({ correlationId, requests });
  }

  scenarios.sort((a, b) => a.correlationId.localeCompare(b.correlationId));
  return { scenarios };
}


function statusClass(code: number): string {
  if (code >= 500) return 'flame-status-5xx';
  if (code >= 400) return 'flame-status-4xx';
  if (code >= 300) return 'flame-status-3xx';
  return 'flame-status-2xx';
}

function E2eTracesBody({ data }: { data: E2eTracesData }) {
  const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(
    data.scenarios[0]?.correlationId ?? null,
  );
  const [selectedSeq, setSelectedSeq] = useState<number | null>(null);

  // Honor ?select=<correlationId> in window.location.hash for cross-linking.
  useEffect(() => {
    const match = /select=([^&]+)/.exec(window.location.hash);
    if (match) {
      const target = decodeURIComponent(match[1]);
      const found = data.scenarios.find((s) => s.correlationId === target);
      if (found) setSelectedScenarioId(found.correlationId);
    }
  }, [data]);

  const selectedScenario =
    data.scenarios.find((s) => s.correlationId === selectedScenarioId) ?? null;

  const selectedRequest =
    selectedScenario?.requests.find((r) => r.seq === selectedSeq) ??
    selectedScenario?.requests[0] ??
    null;

  function selectScenario(id: string) {
    setSelectedScenarioId(id);
    setSelectedSeq(null);
  }

  return (
    <div className="trace-layout">
      <div data-testid="e2e-traces-list" className="trace-list">
        {data.scenarios.length === 0 ? (
          <div className="empty">No E2E trace scenarios found.</div>
        ) : (
          data.scenarios.map((s) => (
            <button
              key={s.correlationId}
              type="button"
              aria-selected={s.correlationId === selectedScenarioId}
              data-testid={`e2e-scenario-${s.correlationId}`}
              title={s.correlationId}
              onClick={() => selectScenario(s.correlationId)}
            >
              {s.correlationId}
            </button>
          ))
        )}
      </div>
      <div>
        {selectedScenario ? (
          <div>
            <h3>{selectedScenario.correlationId}</h3>
            {selectedScenario.requests.length === 0 ? (
              <div className="empty">No requests recorded.</div>
            ) : (
              <>
                <div
                  className="flame-req-tabs"
                  data-testid="e2e-requests-list"
                >
                  {selectedScenario.requests.map((req) => (
                    <button
                      key={req.seq}
                      type="button"
                      className="flame-req-tab"
                      aria-selected={req.seq === (selectedSeq ?? selectedScenario.requests[0]?.seq)}
                      data-testid={`e2e-request-${req.seq}`}
                      onClick={() => setSelectedSeq(req.seq)}
                    >
                      <span className={statusClass(req.status_code)}>{req.status_code}</span>{' '}
                      {req.seq}: {req.method} {req.path}
                    </button>
                  ))}
                </div>
                {selectedRequest && (
                  <RequestFlameChart request={selectedRequest} />
                )}
              </>
            )}
          </div>
        ) : (
          <div className="empty">Select a scenario to view its traces.</div>
        )}
      </div>
    </div>
  );
}

export const e2eTracesAspect: Aspect<E2eTracesData> = {
  id: 'e2e-traces',
  title: 'E2E Traces',
  icon: '\u21c4',
  sourceRoots: ['frontend/e2e/scenarios'],
  artifacts: [
    {
      url: `${BASE}/`,
      label: 'e2e-traces/',
      repoPath: 'backend/e2e-traces/',
    },
  ],
  refreshCommand: 'npm --prefix frontend run e2e:scenarios',
  refreshCwd: '<repo-root>',
  refreshDescription:
    're-runs E2E scenario tests; backend middleware writes per-request call traces under backend/e2e-traces/.',
  load: loadE2eTraces,
  render: (data) => <E2eTracesBody data={data} />,
};

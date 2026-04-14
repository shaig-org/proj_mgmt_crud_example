import { useEffect, useState } from 'react';
import type { Aspect } from '../types';
import { ArtifactMissingError, loadArtifact } from '../../lib/loadArtifact';
import type {
  CallEvent,
  E2eRequestTrace,
  E2eScenarioTraces,
  E2eTracesData,
} from './types';

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

function CallEventRow({ event }: { event: CallEvent }) {
  return (
    <div style={{ paddingLeft: `${event.depth * 16}px`, fontFamily: 'monospace', fontSize: '12px', padding: `2px 0 2px ${event.depth * 16}px` }}>
      {event.event}: {event.file}:{event.function} (line {event.line})
    </div>
  );
}

function RequestDetail({ request }: { request: E2eRequestTrace }) {
  const [showReturns, setShowReturns] = useState(false);

  const visibleEvents = showReturns
    ? request.call_events
    : request.call_events.filter((e) => e.event === 'call');

  return (
    <div>
      <h4>
        {request.method} {request.path} &rarr; {request.status_code} ({request.duration_ms}ms)
      </h4>
      <div style={{ marginBottom: '8px' }}>
        <label style={{ fontSize: '13px', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={showReturns}
            onChange={(e) => setShowReturns(e.currentTarget.checked)}
            style={{ marginRight: '4px' }}
          />
          Show return events
        </label>
      </div>
      <div data-testid="e2e-call-events">
        {visibleEvents.length === 0 ? (
          <div style={{ color: '#888', fontSize: '13px' }}>No call events.</div>
        ) : (
          visibleEvents.map((evt, i) => (
            <CallEventRow key={i} event={evt} />
          ))
        )}
      </div>
    </div>
  );
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
    selectedScenario?.requests.find((r) => r.seq === selectedSeq) ?? null;

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
            <div data-testid="e2e-requests-list">
              {selectedScenario.requests.length === 0 ? (
                <div className="empty">No requests recorded.</div>
              ) : (
                selectedScenario.requests.map((req) => (
                  <button
                    key={req.seq}
                    type="button"
                    aria-selected={req.seq === selectedSeq}
                    data-testid={`e2e-request-${req.seq}`}
                    onClick={() => setSelectedSeq(req.seq === selectedSeq ? null : req.seq)}
                    style={{ display: 'block', width: '100%', textAlign: 'left', marginBottom: '4px' }}
                  >
                    {req.method} {req.path} &rarr; {req.status_code} ({req.duration_ms}ms)
                  </button>
                ))
              )}
            </div>
            {selectedRequest && (
              <RequestDetail request={selectedRequest} />
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

import { useEffect, useState } from 'react';
import type { E2eRequestTrace, E2eScenarioTraces } from '../e2e-traces/types';
import { RequestFlameChart } from '../../components/RequestFlameChart';

interface DirEntry {
  name: string;
  type: string;
}

interface DirListing {
  entries: DirEntry[];
}

type PanelState = 'loading' | 'empty' | E2eScenarioTraces;

function statusClass(code: number): string {
  if (code >= 500) return 'flame-status-5xx';
  if (code >= 400) return 'flame-status-4xx';
  if (code >= 300) return 'flame-status-3xx';
  return 'flame-status-2xx';
}

interface ScenarioTracePanelProps {
  correlationId: string;
}

export function ScenarioTracePanel({ correlationId }: ScenarioTracePanelProps) {
  const [state, setState] = useState<PanelState>('loading');
  const [selectedSeq, setSelectedSeq] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const listing = await fetch(`/artifacts/e2e-traces/${correlationId}/`);
        if (!listing.ok) {
          if (!cancelled) setState('empty');
          return;
        }
        const dir = (await listing.json()) as DirListing;
        const reqFiles = dir.entries
          .filter(
            (e) => e.type === 'file' && /^req-\d+\.json$/.test(e.name),
          )
          .map((e) => e.name)
          .sort();
        if (reqFiles.length === 0) {
          if (!cancelled) setState('empty');
          return;
        }
        const requests: E2eRequestTrace[] = [];
        for (const name of reqFiles) {
          const r = await fetch(
            `/artifacts/e2e-traces/${correlationId}/${name}`,
          );
          if (r.ok) requests.push((await r.json()) as E2eRequestTrace);
        }
        if (!cancelled) {
          const sorted = requests.sort((a, b) => a.seq - b.seq);
          setState({ correlationId, requests: sorted });
          setSelectedSeq(sorted[0]?.seq ?? null);
        }
      } catch {
        if (!cancelled) setState('empty');
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [correlationId]);

  if (state === 'loading') {
    return <div className="flame-loading">Loading backend traces…</div>;
  }
  if (state === 'empty') {
    return null;
  }

  const traceData = state as E2eScenarioTraces;
  const selectedRequest =
    traceData.requests.find((r) => r.seq === selectedSeq) ?? null;

  return (
    <div>
      <div className="flame-req-tabs">
        {traceData.requests.map((req) => (
          <button
            key={req.seq}
            type="button"
            className="flame-req-tab"
            aria-selected={req.seq === selectedSeq}
            onClick={() => setSelectedSeq(req.seq)}
          >
            <span className={statusClass(req.status_code)}>{req.status_code}</span>{' '}
            {req.seq}: {req.method} {req.path}
          </button>
        ))}
      </div>
      {selectedRequest && <RequestFlameChart request={selectedRequest} />}
    </div>
  );
}

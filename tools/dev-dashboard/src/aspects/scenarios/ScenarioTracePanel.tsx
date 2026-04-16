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
  const [openSeqs, setOpenSeqs] = useState<Set<number>>(new Set());

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
          // First request starts expanded
          if (sorted.length > 0) {
            setOpenSeqs(new Set([sorted[0]!.seq]));
          }
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
  const firstTimestamp = traceData.requests[0]?.timestamp_ms ?? 0;

  function toggleSeq(seq: number) {
    setOpenSeqs((prev) => {
      const next = new Set(prev);
      if (next.has(seq)) {
        next.delete(seq);
      } else {
        next.add(seq);
      }
      return next;
    });
  }

  return (
    <div>
      {traceData.requests.map((req) => {
        const isOpen = openSeqs.has(req.seq);
        const delta = req.timestamp_ms - firstTimestamp;
        return (
          <div className="trace-request" key={req.seq}>
            <button
              className="trace-request-header"
              aria-expanded={isOpen}
              onClick={() => toggleSeq(req.seq)}
              data-testid={`trace-req-header-${req.seq}`}
              type="button"
            >
              <span className="trace-req-timestamp">t+{delta}ms</span>
              <span className={`trace-req-method trace-req-method--${req.method.toLowerCase()}`}>{req.method}</span>
              <span className="trace-req-path">{req.path}</span>
              <span className={`trace-req-status ${statusClass(req.status_code)}`}>{req.status_code}</span>
              <span className="trace-req-duration">{req.duration_ms}ms</span>
              <span className="trace-req-chevron">{isOpen ? '▾' : '▸'}</span>
            </button>
            {isOpen && <RequestFlameChart request={req} />}
          </div>
        );
      })}
    </div>
  );
}

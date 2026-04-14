export interface CallEvent {
  event: 'call' | 'return';
  file: string;
  function: string;
  line: number;
  depth: number;
  timestamp_ns: number;
}

export interface E2eRequestTrace {
  seq: number;
  method: string;
  path: string;
  status_code: number;
  duration_ms: number;
  timestamp_ms: number;
  call_events: CallEvent[];
}

export interface E2eScenarioTraces {
  correlationId: string;
  requests: E2eRequestTrace[];
}

export interface E2eTracesData {
  scenarios: E2eScenarioTraces[];
}

/**
 * Parse and validate a single req-NNN.json file produced by the backend
 * E2eTracingMiddleware. Throws with a descriptive message if a required
 * field is missing or has the wrong type — used by scenarios.realschema.test.ts
 * to lock in the producer contract.
 */
export function parseRequestTrace(raw: unknown): E2eRequestTrace {
  if (typeof raw !== 'object' || raw === null) {
    throw new Error('E2eRequestTrace: expected object');
  }
  const r = raw as Record<string, unknown>;
  if (typeof r['seq'] !== 'number') throw new Error('E2eRequestTrace: missing or invalid seq');
  if (typeof r['method'] !== 'string') throw new Error('E2eRequestTrace: missing or invalid method');
  if (typeof r['path'] !== 'string') throw new Error('E2eRequestTrace: missing or invalid path');
  if (typeof r['status_code'] !== 'number') throw new Error('E2eRequestTrace: missing or invalid status_code');
  if (typeof r['duration_ms'] !== 'number') throw new Error('E2eRequestTrace: missing or invalid duration_ms');
  if (typeof r['timestamp_ms'] !== 'number') throw new Error('E2eRequestTrace: missing or invalid timestamp_ms');
  if (!Array.isArray(r['call_events'])) throw new Error('E2eRequestTrace: missing or invalid call_events');
  return r as unknown as E2eRequestTrace;
}

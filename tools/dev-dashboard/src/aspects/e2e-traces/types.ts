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

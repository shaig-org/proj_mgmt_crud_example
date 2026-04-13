export interface TraceSummary {
  scenarioId: string;
  title?: string;
  // TODO(v2): consume `coveredFiles: string[]` when pytest-tracer emits it.
  // Until then the "tests covering file X" search box is disabled.
  coveredFiles?: string[];
}

export interface TraceEntry {
  id: string;
  hasMermaid: boolean;
  hasFlame: boolean;
  hasFolded: boolean;
  summary: TraceSummary | null;
}

export interface TracesData {
  entries: TraceEntry[];
}

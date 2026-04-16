export interface CapabilityRoute {
  method: string;
  path: string;
  handler: string;
  capabilities: string[];
}

export interface CapabilityDocument {
  routes: CapabilityRoute[];
}

export type CapabilityStatus =
  | 'unchanged'
  | 'expanded'
  | 'reduced'
  | 'new'
  | 'removed';

export interface CapabilityRow {
  method: string;
  path: string;
  handler: string;
  baseline: string[] | null;
  current: string[] | null;
  status: CapabilityStatus;
  added: string[];
  removed: string[];
}

export interface CapabilitiesData {
  rows: CapabilityRow[];
  hasReport: boolean;
  gitDiff: GitDiffData | null;
}

// ---------------------------------------------------------------------------
// Git diff artifact (git-diff.json)
// ---------------------------------------------------------------------------

export interface GitDiffRoute {
  method: string;
  path: string;
  handler: string;
  from_capabilities: string[] | null;
  to_capabilities: string[] | null;
  status: CapabilityStatus;
  added: string[];
  removed: string[];
}

export interface GitDiffSummary {
  total: number;
  unchanged: number;
  expanded: number;
  reduced: number;
  new: number;
  removed: number;
}

export interface GitDiffDocument {
  from_ref: string;
  to_ref: string;
  from_commit: string;
  to_commit: string;
  generated_at: string;
  routes: GitDiffRoute[];
  summary: GitDiffSummary;
}

export interface GitDiffData {
  rows: CapabilityRow[];
  fromRef: string;
  toRef: string;
  fromCommit: string;
  toCommit: string;
  generatedAt: string;
  summary: GitDiffSummary;
}

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
}

export interface ScenarioStep {
  index: number;
  label: string;
  screenshot?: string;
}

export interface ScenarioEntry {
  id: string;
  title: string;
  tags?: string[];
  status?: 'passing' | 'failing';
  correlationId?: string;
  gif?: string;
  video?: string;
  thumbnail?: string;
  steps?: ScenarioStep[];
}

export interface ScenariosManifest {
  scenarios: ScenarioEntry[];
}

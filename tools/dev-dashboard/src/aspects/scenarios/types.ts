export interface ScenarioStep {
  index: number;
  label: string;
  screenshot?: string;
  durationMs?: number;
  status?: 'passing' | 'failing';
}

export interface ScenarioEntry {
  id: string;
  title: string;
  tags?: string[];
  status?: 'passing' | 'failing';
  correlationId?: string;
  gif?: string;
  motionGif?: string;
  video?: string;
  thumbnail?: string;
  durationMs?: number;
  startedAt?: string;
  steps?: ScenarioStep[];
  specFile?: string;
  feature?: string;
}

export interface ScenariosManifest {
  scenarios: ScenarioEntry[];
  generatedAt?: string;
}

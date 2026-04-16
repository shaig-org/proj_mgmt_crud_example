import type { ScenarioEntry } from '../scenarios/types';
import { normalizeUrl } from './normalizeUrl';

export interface ScreenVisit {
  scenarioId: string;
  scenarioTitle: string;
  stepIndex: number;
  stepLabel: string;
  screenshot?: string;
  url: string;
}

export type ScreenIndex = Map<string, ScreenVisit[]>;

/**
 * Invert scenarios→steps into screen→visits.
 *
 * For each step with a non-empty url, normalize the url to a route pattern
 * and push a ScreenVisit into the index under that pattern.
 *
 * Deduplication: same scenarioId + stepIndex combination is only added once.
 */
export function buildScreenIndex(scenarios: ScenarioEntry[]): ScreenIndex {
  const index: ScreenIndex = new Map();
  const seen = new Set<string>();

  for (const scenario of scenarios) {
    if (!scenario.steps) continue;
    for (const step of scenario.steps) {
      if (!step.url) continue;

      const pattern = normalizeUrl(step.url);
      if (pattern === null) continue;

      // Deduplication guard: same scenario+step should only appear once
      const key = `${scenario.id}::${step.index}::${pattern}`;
      if (seen.has(key)) continue;
      seen.add(key);

      const visit: ScreenVisit = {
        scenarioId: scenario.id,
        scenarioTitle: scenario.title,
        stepIndex: step.index,
        stepLabel: step.label,
        screenshot: step.screenshot,
        url: step.url,
      };

      const existing = index.get(pattern);
      if (existing) {
        existing.push(visit);
      } else {
        index.set(pattern, [visit]);
      }
    }
  }

  return index;
}

/**
 * Returns known routes that have zero visits in the screen index.
 * Result is sorted alphabetically.
 */
export function uncoveredScreens(index: ScreenIndex, knownRoutes: string[]): string[] {
  return knownRoutes
    .filter((route) => !index.has(route))
    .sort();
}

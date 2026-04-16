import { describe, it, expect } from 'vitest';
import type { ScenarioEntry } from '../../src/aspects/scenarios/types';
import { buildScreenIndex, uncoveredScreens } from '../../src/aspects/screens/screenIndex';
import { KNOWN_ROUTES } from '../../src/aspects/screens/normalizeUrl';

function makeScenario(
  id: string,
  title: string,
  steps: Array<{
    index: number;
    label: string;
    url?: string;
    screenshot?: string;
  }>,
): ScenarioEntry {
  return {
    id,
    title,
    steps: steps.map((s) => ({
      index: s.index,
      label: s.label,
      url: s.url,
      screenshot: s.screenshot,
    })),
  };
}

describe('buildScreenIndex', () => {
  it('buildScreenIndex_returns_empty_map_for_empty_scenarios_array', () => {
    const index = buildScreenIndex([]);
    expect(index.size).toBe(0);
  });

  it('buildScreenIndex_returns_empty_map_when_all_steps_have_no_url', () => {
    const scenarios = [
      makeScenario('s1', 'Scenario 1', [
        { index: 1, label: 'Step 1' },
        { index: 2, label: 'Step 2' },
      ]),
    ];
    const index = buildScreenIndex(scenarios);
    expect(index.size).toBe(0);
  });

  it('buildScreenIndex_indexes_single_scenario_single_step', () => {
    const scenarios = [
      makeScenario('s1', 'Scenario 1', [
        { index: 1, label: 'Login', url: 'http://localhost:5173/login' },
      ]),
    ];
    const index = buildScreenIndex(scenarios);
    expect(index.size).toBe(1);
    expect(index.has('/login')).toBe(true);
    expect(index.get('/login')).toHaveLength(1);
  });

  it('buildScreenIndex_visit_contains_scenarioId_title_stepIndex_stepLabel_screenshot_url', () => {
    const scenarios = [
      makeScenario('s1', 'Scenario One', [
        {
          index: 1,
          label: 'Open projects',
          url: 'http://localhost:5173/projects',
          screenshot: 'screenshots/s1/01-open-projects.png',
        },
      ]),
    ];
    const index = buildScreenIndex(scenarios);
    const visit = index.get('/projects')![0]!;
    expect(visit.scenarioId).toBe('s1');
    expect(visit.scenarioTitle).toBe('Scenario One');
    expect(visit.stepIndex).toBe(1);
    expect(visit.stepLabel).toBe('Open projects');
    expect(visit.screenshot).toBe('screenshots/s1/01-open-projects.png');
    expect(visit.url).toBe('http://localhost:5173/projects');
  });

  it('buildScreenIndex_two_steps_same_scenario_same_route_both_appear_when_step_index_differs', () => {
    // Two steps with distinct stepIndex hitting the same pattern should both appear
    // (deduplication is same scenario+step triple, not same scenario)
    const scenarios = [
      makeScenario('s1', 'Scenario 1', [
        { index: 1, label: 'Visit orgs first', url: 'http://localhost:5173/organizations' },
        { index: 2, label: 'Visit orgs again', url: 'http://localhost:5173/organizations' },
      ]),
    ];
    const index = buildScreenIndex(scenarios);
    const visits = index.get('/organizations')!;
    // Both steps have different stepIndex so both appear
    expect(visits).toHaveLength(2);
    expect(visits[0]!.stepIndex).toBe(1);
    expect(visits[1]!.stepIndex).toBe(2);
  });

  it('buildScreenIndex_two_scenarios_same_route_both_appear', () => {
    const scenarios = [
      makeScenario('s1', 'Scenario 1', [
        { index: 1, label: 'Login', url: 'http://localhost:5173/login' },
      ]),
      makeScenario('s2', 'Scenario 2', [
        { index: 1, label: 'Login step', url: 'http://localhost:5173/login' },
      ]),
    ];
    const index = buildScreenIndex(scenarios);
    const visits = index.get('/login')!;
    expect(visits).toHaveLength(2);
    expect(visits[0]!.scenarioId).toBe('s1');
    expect(visits[1]!.scenarioId).toBe('s2');
  });

  it('buildScreenIndex_two_scenarios_different_routes_each_indexed_separately', () => {
    const scenarios = [
      makeScenario('s1', 'Scenario 1', [
        { index: 1, label: 'Projects', url: 'http://localhost:5173/projects' },
      ]),
      makeScenario('s2', 'Scenario 2', [
        { index: 1, label: 'Users', url: 'http://localhost:5173/users' },
      ]),
    ];
    const index = buildScreenIndex(scenarios);
    expect(index.size).toBe(2);
    expect(index.has('/projects')).toBe(true);
    expect(index.has('/users')).toBe(true);
    expect(index.get('/projects')![0]!.scenarioId).toBe('s1');
    expect(index.get('/users')![0]!.scenarioId).toBe('s2');
  });

  it('buildScreenIndex_step_with_empty_string_url_is_skipped', () => {
    const scenarios = [
      makeScenario('s1', 'Scenario 1', [
        { index: 1, label: 'No URL', url: '' },
        { index: 2, label: 'With URL', url: 'http://localhost:5173/projects' },
      ]),
    ];
    const index = buildScreenIndex(scenarios);
    expect(index.size).toBe(1);
    expect(index.has('/projects')).toBe(true);
  });

  it('buildScreenIndex_normalizes_uuid_urls_to_patterns', () => {
    const scenarios = [
      makeScenario('s1', 'Scenario 1', [
        {
          index: 1,
          label: 'View project',
          url: 'http://localhost:5173/projects/a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        },
      ]),
    ];
    const index = buildScreenIndex(scenarios);
    expect(index.has('/projects/:projectId')).toBe(true);
    expect(index.get('/projects/:projectId')![0]!.url).toBe(
      'http://localhost:5173/projects/a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    );
  });

  it('buildScreenIndex_step_screenshot_optional_when_absent', () => {
    const scenarios = [
      makeScenario('s1', 'Scenario 1', [
        { index: 1, label: 'Login', url: 'http://localhost:5173/login' },
      ]),
    ];
    const index = buildScreenIndex(scenarios);
    const visit = index.get('/login')![0]!;
    expect(visit.screenshot).toBeUndefined();
  });
});

describe('uncoveredScreens', () => {
  it('uncoveredScreens_returns_all_known_routes_when_index_is_empty', () => {
    const index = new Map<string, never[]>();
    const result = uncoveredScreens(index, KNOWN_ROUTES);
    expect(result).toHaveLength(KNOWN_ROUTES.length);
    for (const route of KNOWN_ROUTES) {
      expect(result).toContain(route);
    }
  });

  it('uncoveredScreens_returns_empty_array_when_all_routes_are_covered', () => {
    const index = new Map<string, []>();
    for (const route of KNOWN_ROUTES) {
      index.set(route, []);
    }
    const result = uncoveredScreens(index, KNOWN_ROUTES);
    expect(result).toHaveLength(0);
  });

  it('uncoveredScreens_returns_only_routes_absent_from_index', () => {
    const index = new Map<string, []>();
    index.set('/login', []);
    index.set('/projects', []);
    const result = uncoveredScreens(index, KNOWN_ROUTES);
    expect(result).not.toContain('/login');
    expect(result).not.toContain('/projects');
    expect(result).toContain('/organizations');
    expect(result).toContain('/users');
  });

  it('uncoveredScreens_result_is_sorted_alphabetically', () => {
    const index = new Map<string, []>();
    const result = uncoveredScreens(index, ['/zebra', '/apple', '/mango']);
    expect(result).toEqual(['/apple', '/mango', '/zebra']);
  });

  it('uncoveredScreens_unknown_routes_in_index_do_not_affect_result', () => {
    const index = new Map<string, []>();
    index.set('/unknown-route', []);
    index.set('/another-unknown', []);
    const knownRoutes = ['/login', '/projects'];
    const result = uncoveredScreens(index, knownRoutes);
    expect(result).toEqual(['/login', '/projects']);
  });
});

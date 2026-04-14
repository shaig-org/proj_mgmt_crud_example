import { describe, it, expect } from 'vitest';
import {
  deriveFeature,
  groupByFeature,
  parseScenariosHash,
} from '../../src/aspects/scenarios/grouping';

describe('deriveFeature', () => {
  it('strips .scenario.spec.ts from the basename', () => {
    expect(
      deriveFeature('e2e/scenarios/org-create.scenario.spec.ts'),
    ).toBe('org-create');
  });

  it('handles plain .spec.ts and .ts', () => {
    expect(deriveFeature('foo/bar/member-invite.spec.ts')).toBe(
      'member-invite',
    );
    expect(deriveFeature('baz.ts')).toBe('baz');
  });

  it('returns null for undefined/empty input', () => {
    expect(deriveFeature(undefined)).toBeNull();
    expect(deriveFeature('')).toBeNull();
    expect(deriveFeature('   ')).toBeNull();
  });
});

describe('groupByFeature', () => {
  it('groups by explicit .feature, trimming whitespace', () => {
    const groups = groupByFeature([
      { id: 'a', title: 'A', feature: ' create project' },
      { id: 'b', title: 'B', feature: 'create project' },
      { id: 'c', title: 'C', feature: 'org' },
    ]);
    expect(groups).toHaveLength(2);
    const cp = groups.find((g) => g.slug === 'create-project')!;
    expect(cp.label).toBe('create project');
    expect(cp.scenarioIds).toEqual(['a', 'b']);
    const org = groups.find((g) => g.slug === 'org')!;
    expect(org.scenarioIds).toEqual(['c']);
  });

  it('falls back to specFile basename when no explicit feature', () => {
    const groups = groupByFeature([
      {
        id: 'x',
        title: 'X',
        specFile: 'e2e/scenarios/member-invite.scenario.spec.ts',
      },
    ]);
    expect(groups).toHaveLength(1);
    expect(groups[0]!.slug).toBe('member-invite');
  });

  it('puts scenarios with no feature or specFile into an "uncategorized" bucket', () => {
    const groups = groupByFeature([
      { id: 'n1', title: 'N1' },
      { id: 'n2', title: 'N2', feature: '   ' },
    ]);
    expect(groups).toHaveLength(1);
    expect(groups[0]!.slug).toBe('uncategorized');
    expect(groups[0]!.scenarioIds).toEqual(['n1', 'n2']);
  });

  it('preserves first-appearance order of groups', () => {
    const groups = groupByFeature([
      { id: 'a', title: 'A', feature: 'second' },
      { id: 'b', title: 'B', feature: 'first' },
      { id: 'c', title: 'C', feature: 'second' },
    ]);
    expect(groups.map((g) => g.slug)).toEqual(['second', 'first']);
  });
});

describe('parseScenariosHash', () => {
  it('parses aspect id and group param', () => {
    expect(parseScenariosHash('#/scenarios?group=org')).toEqual({
      aspectId: 'scenarios',
      group: 'org',
    });
  });

  it('returns null group when missing or empty', () => {
    expect(parseScenariosHash('#/scenarios')).toEqual({
      aspectId: 'scenarios',
      group: null,
    });
    expect(parseScenariosHash('#/scenarios?group=')).toEqual({
      aspectId: 'scenarios',
      group: null,
    });
  });
});

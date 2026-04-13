import { describe, it, expect } from 'vitest';
import {
  buildRegistry,
  DuplicateAspectIdError,
  getAspect,
} from '../../src/lib/registry';
import type { AnyAspect } from '../../src/aspects/types';

function stub(id: string): AnyAspect {
  return {
    id,
    title: id,
    icon: '*',
    sourceRoots: [],
    artifacts: [{ url: '/x', label: 'x', repoPath: 'x' }],
    refreshCommand: 'echo',
    refreshCwd: '.',
    refreshDescription: 'x',
    load: async () => ({}),
    render: () => null,
  };
}

describe('registry', () => {
  it('registry_resolves_aspect_by_id', () => {
    const reg = buildRegistry([stub('scenarios'), stub('capabilities')]);
    const a = getAspect(reg, 'scenarios');
    expect(a?.id).toBe('scenarios');
  });

  it('registry_returns_undefined_for_unknown_id', () => {
    const reg = buildRegistry([stub('scenarios')]);
    expect(getAspect(reg, 'nope')).toBeUndefined();
  });

  it('registry_aspect_ids_are_unique', () => {
    expect(() =>
      buildRegistry([stub('scenarios'), stub('scenarios')]),
    ).toThrow(DuplicateAspectIdError);
  });
});

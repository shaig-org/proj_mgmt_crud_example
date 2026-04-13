import { describe, it, expect } from 'vitest';
import { buildRows, classifyRoute } from '../../src/aspects/capabilities/classifier';
import type { CapabilityDocument } from '../../src/aspects/capabilities/types';

describe('capabilities classifier', () => {
  it('capabilities_status_classifier_unchanged', () => {
    const r = classifyRoute(['a', 'b'], ['a', 'b']);
    expect(r.status).toBe('unchanged');
    expect(r.added).toEqual([]);
    expect(r.removed).toEqual([]);
  });

  it('capabilities_status_classifier_expanded', () => {
    const r = classifyRoute(['a'], ['a', 'b']);
    expect(r.status).toBe('expanded');
    expect(r.added).toEqual(['b']);
  });

  it('capabilities_status_classifier_reduced', () => {
    const r = classifyRoute(['a', 'b'], ['a']);
    expect(r.status).toBe('reduced');
    expect(r.removed).toEqual(['b']);
  });

  it('capabilities_status_classifier_new_route', () => {
    const r = classifyRoute(null, ['x']);
    expect(r.status).toBe('new');
    expect(r.added).toEqual(['x']);
  });

  it('capabilities_status_classifier_removed_route', () => {
    const r = classifyRoute(['x'], null);
    expect(r.status).toBe('removed');
    expect(r.removed).toEqual(['x']);
  });

  it('buildRows joins by method+path', () => {
    const baseline: CapabilityDocument = {
      routes: [
        { method: 'GET', path: '/a', handler: 'h.a', capabilities: ['r'] },
        { method: 'POST', path: '/b', handler: 'h.b', capabilities: ['w'] },
      ],
    };
    const report: CapabilityDocument = {
      routes: [
        { method: 'GET', path: '/a', handler: 'h.a', capabilities: ['r', 'w'] },
        { method: 'PUT', path: '/c', handler: 'h.c', capabilities: ['new'] },
      ],
    };
    const rows = buildRows(baseline, report);
    const statuses = Object.fromEntries(rows.map((r) => [`${r.method} ${r.path}`, r.status]));
    expect(statuses['GET /a']).toBe('expanded');
    expect(statuses['POST /b']).toBe('removed');
    expect(statuses['PUT /c']).toBe('new');
  });
});

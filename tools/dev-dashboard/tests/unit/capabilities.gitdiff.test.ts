import { describe, it, expect } from 'vitest';
import { parseGitDiff } from '../../src/aspects/capabilities/classifier';
import type { GitDiffDocument } from '../../src/aspects/capabilities/types';

const MINIMAL_DOC: GitDiffDocument = {
  from_ref: 'main',
  to_ref: 'HEAD',
  from_commit: 'aaaaaaa1',
  to_commit: 'bbbbbbb2',
  generated_at: '2026-04-15T10:00:00+00:00',
  routes: [],
  summary: { total: 0, unchanged: 0, expanded: 0, reduced: 0, new: 0, removed: 0 },
};

describe('parseGitDiff', () => {
  it('git_diff_parse_preserves_refs', () => {
    const data = parseGitDiff(MINIMAL_DOC);
    expect(data.fromRef).toBe('main');
    expect(data.toRef).toBe('HEAD');
    expect(data.fromCommit).toBe('aaaaaaa1');
    expect(data.toCommit).toBe('bbbbbbb2');
  });

  it('git_diff_parse_empty_routes_produces_empty_rows', () => {
    const data = parseGitDiff(MINIMAL_DOC);
    expect(data.rows).toHaveLength(0);
  });

  it('git_diff_parse_expanded_route_maps_to_row', () => {
    const doc: GitDiffDocument = {
      ...MINIMAL_DOC,
      routes: [
        {
          method: 'GET',
          path: '/api/tickets',
          handler: 'ticket_api.list',
          from_capabilities: ['TicketReadCapability'],
          to_capabilities: ['TicketReadCapability', 'ProjectReadCapability'],
          status: 'expanded',
          added: ['ProjectReadCapability'],
          removed: [],
        },
      ],
      summary: { total: 1, unchanged: 0, expanded: 1, reduced: 0, new: 0, removed: 0 },
    };
    const data = parseGitDiff(doc);
    expect(data.rows).toHaveLength(1);
    const row = data.rows[0];
    expect(row.status).toBe('expanded');
    expect(row.baseline).toEqual(['TicketReadCapability']);
    expect(row.current).toEqual(['ProjectReadCapability', 'TicketReadCapability']);   // sorted
    expect(row.added).toEqual(['ProjectReadCapability']);
    expect(row.removed).toEqual([]);
  });

  it('git_diff_parse_new_route_has_null_baseline', () => {
    const doc: GitDiffDocument = {
      ...MINIMAL_DOC,
      routes: [
        {
          method: 'POST',
          path: '/api/widgets',
          handler: 'widget_api.create',
          from_capabilities: null,
          to_capabilities: ['WidgetWriteCapability'],
          status: 'new',
          added: ['WidgetWriteCapability'],
          removed: [],
        },
      ],
      summary: { total: 1, unchanged: 0, expanded: 0, reduced: 0, new: 1, removed: 0 },
    };
    const data = parseGitDiff(doc);
    const row = data.rows[0];
    expect(row.status).toBe('new');
    expect(row.baseline).toBeNull();
    expect(row.current).toEqual(['WidgetWriteCapability']);
    expect(row.added).toEqual(['WidgetWriteCapability']);
  });

  it('git_diff_parse_removed_route_has_null_current', () => {
    const doc: GitDiffDocument = {
      ...MINIMAL_DOC,
      routes: [
        {
          method: 'DELETE',
          path: '/api/legacy',
          handler: 'legacy_api.delete',
          from_capabilities: ['LegacyWriteCapability'],
          to_capabilities: null,
          status: 'removed',
          added: [],
          removed: ['LegacyWriteCapability'],
        },
      ],
      summary: { total: 1, unchanged: 0, expanded: 0, reduced: 0, new: 0, removed: 1 },
    };
    const data = parseGitDiff(doc);
    const row = data.rows[0];
    expect(row.status).toBe('removed');
    expect(row.baseline).toEqual(['LegacyWriteCapability']);
    expect(row.current).toBeNull();
    expect(row.removed).toEqual(['LegacyWriteCapability']);
  });

  it('git_diff_parse_unchanged_route', () => {
    const doc: GitDiffDocument = {
      ...MINIMAL_DOC,
      routes: [
        {
          method: 'GET',
          path: '/api/projects',
          handler: 'project_api.list',
          from_capabilities: ['ProjectReadCapability'],
          to_capabilities: ['ProjectReadCapability'],
          status: 'unchanged',
          added: [],
          removed: [],
        },
      ],
      summary: { total: 1, unchanged: 1, expanded: 0, reduced: 0, new: 0, removed: 0 },
    };
    const data = parseGitDiff(doc);
    const row = data.rows[0];
    expect(row.status).toBe('unchanged');
    expect(row.added).toHaveLength(0);
    expect(row.removed).toHaveLength(0);
  });

  it('git_diff_parse_summary_preserved', () => {
    const summary = { total: 10, unchanged: 7, expanded: 1, reduced: 1, new: 1, removed: 0 };
    const data = parseGitDiff({ ...MINIMAL_DOC, summary });
    expect(data.summary).toEqual(summary);
  });

  it('git_diff_parse_generated_at_preserved', () => {
    const data = parseGitDiff(MINIMAL_DOC);
    expect(data.generatedAt).toBe('2026-04-15T10:00:00+00:00');
  });

  it('git_diff_parse_capabilities_are_sorted', () => {
    const doc: GitDiffDocument = {
      ...MINIMAL_DOC,
      routes: [
        {
          method: 'GET',
          path: '/api/x',
          handler: 'x_api.get',
          from_capabilities: ['ZCapability', 'ACapability'],
          to_capabilities: ['ZCapability', 'MCapability', 'ACapability'],
          status: 'expanded',
          added: ['MCapability'],
          removed: [],
        },
      ],
      summary: { total: 1, unchanged: 0, expanded: 1, reduced: 0, new: 0, removed: 0 },
    };
    const data = parseGitDiff(doc);
    const row = data.rows[0];
    expect(row.baseline).toEqual(['ACapability', 'ZCapability']);
    expect(row.current).toEqual(['ACapability', 'MCapability', 'ZCapability']);
  });
});

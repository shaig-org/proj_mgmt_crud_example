// Regression tests that lock in the schema emitted by the real
// walkthrough generator (frontend/scripts/generate-walkthroughs.ts) and the
// capability analyzer (backend/.../tools/analyze_capabilities.py).
//
// When one of these producers changes its output shape, these tests should
// fail loudly — that's exactly the class of bug that shipped to the user
// on first run ("Artifact is missing required field: scenarios[0].id").

import { describe, it, expect } from 'vitest';
import { validate as validateScenarios } from '../../src/aspects/scenarios/ScenariosAspect';
import { buildRows } from '../../src/aspects/capabilities/classifier';

describe('scenarios manifest — real walkthrough-generator schema', () => {
  const realManifest = {
    generatedAt: '2026-04-14T04:02:41.793Z',
    scenarios: [
      {
        name: 'Create project full flow',
        slug: 'create-project-full-flow-1776139319974-w2',
        specFile: 'e2e/scenarios/create-project.scenario.spec.ts',
        correlationId: 'create-project-full-flow-1776139319974-w2',
        startedAt: '2026-04-14T04:01:59.981Z',
        endedAt: '2026-04-14T04:02:01.313Z',
        durationMs: 1332,
        status: 'passed',
        steps: [
          {
            index: 1,
            name: 'login as project manager',
            slug: 'login-as-project-manager',
            screenshot:
              'screenshots/create-project-full-flow-1776139319974-w2/01-login-as-project-manager.png',
            startedAt: '2026-04-14T04:01:59.982Z',
            durationMs: 636,
            status: 'passed',
          },
          {
            index: 2,
            name: 'open new project modal',
            slug: 'open-new-project-modal',
            screenshot:
              'screenshots/create-project-full-flow-1776139319974-w2/02-open-new-project-modal.png',
            startedAt: '2026-04-14T04:02:00.618Z',
            durationMs: 91,
            status: 'passed',
          },
        ],
        videoPath:
          'videos/create-project-full-flow-1776139319974-w2.webm',
        tracePath:
          'traces/create-project-full-flow-1776139319974-w2.zip',
        gifPath: 'gifs/create-project-full-flow-1776139319974-w2.gif',
        motionGifPath:
          'gifs/create-project-full-flow-1776139319974-w2-motion.gif',
        videoGalleryPath:
          'videos/create-project-full-flow-1776139319974-w2.webm',
        feature: ' create project',
      },
    ],
  };

  it('accepts slug→id and name→title from real manifest', () => {
    const out = validateScenarios(realManifest);
    expect(out.scenarios).toHaveLength(1);
    const s = out.scenarios[0]!;
    expect(s.id).toBe('create-project-full-flow-1776139319974-w2');
    expect(s.title).toBe('Create project full flow');
  });

  it('normalizes status "passed" to "passing"', () => {
    const s = validateScenarios(realManifest).scenarios[0]!;
    expect(s.status).toBe('passing');
  });

  it('maps gifPath/videoPath to gif/video (URL-resolved under /artifacts/scenarios/)', () => {
    const s = validateScenarios(realManifest).scenarios[0]!;
    expect(s.gif).toBe(
      '/artifacts/scenarios/gifs/create-project-full-flow-1776139319974-w2.gif',
    );
    expect(s.video).toBe(
      '/artifacts/scenarios/videos/create-project-full-flow-1776139319974-w2.webm',
    );
  });

  it('maps step.name → step.label and keeps step.screenshot', () => {
    const s = validateScenarios(realManifest).scenarios[0]!;
    expect(s.steps).toHaveLength(2);
    expect(s.steps![0]!.label).toBe('login as project manager');
    expect(s.steps![0]!.screenshot).toBe(
      '/artifacts/scenarios/screenshots/create-project-full-flow-1776139319974-w2/01-login-as-project-manager.png',
    );
  });

  it('derives a thumbnail from the first step screenshot when no explicit thumbnail is given', () => {
    const s = validateScenarios(realManifest).scenarios[0]!;
    expect(s.thumbnail).toBe(
      '/artifacts/scenarios/screenshots/create-project-full-flow-1776139319974-w2/01-login-as-project-manager.png',
    );
  });

  it('still accepts the internal-shape manifest (id/title/gif/video/step.label)', () => {
    const internal = {
      scenarios: [
        {
          id: 'org_create',
          title: 'Create org',
          gif: 'media/org_create.gif',
          video: 'media/org_create.webm',
          steps: [{ index: 1, label: 'Open signup' }],
        },
      ],
    };
    const out = validateScenarios(internal);
    expect(out.scenarios[0]!.id).toBe('org_create');
    expect(out.scenarios[0]!.steps![0]!.label).toBe('Open signup');
  });

  it('throws with a field path when both id and slug are missing', () => {
    expect(() =>
      validateScenarios({ scenarios: [{ name: 'no id', gifPath: 'x.gif' }] }),
    ).toThrow(/scenarios\[0\]\.id\|slug/);
  });
});

describe('capabilities — real analyze_capabilities.py schema', () => {
  // Shape copied verbatim from backend/evidence/capabilities/baseline.json.
  const realBaseline = {
    routes: [
      {
        capabilities: ['ActivityLogReadCapability'],
        handler: 'activity_log_api.list_activity_logs',
        method: 'GET',
        path: '/api/activity-logs',
      },
      {
        capabilities: ['OrgCommentModerationCapability'],
        handler: 'comment_api.moderate_delete_comment',
        method: 'DELETE',
        path: '/api/admin/comments/{comment_id}',
      },
    ],
  };

  it('buildRows accepts the real schema (unchanged vs identical report)', () => {
    const rows = buildRows(realBaseline, realBaseline);
    expect(rows).toHaveLength(2);
    for (const r of rows) expect(r.status).toBe('unchanged');
  });

  it('buildRows flags a new route when present only in report', () => {
    const report = {
      routes: [
        ...realBaseline.routes,
        {
          capabilities: ['CommentReadCapability'],
          handler: 'comment_api.get_comment',
          method: 'GET',
          path: '/api/comments/{comment_id}',
        },
      ],
    };
    const rows = buildRows(realBaseline, report);
    const newRow = rows.find((r) => r.path === '/api/comments/{comment_id}');
    expect(newRow?.status).toBe('new');
    expect(newRow?.added).toContain('CommentReadCapability');
  });

  it('buildRows falls back to baseline-only (all unchanged) when report is null', () => {
    const rows = buildRows(realBaseline, null);
    expect(rows).toHaveLength(2);
    for (const r of rows) expect(r.status).toBe('unchanged');
  });
});

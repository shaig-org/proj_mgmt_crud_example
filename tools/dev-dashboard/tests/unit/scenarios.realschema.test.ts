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
import { parseRequestTrace } from '../../src/aspects/e2e-traces/types';

describe('scenarios manifest — real walkthrough-generator schema', () => {
  const realManifest = {
    generatedAt: '2026-04-14T04:02:41.793Z',
    scenarios: [
      {
        name: 'Create project full flow',
        slug: 'create-project-full-flow-1776139319974-w2',
        specFile: 'e2e/scenarios/projects/create-project.scenario.spec.ts',
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
            url: 'http://localhost:5173/projects',
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
            url: 'http://localhost:5173/projects',
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

  it('maps gifPath/videoPath to gif/video (URL-resolved under /artifacts/scenarios/gallery/)', () => {
    const s = validateScenarios(realManifest).scenarios[0]!;
    expect(s.gif).toBe(
      '/artifacts/scenarios/gallery/gifs/create-project-full-flow-1776139319974-w2.gif',
    );
    expect(s.video).toBe(
      '/artifacts/scenarios/gallery/videos/create-project-full-flow-1776139319974-w2.webm',
    );
  });

  it('maps step.name → step.label and keeps step.screenshot', () => {
    const s = validateScenarios(realManifest).scenarios[0]!;
    expect(s.steps).toHaveLength(2);
    expect(s.steps![0]!.label).toBe('login as project manager');
    expect(s.steps![0]!.screenshot).toBe(
      '/artifacts/scenarios/gallery/screenshots/create-project-full-flow-1776139319974-w2/01-login-as-project-manager.png',
    );
  });

  it('step.url_is_forwarded_when_present_in_manifest', () => {
    const s = validateScenarios(realManifest).scenarios[0]!;
    expect(s.steps![0]!.url).toBe('http://localhost:5173/projects');
  });

  it('step.url_is_undefined_when_absent_from_manifest', () => {
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
    expect(out.scenarios[0]!.steps![0]!.url).toBeUndefined();
  });

  it('derives a thumbnail from the first step screenshot when no explicit thumbnail is given', () => {
    const s = validateScenarios(realManifest).scenarios[0]!;
    expect(s.thumbnail).toBe(
      '/artifacts/scenarios/gallery/screenshots/create-project-full-flow-1776139319974-w2/01-login-as-project-manager.png',
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

describe('e2e-traces — real E2eTracingMiddleware schema', () => {
  // Shape copied verbatim from a real backend/e2e-traces/{id}/req-NNN.json file
  // produced by backend/project_management_crud_example/middleware/e2e_tracing.py.
  // When the middleware changes its JSON output shape, this test should fail loudly.
  const realRequestTrace = {
    seq: 1,
    method: 'GET',
    path: '/health',
    status_code: 200,
    duration_ms: 5,
    timestamp_ms: 1734567890000,
    call_events: [
      {
        event: 'call',
        file: 'routers/health.py',
        function: 'health_check',
        line: 10,
        depth: 0,
        timestamp_ns: 0,
      },
      {
        event: 'return',
        file: 'routers/health.py',
        function: 'health_check',
        line: 10,
        depth: 0,
        timestamp_ns: 500,
      },
    ],
  };

  it('accepts all required fields from real middleware output', () => {
    const trace = parseRequestTrace(realRequestTrace);
    expect(trace.seq).toBe(1);
    expect(trace.method).toBe('GET');
    expect(trace.path).toBe('/health');
    expect(trace.status_code).toBe(200);
    expect(trace.duration_ms).toBe(5);
    expect(trace.timestamp_ms).toBe(1734567890000);
    expect(trace.call_events).toHaveLength(2);
  });

  it('call_events have all required fields with correct types', () => {
    const trace = parseRequestTrace(realRequestTrace);
    const evt = trace.call_events[0]!;
    expect(evt.event).toBe('call');
    expect(typeof evt.file).toBe('string');
    expect(typeof evt.function).toBe('string');
    expect(typeof evt.line).toBe('number');
    expect(typeof evt.depth).toBe('number');
    expect(typeof evt.timestamp_ns).toBe('number');
  });

  it('throws with field path when seq is missing', () => {
    const noSeq = Object.fromEntries(
      Object.entries(realRequestTrace).filter(([k]) => k !== 'seq'),
    );
    expect(() => parseRequestTrace(noSeq)).toThrow(/seq/);
  });

  it('throws when status_code is missing', () => {
    const noStatus = Object.fromEntries(
      Object.entries(realRequestTrace).filter(([k]) => k !== 'status_code'),
    );
    expect(() => parseRequestTrace(noStatus)).toThrow(/status_code/);
  });

  it('throws when call_events is not an array', () => {
    expect(() => parseRequestTrace({ ...realRequestTrace, call_events: 'oops' })).toThrow(
      /call_events/,
    );
  });
});

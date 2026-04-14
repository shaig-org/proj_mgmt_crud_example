// Shared declarative aspect config. Imported by both the Vite-side TS
// registry (via JS interop) and the Node-side staleness script. Do NOT put
// render/load functions here — only data.

/**
 * @typedef {Object} AspectArtifactConfig
 * @property {string} url              URL (under /artifacts/...) the dashboard fetches.
 * @property {string} label            Human-readable filename label.
 * @property {string} repoPath         Repo-relative path (for UI display).
 * @property {string} fsPath           Repo-relative path on disk (for staleness stat).
 */

/**
 * @typedef {Object} AspectConfig
 * @property {string} id
 * @property {string} title
 * @property {string[]} sourceRoots           Repo-relative dirs whose mtimes determine staleness.
 * @property {AspectArtifactConfig[]} artifacts  First entry is "primary".
 * @property {string} refreshCommand
 * @property {string} refreshCwd
 * @property {string} refreshDescription
 */

/** @type {AspectConfig[]} */
export const aspectsConfig = [
  {
    id: 'scenarios',
    title: 'Scenarios',
    sourceRoots: ['frontend/e2e/scenarios'],
    artifacts: [
      {
        url: '/artifacts/scenarios/manifest.json',
        label: 'manifest.json',
        repoPath: 'frontend/walkthroughs/gallery/manifest.json',
        fsPath: 'frontend/walkthroughs/gallery/manifest.json',
      },
    ],
    refreshCommand: 'npm --prefix frontend run walkthroughs:generate',
    refreshCwd: '<repo-root>',
    refreshDescription:
      're-runs scenario tests headed and captures GIFs, screenshots, and step transcripts.',
  },
  {
    id: 'capabilities',
    title: 'Capabilities',
    sourceRoots: ['backend/project_management_crud_example/routers'],
    artifacts: [
      {
        url: '/artifacts/capabilities/report.json',
        label: 'report.json',
        repoPath: 'backend/evidence/capabilities/report.json',
        fsPath: 'backend/evidence/capabilities/report.json',
      },
      {
        url: '/artifacts/capabilities/baseline.json',
        label: 'baseline.json',
        repoPath: 'backend/evidence/capabilities/baseline.json',
        fsPath: 'backend/evidence/capabilities/baseline.json',
      },
    ],
    refreshCommand:
      'uv --project backend run python -m project_management_crud_example.tools.analyze_capabilities',
    refreshCwd: '<repo-root>',
    refreshDescription:
      're-runs capability analysis against the current route handlers and writes report.json.',
  },
  {
    id: 'traces',
    title: 'Traces',
    sourceRoots: ['backend/tests'],
    artifacts: [
      {
        url: '/artifacts/traces/',
        label: '.trace-artifacts/',
        repoPath: 'backend/.trace-artifacts/',
        fsPath: 'backend/.trace-artifacts',
      },
    ],
    refreshCommand: 'npm --prefix frontend run e2e:scenarios',
    refreshCwd: '<repo-root>',
    refreshDescription:
      're-runs scenario tests; pytest-tracer writes per-scenario trace artifacts under backend/.trace-artifacts/.',
  },
  {
    id: 'e2e-traces',
    title: 'E2E Traces',
    sourceRoots: ['frontend/e2e/scenarios'],
    artifacts: [
      {
        url: '/artifacts/e2e-traces/',
        label: 'e2e-traces/',
        repoPath: 'backend/e2e-traces/',
        fsPath: 'backend/e2e-traces',
      },
    ],
    refreshCommand: 'npm --prefix frontend run e2e:scenarios',
    refreshCwd: '<repo-root>',
    refreshDescription:
      're-runs E2E scenario tests; backend E2E tracing middleware writes per-request call traces under backend/e2e-traces/.',
  },
];

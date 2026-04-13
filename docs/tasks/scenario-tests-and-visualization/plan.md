# Feature Plan: Scenario Tests & Evidence Visualization (POC)

**Status**: 🟡 Draft
**Date**: 2026-04-12
**Stack**: Frontend (tests + tooling only; no production FE or BE code changes)
**Rough spec**: `docs/rough_specs/SCENARIO_TESTS_AND_VISUALIZATIONS.md`
**Detailed spec**: none yet — this is a developer-tooling feature. Rough spec + this plan are authoritative. Formal spec not required because the feature is not a user-observable product capability (it is an engineering-evidence pipeline).

## 1. Requirements in scope

User-facing (developer-facing) capabilities this plan delivers:

- **SCN-001** — A `scenarioTest` fixture that wraps Playwright `test`, exposes a `step(name, fn)` helper that auto-numbers and captures a screenshot after each step, and emits one metadata JSON per scenario run.
- **SCN-002** — A dedicated Playwright project named `scenarios` (isolated from the existing 17 specs) with `video: 'on'`, `trace: 'on'`, explicit screenshots (no auto-on-failure), and scenario outputs written under `frontend/evidence/`.
- **SCN-003** — Three initial shipped scenarios under `frontend/e2e/scenarios/`:
  - `create-project.scenario.spec.ts`
  - `create-epic-in-project.scenario.spec.ts`
  - `create-ticket-and-change-status.scenario.spec.ts`
  Each 4–8 steps, UI-only inside the test body, parallel-safe data.
- **SCN-004** — An evidence generator script (`frontend/scripts/generate-evidence.ts`, invoked via `npm run evidence:generate`) that:
  - Reads per-scenario metadata JSONs from `frontend/evidence/metadata/`.
  - Reads Playwright-captured videos from the scenarios output dir.
  - Uses `ffmpeg` to produce a short (5–8 s target, 640 px wide, 10 fps) GIF per scenario.
  - Writes `frontend/evidence/gallery/manifest.json`.
  - Copies static viewer assets (HTML/CSS/JS) from `frontend/src-evidence-gallery/` into `frontend/evidence/gallery/`.
- **SCN-005** — A static HTML Evidence Viewer POC served from `frontend/evidence/gallery/`:
  - Sidebar with feature filter + search box.
  - Grid of scenario cards (GIF auto-play on hover).
  - Click card → modal with large GIF, screenshot filmstrip, metadata (correlation ID, timestamp, step list, duration), and links to the trace zip.
  - Reads `manifest.json`; zero build step; no framework.
- **SCN-006** — npm scripts:
  - `e2e:scenarios` — runs the `scenarios` Playwright project only.
  - `evidence:generate` — runs the generator.
  - `evidence:serve` — serves `frontend/evidence/gallery/` via `npx serve`.
- **SCN-007** — `frontend/.gitignore` additions: ignore all of `frontend/evidence/` (generated output). Viewer source lives in `frontend/src-evidence-gallery/` and IS committed.
- **SCN-008** — The existing `npm run e2e` continues to run all e2e projects including `scenarios`; validation gate (`npm run lint && npm run typecheck && npm run e2e`) stays zero-warning.

## 2. Out of scope

- **Evidence generation in CI.** The generator and viewer are dev-time tools. `ffmpeg` is assumed present locally; CI does not run `evidence:generate`. Scenario tests themselves DO run in CI as regular Playwright tests, but video/GIF post-processing does not.
- **"New / Changed / Passed" diffing** between runs (rough spec mentions highlighting changed evidence) — deferred. The viewer shows the latest run only; manifest has a single state.
- **"Jump to Test Code"** deep-linking from the viewer to source — deferred. Metadata will record the spec file path so this can be added later, but the viewer will not implement it in this POC.
- **Status chips (New/Changed/Passed)** filter beyond pass/fail — deferred; viewer only filters by feature/search.
- **Backend changes.** No API, domain, repository, or ORM changes. No correlation-ID ingestion on the backend (the scenario still sets `window.__CORRELATION_ID` for future use, but BE does not consume it in this feature).
- **Replacing existing specs.** The 17 existing specs are untouched and keep the current config (`trace: 'on-first-retry'`, no video).
- **Accessibility / i18n of the viewer.** POC.
- **Authentication / hosting** for the viewer. Local static only.
- **Unit tests for the generator script.** It is tooling; correctness is verified by the one end-to-end scenario-fixture test (see 4.3).

## 3. Architecture

This feature touches only `frontend/` and adds one doc. No backend changes.

### 3.1 Frontend changes

#### New files

- `frontend/e2e/helpers/scenario.ts` — exports `scenarioTest` (a Playwright `test.extend` fixture) and a `step()` helper. Responsibilities:
  - Generate a correlation ID per test: `${sanitize(testInfo.title)}-${Date.now()}-${workerIndex}`.
  - Inject the correlation ID via `page.addInitScript` into `window.__CORRELATION_ID` (best-effort hook; backend consumption is out of scope).
  - Provide `step(name: string, fn: () => Promise<void>)` that:
    - Wraps the body in `test.step(name, fn)` for trace grouping.
    - After `fn` resolves, takes `page.screenshot({ path: '<evidenceDir>/screenshots/<scenarioSlug>/<NN>-<slug>.png', fullPage: true })` where NN is zero-padded step index.
    - Records `{ index, name, slug, screenshot, startedAt, durationMs }` in an in-memory steps array.
  - After the test (via a fixture teardown) writes `frontend/evidence/metadata/<scenarioSlug>.json`:
    ```json
    {
      "name": "<test title>",
      "slug": "<scenarioSlug>",
      "specFile": "<relative path>",
      "correlationId": "...",
      "startedAt": "...ISO...",
      "endedAt": "...ISO...",
      "durationMs": 1234,
      "status": "passed|failed|timedout",
      "steps": [ { "index": 1, "name": "Open /projects", "slug": "open-projects", "screenshot": "screenshots/<scenarioSlug>/01-open-projects.png", "startedAt": "...", "durationMs": 120 } ],
      "videoPath": "videos/<scenarioSlug>.webm",
      "tracePath": "traces/<scenarioSlug>.zip"
    }
    ```
  - Resolves the test's produced video and trace paths from `testInfo.attachments` and copies (not moves) them to stable names under `frontend/evidence/videos/` and `frontend/evidence/traces/` during teardown.
  - Must be synchronous-safe regarding parallelism: each scenario writes its own file under a unique slug — no shared mutation.

- `frontend/e2e/scenarios/create-project.scenario.spec.ts` — uses `scenarioTest` to:
  1. Login as admin (via `beforeAll` API setup — not counted as a scenario step).
  2. `step('open-projects-page', ...)` — navigate to `/projects`.
  3. `step('open-new-project-modal', ...)` — click "New Project".
  4. `step('fill-project-form', ...)` — fill name/description.
  5. `step('submit-project-form', ...)` — click Create.
  6. `step('verify-project-in-list', ...)` — assert the created project visible.

- `frontend/e2e/scenarios/create-epic-in-project.scenario.spec.ts` — (project pre-created via API in `beforeAll`):
  1. `step('open-project-details', ...)`.
  2. `step('open-new-epic-modal', ...)`.
  3. `step('fill-epic-form', ...)`.
  4. `step('submit-epic-form', ...)`.
  5. `step('verify-epic-on-project-page', ...)`.

- `frontend/e2e/scenarios/create-ticket-and-change-status.scenario.spec.ts` — (project + epic via API):
  1. `step('open-epic-details', ...)`.
  2. `step('open-new-ticket-modal', ...)`.
  3. `step('fill-ticket-form', ...)`.
  4. `step('submit-ticket-form', ...)`.
  5. `step('open-ticket-details', ...)`.
  6. `step('change-ticket-status', ...)`.
  7. `step('verify-status-updated', ...)`.

- `frontend/e2e/scenarios/_fixture-smoketest.scenario.spec.ts` — see 4.3.

- `frontend/scripts/generate-evidence.ts` — Node/tsx script. Inputs: `frontend/evidence/metadata/*.json`, `frontend/evidence/videos/*.webm`. Output: `frontend/evidence/gallery/` populated with static viewer + `manifest.json` + rendered `gifs/<slug>.gif`. Uses `child_process.execFile('ffmpeg', [...])`. Palette + scale filter: `-vf "fps=10,scale=640:-1:flags=lanczos"`; duration clamped to 5–8 s by computing speed multiplier from source duration (`setpts=PTS/<mult>`). Exits non-zero on ffmpeg failure. No hard dependency from Playwright config — runs separately.

- `frontend/src-evidence-gallery/index.html`, `viewer.js`, `viewer.css` — static viewer source. Committed. Generator copies these into `frontend/evidence/gallery/` and injects / writes `manifest.json` alongside them.

- `docs/tasks/scenario-tests-and-visualization/plan.md` — this file.

#### Modified files

- `frontend/playwright.config.ts` — add a second project `scenarios`:
  ```ts
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    {
      name: 'scenarios',
      testDir: './e2e/scenarios',
      outputDir: './evidence/.playwright-output',
      use: {
        ...devices['Desktop Chrome'],
        video: 'on',
        trace: 'on',
        screenshot: 'off',
      },
    },
  ],
  ```
  The existing `chromium` project keeps `testDir: './e2e'` default behavior but MUST be scoped to exclude `e2e/scenarios/**` via `testIgnore: ['**/scenarios/**']` so scenarios don't run twice. Global setup/teardown and webServer are shared.

- `frontend/package.json` — add scripts:
  ```json
  "e2e:scenarios": "playwright test --project=scenarios",
  "evidence:generate": "tsx scripts/generate-evidence.ts",
  "evidence:serve": "npx --yes serve evidence/gallery -l 4173"
  ```
  Add devDependency on `tsx` (if not already present) and `serve` is invoked via `npx --yes` so no dep needed. No new runtime deps for the viewer.

- `frontend/.gitignore` — add `evidence/` (whole directory ignored; viewer source lives in `src-evidence-gallery/` and IS committed).

- `frontend/CLAUDE.md` — add a one-paragraph pointer to scenario tests: "Scenario tests live in `e2e/scenarios/` and use the `scenarioTest` fixture. Do not put regular specs there."

### 3.2 Backend changes

None.

### 3.3 FE/BE contract

N/A — no backend changes. Scenarios exercise the existing public UI and, transitively, existing APIs. Correlation ID injection into `window.__CORRELATION_ID` is forward-looking only; backend does not read it in this feature.

### 3.4 Directory layout (final)

```
frontend/
  e2e/
    scenarios/
      create-project.scenario.spec.ts
      create-epic-in-project.scenario.spec.ts
      create-ticket-and-change-status.scenario.spec.ts
      _fixture-smoketest.scenario.spec.ts
    helpers/
      scenario.ts
    ...existing specs...
  scripts/
    generate-evidence.ts
  src-evidence-gallery/        # committed viewer source
    index.html
    viewer.js
    viewer.css
  evidence/                    # gitignored, generated
    metadata/
    screenshots/<slug>/NN-*.png
    videos/<slug>.webm
    traces/<slug>.zip
    gifs/<slug>.gif
    gallery/
      index.html
      viewer.js
      viewer.css
      manifest.json
      gifs/
      screenshots/
    .playwright-output/
```

## 4. Test matrix

This feature is test/tooling infrastructure. The "tests" are limited to verifying the fixture itself works, because:
- The three shipped scenarios (SCN-003) are themselves the main user-observable tests of the frontend product flows; they run under `npm run e2e` as normal Playwright tests.
- The generator (`generate-evidence.ts`) is dev tooling; per principles "No speculative abstractions" — we don't unit-test it. It is manually verified during development and implicitly verified by the maintainer running `evidence:generate`.

### 4.1 API tests
N/A — no backend changes.

### 4.2 Repository tests
N/A — no backend changes.

### 4.3 Fixture verification test — `frontend/e2e/scenarios/_fixture-smoketest.scenario.spec.ts`

This file is a real `scenarioTest` that exercises a trivial UI path (login → land on /projects), AND uses `test.afterAll` to assert the helper produced its outputs on disk. It is the only meta-test — one scenario that self-verifies the fixture contract.

| Test name | Verifies | UI / assertion steps |
|---|---|---|
| `scenario_fixture_produces_numbered_screenshots_per_step` | `step()` writes `01-*.png`, `02-*.png`, ... under `evidence/screenshots/<slug>/` in call order | run 2 `step()` calls; in `afterAll` read dir, assert two files matching `^0[12]-.+\.png$` exist |
| `scenario_fixture_writes_metadata_json_with_expected_fields` | Teardown writes metadata JSON with `name`, `slug`, `correlationId`, `steps[]`, `status`, `videoPath`, `tracePath` populated | `afterAll` reads `evidence/metadata/<slug>.json`, parses, asserts all required keys present and `steps.length === 2` |
| `scenario_fixture_injects_correlation_id_into_window` | `window.__CORRELATION_ID` is set before first navigation | inside a `step`, `page.evaluate(() => (window as any).__CORRELATION_ID)` returns a non-empty string matching the slug pattern |
| `scenario_fixture_copies_video_and_trace_to_stable_paths` | Post-test, `evidence/videos/<slug>.webm` and `evidence/traces/<slug>.zip` exist with non-zero size | `afterAll` stats both files |
| `scenario_fixture_slug_is_parallel_safe` | Two scenarios with identical titles in different workers do not overwrite each other's metadata | covered by: slug includes `workerIndex` and `Date.now()`; verified by a unit-style assertion in `afterAll` that the emitted slug contains the workerIndex |

All five live in the single smoketest spec as separate `scenarioTest(...)` calls sharing one `afterAll`. The smoketest spec is included in the `scenarios` Playwright project and runs under `npm run e2e`.

### 4.4 Shipped user-flow scenarios — `frontend/e2e/scenarios/*.scenario.spec.ts`

These double as regular E2E tests (they assert real product behavior). They run under `npm run e2e`. Failures block the validation gate.

| Test name | Verifies | UI steps |
|---|---|---|
| `scenario_create_project_full_flow` | Admin can create a project via UI and see it in the list | open `/projects` → open new-project modal → fill form → submit → assert new project row visible |
| `scenario_create_epic_in_project` | Given a project (API pre-created), admin can create an epic under it via UI | open project details → open new-epic modal → fill form → submit → assert epic appears in project's epic list |
| `scenario_create_ticket_and_change_status` | Given project+epic (API pre-created), admin can create a ticket and transition its status | open epic details → open new-ticket modal → fill form → submit → open ticket details → change status → assert status updated in UI |

Each test must:
- Use `beforeAll` for API-based org/user/project/epic setup (following existing e2e conventions).
- Be UI-only inside the test body.
- Use `toBeVisible` / `toHaveValue`; no `waitForTimeout`.
- Generate unique test data via `frontend/e2e/utils/test-config.ts` helpers to stay parallel-safe.

### 4.5 Unit / component tests
N/A. No production source code is added.

### 4.6 Property-based tests
N/A. See `write-pbt` skill; no invariants of interest at this layer.

### 4.7 Generator script tests
Deliberately none (see preamble). Manual acceptance check documented in 7.step 7.

## 5. Test fixtures and helpers

### Existing helpers reused
- `frontend/e2e/utils/test-config.ts` — worker-safe unique data generation for all scenarios.
- Existing login / API helpers used by the current 17 specs (whichever is currently canonical — engineer to reuse, not reinvent).
- `frontend/e2e/global-setup.ts` / `global-teardown.ts` — unchanged.

### New helpers
- `frontend/e2e/helpers/scenario.ts`:
  - `export const scenarioTest = base.test.extend<ScenarioFixtures>({...})`
  - `ScenarioFixtures`:
    - `step: (name: string, fn: () => Promise<void>) => Promise<void>` — auto-screenshot + metadata recording.
    - `correlationId: string` — readable from the test body if needed.
  - `slugify(title: string): string`
  - Internal: per-test `MetadataCollector` that flushes in the fixture's teardown (use `use(...)` pattern of Playwright fixtures).

### Types
- All types colocated in `scenario.ts`. No `any`. Strict TS.

## 6. Edge cases covered

- **Parallel workers running the same scenario title** — slug includes `workerIndex` + `Date.now()`; metadata filenames never collide.
- **Step function throws** — screenshot still attempted via `try/finally`; metadata records `status: 'failed'` and the failing step's index; Playwright test still fails.
- **Video not produced** (e.g., scenario aborted before any nav) — teardown tolerates missing attachment; metadata records `videoPath: null`; generator skips GIF for scenarios without video and logs.
- **ffmpeg not installed** — generator detects `ENOENT` on spawn, prints actionable message ("install ffmpeg; this is a dev-only tool"), exits 1; does not affect `npm run e2e`.
- **Very short scenario (< 5 s of video)** — GIF clamping: if source shorter than 5 s, do NOT speed up; keep natural speed.
- **Very long scenario (> 30 s)** — clamp playback to 8 s max by computing `setpts=PTS/(duration/8)`.
- **Unicode / special characters in test titles** — `slugify` strips to `[a-z0-9-]+`.
- **CI environment** — scenario tests run (video on, trace on), but `evidence:generate` does NOT run; artifacts size is bounded by retention of Playwright's `outputDir` only, which is already cleaned per run.
- **Evidence dir missing on first run** — helper and generator both `mkdir -p` all output subdirs.
- **Stale evidence from prior runs** — generator clears `gallery/` and `gifs/` before writing; does NOT clear `metadata/`, `videos/`, `traces/`, `screenshots/` (those are per-slug and overwritten per scenario run; stale slugs from renamed tests accumulate — acceptable for POC, documented as known limitation).
- **Gitignore correctness** — `frontend/evidence/` is fully ignored; viewer source under `frontend/src-evidence-gallery/` remains committed.
- **The existing 17 specs continue to pass unchanged** — `testIgnore: ['**/scenarios/**']` on the `chromium` project prevents double-runs.

## 7. Implementation order

1. Add `frontend/.gitignore` entry for `evidence/`.
2. Add `scenarios` Playwright project in `playwright.config.ts` and the `testIgnore` to `chromium`.
3. Implement `frontend/e2e/helpers/scenario.ts`.
4. Write `_fixture-smoketest.scenario.spec.ts` (4.3). Run `npm run e2e:scenarios`; confirm it passes and produces expected files under `frontend/evidence/`.
5. Write the three shipped scenarios (4.4). Run `npm run e2e` end-to-end; confirm zero warnings, zero failures, all existing specs + scenarios green.
6. Implement `frontend/src-evidence-gallery/` static viewer source (HTML/CSS/JS reading `./manifest.json`).
7. Implement `frontend/scripts/generate-evidence.ts`. Add npm scripts (`e2e:scenarios`, `evidence:generate`, `evidence:serve`). Manually verify: after an `npm run e2e:scenarios` run, `npm run evidence:generate` produces `frontend/evidence/gallery/index.html` with three GIFs and a working manifest; `npm run evidence:serve` serves at http://localhost:4173.
8. Update `frontend/CLAUDE.md` with one-paragraph pointer.
9. Full validation: `npm run lint && npm run typecheck && npm run e2e` — zero errors, zero warnings.
10. code-reviewer pass.

## 8. Risks / open questions

- **Video always on for the `scenarios` project** increases disk I/O during test runs. Mitigation: only the `scenarios` project has `video: 'on'`; existing 17 specs unchanged. Acceptable.
- **Playwright's `testInfo.attachments` for video/trace** may be produced only after the test body completes. The fixture teardown must run AFTER Playwright has flushed the video to disk. Playwright fixtures' `use(...)` cleanup runs after the test closes, which is the correct hook; confirm during implementation. If timing is wrong, fall back to reading `testInfo.outputPath` / waiting on `page.video()?.path()`.
- **`trace: 'on'` produces per-test trace.zip**; must copy to stable `evidence/traces/<slug>.zip` — same timing concern as video.
- **GIF duration clamping heuristic** (5–8 s) may feel too fast for long flows. POC-acceptable; tune later.
- **Stale slug accumulation** in `evidence/screenshots/` when scenarios are renamed — acceptable for POC; user can delete `evidence/` to reset. Documented.
- **Running `scenarios` project as part of `npm run e2e`** roughly doubles the artifact footprint of those three scenarios. Acceptable given only three scenarios.
- **ffmpeg in CI** — not required; CI runs scenarios (as tests) but does not generate evidence. Documented in README/CLAUDE.md.
- **No backend correlation-ID ingestion** means `window.__CORRELATION_ID` is currently unused by BE; it is forward-looking only. If the team wants end-to-end correlation now, that is a separate feature (out of scope here).
- **Typecheck for `scripts/generate-evidence.ts`** — must be covered by `tsconfig.node.json` include list, or added to it. Engineer to verify; may require a minor `tsconfig.node.json` update (counts as tooling config, not production code).

## Deviations (round 2) — 2026-04-12

Four reviewer-driven enhancements to the evidence viewer, shipped on top of commits 7f99e5e and e8c1bd5:

1. **Videos preserved verbatim.** The helper already writes `evidence/videos/<slug>.webm`. The generator now ALSO copies each video into `evidence/gallery/videos/<slug>.webm` so the viewer (served from `gallery/`) can reference it with a relative URL, and adds `videoGalleryPath` to each manifest entry (alongside the pre-existing raw `videoPath`). Scenario detail view embeds an HTML5 `<video controls>` plus a download link; gallery cards expose a "Video" pill.

2. **Per-scenario Screenshots page — dedicated hash-routed screen.** New hash-routing in `viewer.js` with three routes: `#/` (gallery), `#/scenario/<slug>` (detail), `#/scenario/<slug>/screenshots`, `#/scenario/<slug>/flow`. Screenshots page renders a responsive CSS grid (`minmax(320px, 1fr)`) of large thumbnails, each showing zero-padded step number + name. Clicking a thumbnail opens a full-screen lightbox with prev/next buttons + keyboard `ArrowLeft` / `ArrowRight` / `Escape` support. The old inline modal was removed — detail views are now their own routes.

3. **Flow overview page.** Route `#/scenario/<slug>/flow`. Compact CSS-grid "flow strip" showing every step screenshot at ~220px minimum width in reading order, with numbered badges. Frames are clickable and delegate into the same lightbox. Linked from the gallery card (pill), scenario detail (pill), and Screenshots page.

4. **GIF pacing — already addressed in commit e8c1bd5.** Verified the pipeline is now producing: (a) a flipbook GIF built from per-step PNGs at 5 fps with 1s holds per step — one frame per scenario step — as the primary comprehension aid; (b) a motion GIF from the video at 5 fps (no speed-up, no duration cap) alongside it. Both GIFs are surfaced side-by-side on the scenario detail page, along with the raw video. The generator logs `fps`, source duration, and rendered duration per GIF. The old `speedFilter`/duration-cap logic is gone. No further changes to the generator were needed for this round; this deviation entry documents the already-landed behavior.

### Files touched (round 2)
- `frontend/src-evidence-gallery/index.html` — switched to `#app` container + global lightbox element.
- `frontend/src-evidence-gallery/viewer.js` — full rewrite: hash routing, gallery / detail / screenshots / flow views, keyboard-navigable lightbox.
- `frontend/src-evidence-gallery/viewer.css` — new styles for pills, shot grid, flow strip, lightbox.
- `docs/tasks/scenario-tests-and-visualization/plan.md` — this section.

### Known non-goals
- Lightbox does not preload neighbouring images (POC; dataset is tiny).
- Flow strip does not resize frames responsively beyond CSS grid auto-fill; there is no zoom slider.

## Deviations (round 3) — 2026-04-12

Second-pass UX polish on the scenario evidence viewer. All changes frontend-
only; no backend, no production FE. Static viewer served over HTTP via
`npm run evidence:serve` (no `file://` support required).

1. **Slower motion GIF via `setpts` + lower fps.** The motion GIF pipeline
   now stretches wall-clock time by `MOTION_SLOWDOWN=2.0` (`setpts=2.0*PTS`)
   and outputs at `MOTION_FPS=3` (333 ms/frame). A 2 s source video now
   yields a ~4 s GIF — readable on the first pass. Flipbook GIF hold is
   `FLIPBOOK_HOLD_SECONDS=1.5` (up from 1.0). All three constants live at
   the top of `frontend/scripts/generate-evidence.ts` for future tuning.

2. **Playwright viewport bumped to 1600x900** in the `scenarios` project
   (previously Desktop Chrome default, 1280x720). Video `size` is pinned to
   match. Screenshots/videos now have enough pixels to zoom into in the
   enlarged lightbox.

3. **Video playback speed control.** The old `<video controls>` on the
   detail page is replaced with a click-to-enlarge preview; the enlarged
   lightbox video has a native `<select>` speed control (0.25x, 0.5x, 1x,
   1.5x, 2x) driving `video.playbackRate`, plus a Download link. No
   external deps.

4. **Enlarged media lightbox.** A single unified lightbox now handles
   screenshots (with prev/next nav), GIFs, and videos. Sizing:
   `max-width: 95vw; max-height: 90vh; object-fit: contain`. Videos get
   `95vw` width and a toolbar for speed + download.

5. **Arrow-key beep fix.** `keydown` listener is attached to `document` in
   the capture phase and calls `preventDefault()` + `stopPropagation()` on
   `ArrowLeft/Right/Up/Down` and `Escape` whenever the lightbox is open —
   stops macOS Chrome/Safari from emitting the system beep that fires when
   arrows hit a focused button.

6. **Clickable previews on the detail page.** Screenshots preview (small
   filmstrip of the first five frames), flipbook GIF, motion GIF, and
   video thumbnail are themselves clickable. Screenshots preview routes to
   `#/scenario/<slug>/screenshots`; GIFs/video open in the lightbox. The
   redundant top "Screenshots / Flow / Play video / Motion GIF" pills were
   removed — interaction is now the preview itself.

7. **Per-view size control.** Gallery, Screenshots, and Flow pages all get
   a Small / Medium / Large toolbar bound to a CSS custom property
   `--tile-size` used by `grid-template-columns: repeat(auto-fill,
   minmax(var(--tile-size), 1fr))`. Choice persisted in `localStorage`
   (`evidence.tileSize`). Default = Medium (320px).

8. **Gallery view toggle (GIF cards / Screenshot strips).** New toolbar
   button switches the gallery between GIF-thumb cards and horizontal
   screenshot strips. Strip mode renders a scrolling row of every step's
   screenshot per scenario; clicking a frame opens the screenshots
   lightbox at that index. Persisted in `localStorage`
   (`evidence.galleryView`). Default = GIF cards.

### Files touched (round 3)
- `frontend/scripts/generate-evidence.ts` — tunable GIF constants, setpts
  slowdown for motion GIFs, log line now includes slowdown factor.
- `frontend/playwright.config.ts` — 1600x900 viewport + matching video size
  for the `scenarios` project.
- `frontend/src-evidence-gallery/viewer.js` — unified media lightbox,
  routing preserved, new toolbar with size + view-mode controls, strip
  view, clickable detail previews, keybeep fix.
- `frontend/src-evidence-gallery/viewer.css` — toolbar styles, strip/grid
  sizing via `--tile-size`, enlarged lightbox, video toolbar.
- `frontend/src-evidence-gallery/index.html` — lightbox container is now
  an empty focusable element populated by JS per-mode.
- `docs/tasks/scenario-tests-and-visualization/plan.md` — this section.

### Generator log sample (post-change)
```
[evidence] motion GIF scenario-create-ticket-and-change-status-...: 3 fps, 2x slowdown, source=2.52s, gif=5.00s
[evidence] flipbook GIF scenario-create-ticket-and-change-status-...: 5 fps, 8 steps × 1.5s, gif=5.80s
```

### Known non-goals (round 3)
- Lightbox still does not preload neighbouring screenshots.
- Strip-view horizontal scroll uses default browser scrollbar; no custom
  affordance.
- Size control has three presets rather than a continuous slider.

## 9. Sign-off

- [ ] User approved plan — date/note
- [ ] Frontend implementation complete (scenarios project green under `npm run e2e`, smoketest passes, three shipped scenarios pass)
- [ ] Manual acceptance: `npm run evidence:generate` produces a working viewer at `frontend/evidence/gallery/index.html`
- [ ] `npm run lint && npm run typecheck && npm run e2e` — zero errors, zero warnings
- [ ] code-reviewer sign-off

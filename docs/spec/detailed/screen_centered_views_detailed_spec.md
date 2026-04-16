# Detailed Spec: Screen-Centered Views

**Feature**: Screen-Centered Views (dev dashboard "Screens" tab)
**Status**: ✅ Implemented
**Scope**: Dev tooling only — no backend changes, no production frontend changes.

---

## Overview

A new "Screens" tab in the dev dashboard (`#/screens`) that shows which frontend application routes are visited by scenario tests and which have no walkthrough coverage. The primary signal is the "Uncovered Screens" section: routes that no scenario ever visits.

Data flows entirely through the existing `frontend/walkthroughs/gallery/manifest.json`, extended to include the URL captured at each step.

---

## Requirements

### REQ-SCREENS-001: Capture URL per scenario step
**Status**: ✅

The scenario fixture (`frontend/e2e/helpers/scenario.ts`) must capture the current page URL after each step completes and include it in the step's metadata record.

**Acceptance criteria**:
- `ScenarioStepRecord` gains a `url: string` field.
- The captured URL is the value of `page.url()` immediately after `await base.step(name, fn)` returns (or on the error path, before re-throw).
- The URL is written into `frontend/walkthroughs/metadata/<slug>.json` as part of each step entry.
- Existing fields (`index`, `name`, `slug`, `screenshot`, `startedAt`, `durationMs`, `status`) are unchanged.

**Edge cases**:
- If `page.url()` throws (rare browser teardown race), the step record stores an empty string `""` rather than failing the step.

---

### REQ-SCREENS-002: URL flows through manifest schema
**Status**: ✅

The walkthrough generator (`frontend/scripts/generate-walkthroughs.ts`) and the dashboard's `ScenariosAspect` validator/types must forward the `url` field on each step so it is available to the new `screensAspect`.

**Acceptance criteria**:
- `ScenarioStep` in `tools/dev-dashboard/src/aspects/scenarios/types.ts` gains `url?: string`.
- The `validate()` function in `ScenariosAspect.tsx` reads and passes through `url` on each step (optional; absent in legacy artifacts).
- The real-schema regression test in `tests/unit/scenarios.realschema.test.ts` is updated to include `url` in the step fixture data and assert it is forwarded.
- The generator produces `url` in step entries when the metadata JSON contains it.

---

### REQ-SCREENS-003: Screens aspect — route normalization
**Status**: ✅

The screens aspect must normalize concrete URLs to route pattern strings matching the frontend app's route definitions.

**Known route patterns** (from `frontend/src/App.tsx`):
- `/login`
- `/projects`
- `/projects/:projectId`
- `/tickets/:ticketId`
- `/epics/:epicId`
- `/users`
- `/organizations`

**Acceptance criteria**:
- `normalizeUrl(url: string): string | null` strips the origin and query string, then replaces path segments that look like IDs (UUIDs, numeric ids, or any non-slug token matching `[a-f0-9-]{8,}` or purely numeric) with the appropriate `:param` token.
- URLs that match no known route pattern return the raw pathname (not null) so unknown screens are surfaced rather than silently dropped.
- An empty string or non-HTTP url returns `null`.
- The normalization function is pure and exported from its own module for isolated testing.

---

### REQ-SCREENS-004: Screens aspect — index inversion
**Status**: ✅

The screens aspect must build a reverse index: for each route pattern, the list of (scenario id, scenario title, step index, step label, step screenshot) tuples that visited it.

**Acceptance criteria**:
- Function `buildScreenIndex(scenarios: ScenarioEntry[]): ScreenIndex` produces a `Map<routePattern, ScreenVisit[]>`.
- Each `ScreenVisit` records: `scenarioId`, `scenarioTitle`, `stepIndex`, `stepLabel`, `screenshot?`, `url` (original).
- Steps with missing or empty `url` are silently skipped (backward compat with pre-REQ-SCREENS-001 manifests).
- The same scenario step visiting the same route pattern appears only once in that route's list.

---

### REQ-SCREENS-005: Screens aspect — uncovered screens detection
**Status**: ✅

The screens aspect must compute which known routes have zero scenario coverage.

**Acceptance criteria**:
- `uncoveredScreens(index: ScreenIndex, knownRoutes: string[]): string[]` returns the subset of `knownRoutes` not present as keys in `index`.
- The known routes list is the static list from REQ-SCREENS-003.
- Result is sorted alphabetically.

---

### REQ-SCREENS-006: Screens index view
**Status**: ✅

The dashboard `#/screens` route renders an index view listing all visited route patterns as cards, plus a distinct "Uncovered Screens" section.

**Acceptance criteria**:
- Each covered screen card shows: route pattern, count of scenario visits, thumbnail of the first screenshot from any visiting step.
- The uncovered screens section shows one entry per uncovered route pattern. If all known routes are covered the section is hidden.
- The page renders without error when the manifest contains steps with no `url` (backward compat).

---

### REQ-SCREENS-007: Screen detail view
**Status**: ✅

Clicking a covered screen card navigates to a detail view (`#/screens/<encoded-route>`) showing all scenario visits to that screen.

**Acceptance criteria**:
- Each visit row shows: scenario title, step label, step index, thumbnail screenshot (if available), and a deep-link to the scenario detail view (`#/scenarios/<scenarioId>`).
- The detail view has a back-link to the index (`#/screens`).

---

### REQ-SCREENS-008: Screens aspect registered in dashboard
**Status**: ✅

The screens aspect is registered in `tools/dev-dashboard/src/aspects/index.ts` and appears as a tab in the navigation rail.

**Acceptance criteria**:
- A `rail-screens` navigation item is visible when the dashboard loads.
- Clicking it renders the screens panel (with empty state if manifest is missing).
- The aspect reuses the same `manifest.json` artifact and refresh command as `scenariosAspect` — no new artifact files.
- `aspects.config.mjs` does NOT need a new entry (no new staleness source roots; screens share scenarios' source root and artifact).

---

### REQ-SCREENS-009: Smoke test coverage
**Status**: ✅

The dashboard smoke tests verify that the screens tab boots and renders basic structure.

**Acceptance criteria**:
- `rail-screens` is present in the `dashboard_boots_and_shows_four_aspect_tabs` smoke test.
- A smoke test verifies the screens panel renders the index view (covered + uncovered sections) from the fixture manifest (once the fixture manifest is updated to include `url` fields on steps).

---

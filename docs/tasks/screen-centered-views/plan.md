# Feature Plan: Screen-Centered Views

**Status**: ✅ Done
**Date**: 2026-04-15
**Stack**: Frontend (dev tooling only — no backend changes, no production frontend changes)
**Detailed spec**: docs/spec/detailed/screen_centered_views_detailed_spec.md

---

## 1. Requirements in scope

- **REQ-SCREENS-001**: Capture URL per scenario step — add `url: string` to `ScenarioStepRecord` and capture `page.url()` after each step.
- **REQ-SCREENS-002**: URL flows through manifest schema — extend `ScenarioStep` in the dashboard types and thread `url` through the `validate()` function.
- **REQ-SCREENS-003**: Route normalization — pure `normalizeUrl` function that maps concrete URLs to route pattern strings.
- **REQ-SCREENS-004**: Screen index inversion — `buildScreenIndex` that inverts scenarios→steps into screen→visits.
- **REQ-SCREENS-005**: Uncovered screens detection — `uncoveredScreens` that identifies known routes with zero visits.
- **REQ-SCREENS-006**: Screens index view — `#/screens` panel with covered-screen cards and an uncovered-screens section.
- **REQ-SCREENS-007**: Screen detail view — `#/screens/<encoded-route>` listing all visits with deep-links into the scenarios tab.
- **REQ-SCREENS-008**: Aspect registered in dashboard — `screensAspect` in `aspects/index.ts`, `rail-screens` tab visible.
- **REQ-SCREENS-009**: Smoke test coverage — updated smoke test counting four tabs; new smoke for screens panel.

---

## 2. Out of scope

- Any changes to the production frontend application (`frontend/src/`).
- Any backend changes.
- A new `aspects.config.mjs` entry for screens (screens reuse the scenarios artifact; no new source roots or staleness tracking needed).
- Persisting screen-coverage data to a separate artifact file.
- CI integration of the walkthrough generator.
- Tracking which screens a scenario visits across multiple runs (latest run wins; history is not stored).
- Normalization of query-string parameters (stripped entirely).
- Deep-linking to a specific step within the scenario detail view (link is to the scenario detail root).
- Mobile/responsive layout for the screens tab.
- Filtering/searching within the screens index view.

---

## 3. Architecture

### No backend changes.

### Change 1: Scenario fixture — capture URL (`frontend/`)

**File**: `frontend/e2e/helpers/scenario.ts`

- `ScenarioStepRecord`: add `url: string`.
- `StepCollector.run()`: after `await base.step(name, fn)` returns (both success and error paths), capture `url = page.url()` inside a try/catch that falls back to `""`. Assign to the step record push on both paths.

No other files in `frontend/e2e/` change.

---

### Change 2: Dashboard — extend scenario types (`tools/dev-dashboard/`)

**File**: `tools/dev-dashboard/src/aspects/scenarios/types.ts`

- `ScenarioStep`: add `url?: string`.

**File**: `tools/dev-dashboard/src/aspects/scenarios/ScenariosAspect.tsx`

- In the step-mapping block inside `validate()`, read `url: typeof s.url === 'string' ? s.url : undefined` and include it in the returned step object.

**File**: `tools/dev-dashboard/tests/unit/scenarios.realschema.test.ts`

- Update both step fixture entries to include `url: 'http://localhost:5173/projects'` (any plausible URL).
- Add one assertion: `steps[0]!.url` equals the value from the fixture.
- The existing assertions must remain intact and green.

**File**: `tools/dev-dashboard/tests/fixtures/scenarios/manifest.json`

- Add `"url": "http://localhost:5173/organizations"` to each step that should appear in covered-screens fixture tests. Specifically:
  - `org-create` step 1: `/login`, step 2: `/organizations`, step 3: `/organizations`
  - `project-create` step 1: `/organizations`, step 2: `/projects/<uuid>`
  - `member-invite` step 1 (no url — leave absent to test backward compat)

---

### Change 3: Dashboard — screens aspect (`tools/dev-dashboard/`)

#### New files under `tools/dev-dashboard/src/aspects/screens/`

**`normalizeUrl.ts`** — pure utility

```
export const KNOWN_ROUTES: string[] = [
  '/login',
  '/projects',
  '/projects/:projectId',
  '/tickets/:ticketId',
  '/epics/:epicId',
  '/users',
  '/organizations',
];

export function normalizeUrl(url: string): string | null
```

Algorithm:
1. If `url` is empty return `null`.
2. Parse with `new URL(url)` — if it throws (non-absolute URL with no origin) attempt treating as absolute with a dummy base; extract `pathname` only. If still unparseable return `null`.
3. Strip trailing slash (unless pathname is `/`).
4. For each path segment, if the segment matches `/^[0-9a-f]{8}-[0-9a-f]{4}-/i` (UUID prefix) OR `/^\d+$/` (purely numeric), replace it with the corresponding `:param` token by trying each `KNOWN_ROUTES` pattern in order. The first pattern whose static segments match and whose param slots align wins.
5. If no known route matches, return the raw (possibly ID-containing) pathname — do not return `null`. This surfaces unknown screens.

The replacement logic works by: for each `KNOWN_ROUTE`, split by `/` and compare with the actual pathname segments — if lengths match and all literal segments match, return the route pattern.

**`screenIndex.ts`** — grouping/inversion logic

```ts
export interface ScreenVisit {
  scenarioId: string;
  scenarioTitle: string;
  stepIndex: number;
  stepLabel: string;
  screenshot?: string;
  url: string;
}

export type ScreenIndex = Map<string, ScreenVisit[]>;

export function buildScreenIndex(scenarios: ScenarioEntry[]): ScreenIndex

export function uncoveredScreens(index: ScreenIndex, knownRoutes: string[]): string[]
```

`buildScreenIndex` rules:
- For each scenario, for each step that has a non-empty `url`, call `normalizeUrl(step.url)`. If the result is non-null, push a `ScreenVisit` into `index.get(pattern)` (create array if absent).
- Deduplication within the same pattern+scenario+step triple is applied (same `scenarioId` + `stepIndex` seen twice is only added once — shouldn't happen in practice but guard it).
- Steps with missing/empty `url` are skipped silently.

**`ScreensAspect.tsx`** — Aspect<ScenariosManifest> implementation

- `id: 'screens'`
- `title: 'Screens'`
- `sourceRoots: ['frontend/e2e/scenarios']` (same as scenarios)
- `artifacts`: same single entry as `scenariosAspect` — `{ url: '/artifacts/scenarios/manifest.json', ... }`
- `refreshCommand` / `refreshCwd` / `refreshDescription`: identical to `scenariosAspect` (same artifact, same generator command)
- `load()`: fetches `manifest.json`, calls `validate()` (imported from `ScenariosAspect.tsx`), returns the `ScenariosManifest`.
- `render(data)`: calls `buildScreenIndex` and `uncoveredScreens`, renders the index view or routes to detail view based on URL hash.
- `suppressRefresh(hash)`: returns `true` when hash starts with `#/screens/` (detail view) — same pattern as `scenariosAspect` detail suppression.

**`ScreensIndexView.tsx`** — renders the `#/screens` index

- Covered screens section: one card per `ScreenIndex` key, showing route pattern, visit count, and first available thumbnail.
- Uncovered screens section: shown only if `uncoveredScreens(...)` is non-empty; each entry is a row with the route pattern.
- Each covered card has `data-testid="screen-card-<slugified-route>"`.
- The uncovered section container has `data-testid="uncovered-screens"`.
- Clicking a card updates the hash to `#/screens/<encodeURIComponent(routePattern)>`.

**`ScreenDetailView.tsx`** — renders `#/screens/<pattern>`

- Shows the decoded route pattern as the heading.
- Lists all `ScreenVisit[]` for that pattern: thumbnail (if available), scenario title, step label (step N), and a link to `#/scenarios/<scenarioId>`.
- Back-link to `#/screens` with `data-testid="screens-back"`.
- Container `data-testid="screen-detail"`.

#### Updated files

**`tools/dev-dashboard/src/aspects/index.ts`**

Add import and registration of `screensAspect` after `scenariosAspect`.

**`tools/dev-dashboard/tests/smoke/dashboard.smoke.spec.ts`**

- Update `dashboard_boots_and_shows_three_aspect_tabs` → `dashboard_boots_and_shows_four_aspect_tabs`: add assertion for `rail-screens`.
- Update `clicking_each_aspect_tab_renders_its_panel_header`: add `'screens'` to the loop.
- Add new smoke test `screens_panel_renders_index_with_covered_and_uncovered_sections`.

**`tools/dev-dashboard/tests/smoke/fixtures.ts`**

- `AspectId` union: add `'screens'`.

---

## 4. Test matrix

### 4.1 Scenario fixture tests
No dedicated test file for the fixture — covered by the existing E2E scenario tests. The realschema regression test (§4.4) covers the schema change. The scenario fixture change is validated by running `npm run e2e:scenarios` as part of full validation.

### 4.2 Dashboard unit tests

#### `tools/dev-dashboard/tests/unit/screens.normalizeUrl.test.ts`

| Test name | Verifies |
|---|---|
| `normalizeUrl_returns_null_for_empty_string` | Empty string input returns `null` |
| `normalizeUrl_returns_null_for_non_url_string` | Non-URL (e.g. `"not-a-url"`) with no parseable pathname returns `null` |
| `normalizeUrl_strips_origin_and_returns_static_route` | `http://localhost:5173/login` → `/login` |
| `normalizeUrl_strips_origin_and_returns_static_route_projects` | `http://localhost:5173/projects` → `/projects` |
| `normalizeUrl_strips_origin_and_returns_static_route_users` | `http://localhost:5173/users` → `/users` |
| `normalizeUrl_strips_origin_and_returns_static_route_organizations` | `http://localhost:5173/organizations` → `/organizations` |
| `normalizeUrl_normalizes_uuid_project_id_to_pattern` | `http://localhost:5173/projects/a1b2c3d4-e5f6-...` → `/projects/:projectId` |
| `normalizeUrl_normalizes_uuid_ticket_id_to_pattern` | `http://localhost:5173/tickets/00000000-0000-0000-0000-000000000001` → `/tickets/:ticketId` |
| `normalizeUrl_normalizes_uuid_epic_id_to_pattern` | `http://localhost:5173/epics/12345678-1234-1234-1234-123456789abc` → `/epics/:epicId` |
| `normalizeUrl_normalizes_numeric_id_to_pattern` | `http://localhost:5173/projects/42` → `/projects/:projectId` |
| `normalizeUrl_strips_trailing_slash_before_matching` | `http://localhost:5173/projects/` → `/projects` |
| `normalizeUrl_strips_query_string_before_matching` | `http://localhost:5173/projects?foo=bar` → `/projects` |
| `normalizeUrl_strips_hash_fragment_before_matching` | `http://localhost:5173/projects#section` → `/projects` |
| `normalizeUrl_returns_raw_pathname_for_unknown_route` | `/unknown/path/here` is returned as-is (not null) |
| `normalizeUrl_handles_root_path` | `http://localhost:5173/` → `/` (no match but not null) |

#### `tools/dev-dashboard/tests/unit/screens.buildScreenIndex.test.ts`

| Test name | Verifies |
|---|---|
| `buildScreenIndex_returns_empty_map_for_empty_scenarios_array` | Zero scenarios produces empty Map |
| `buildScreenIndex_returns_empty_map_when_all_steps_have_no_url` | Scenarios with steps lacking `url` are silently skipped |
| `buildScreenIndex_indexes_single_scenario_single_step` | One scenario, one step → index has one pattern key with one visit |
| `buildScreenIndex_visit_contains_scenarioId_title_stepIndex_stepLabel_screenshot_url` | All ScreenVisit fields are populated correctly |
| `buildScreenIndex_multiple_steps_same_scenario_same_route_deduplicates` | Two steps in the same scenario hitting the same pattern → only one visit entry per step (they share pattern but distinct stepIndex so both appear; deduplication is same scenario+step, not same scenario) |
| `buildScreenIndex_two_scenarios_same_route_both_appear` | Both scenarios appear as visits under the same pattern |
| `buildScreenIndex_two_scenarios_different_routes_each_indexed_separately` | Each pattern gets its own entry |
| `buildScreenIndex_step_with_empty_string_url_is_skipped` | `url: ""` step not indexed |
| `buildScreenIndex_normalizes_uuid_urls_to_patterns` | `/projects/<uuid>` steps land under `/projects/:projectId` |
| `buildScreenIndex_step_screenshot_optional_when_absent` | Steps without screenshot produce ScreenVisit with `screenshot: undefined` |
| `uncoveredScreens_returns_all_known_routes_when_index_is_empty` | All known routes uncovered when map is empty |
| `uncoveredScreens_returns_empty_array_when_all_routes_are_covered` | All routes present in index → empty result |
| `uncoveredScreens_returns_only_routes_absent_from_index` | Partial coverage — only missing routes returned |
| `uncoveredScreens_result_is_sorted_alphabetically` | Multiple uncovered routes returned in sorted order |
| `uncoveredScreens_unknown_routes_in_index_do_not_affect_result` | Extra keys in index (routes not in knownRoutes) don't affect the output |

### 4.3 Dashboard real-schema regression tests (updates to existing file)

**File**: `tools/dev-dashboard/tests/unit/scenarios.realschema.test.ts`

| Test name | Verifies | Change |
|---|---|---|
| `maps step.name → step.label and keeps step.screenshot` (existing) | Existing behavior still passes | Update fixture to add `url` to step entries — test still passes |
| `step.url_is_forwarded_when_present_in_manifest` | `steps[0]!.url` equals the URL from the fixture step | **New assertion** within the existing describe block, or a new `it()` |
| `step.url_is_undefined_when_absent_from_manifest` | Legacy manifest (no `url` on step) → `step.url` is `undefined` | **New test** using the internal-shape fixture that has no `url` |

### 4.4 Smoke tests (updates + new tests)

**File**: `tools/dev-dashboard/tests/smoke/dashboard.smoke.spec.ts`

| Test name | Verifies | Change type |
|---|---|---|
| `dashboard_boots_and_shows_four_aspect_tabs` | `rail-screens` is visible alongside the other three tabs | Rename + extend existing `..._three_aspect_tabs` |
| `clicking_each_aspect_tab_renders_its_panel_header` | Screens panel boots without console errors | Add `'screens'` to existing loop |
| `screens_panel_renders_index_with_covered_and_uncovered_sections` | Covered screen cards and uncovered section are visible from fixture manifest | **New** |
| `screens_panel_shows_empty_state_when_manifest_missing` | Same empty-state UX as scenarios tab when artifact absent | **New** |
| `screens_card_click_opens_detail_view` | Clicking a covered screen card renders `screen-detail` with visits | **New** |

### 4.5 Property-based tests

Not applicable for this feature. The normalization function has a small, well-defined input space tested exhaustively in unit tests. The index/inversion logic is purely structural with no numeric or combinatorial invariants warranting Hypothesis strategies.

### 4.6 Scenario test for the screens tab

The screens feature is a developer dashboard tab, not a user-facing application feature. Per `docs/architecture/principles.md` and `docs/testing/scenario_walkthroughs.md`, scenario tests cover user-facing features. The dev dashboard is dev tooling. **No scenario test is required for the screens tab itself.**

The existing scenario tests (create-project, org-create, etc.) serve as indirect integration tests: once `url` is captured, regenerating the manifest and browsing the screens tab validates the full pipeline.

---

## 5. Test fixtures and helpers

### Existing fixtures modified

**`tools/dev-dashboard/tests/fixtures/scenarios/manifest.json`**

Add `url` to step entries to enable screens tests that need route coverage data:

- `org-create` scenario:
  - step 1 (Open signup): `"url": "http://localhost:5173/login"`
  - step 2 (Fill form): `"url": "http://localhost:5173/organizations"`
  - step 3 (Submit): `"url": "http://localhost:5173/organizations"`
- `project-create` scenario:
  - step 1 (Open org): `"url": "http://localhost:5173/organizations"`
  - step 2 (Create project): `"url": "http://localhost:5173/projects/a1b2c3d4-e5f6-7890-abcd-ef1234567890"`
- `member-invite` scenario:
  - step 1 (Invite): no `url` field — left absent deliberately to test backward compat

With this fixture: `/login` (1 visit), `/organizations` (3 visits), `/projects/:projectId` (1 visit) are covered. Uncovered routes from the known list: `/projects`, `/tickets/:ticketId`, `/epics/:epicId`, `/users`.

### New test data requirements

- `scenarios.realschema.test.ts` inline fixture: add `"url": "http://localhost:5173/projects"` to both step entries in the existing inline manifest object.

### No new conftest/helper files needed

This is entirely dashboard-side TypeScript. No Python fixtures.

---

## 6. Edge cases covered

| Edge case | Where handled |
|---|---|
| Step has no `url` field (legacy manifest written before this change) | `buildScreenIndex` skips steps with missing/empty `url`; dashboard renders without error |
| `page.url()` throws during step capture | try/catch in `StepCollector.run()` falls back to `""` |
| URL with query string | `normalizeUrl` strips query string before matching |
| URL with hash fragment | `normalizeUrl` strips hash fragment (`pathname` from URL API excludes it) |
| Trailing slash in URL | `normalizeUrl` strips trailing slash before pattern matching |
| All known routes covered | Uncovered section is hidden (not rendered) |
| No scenarios in manifest | Both index and uncovered sections render correctly with an empty covered set and all routes listed as uncovered |
| Unknown route visited by a scenario | `normalizeUrl` returns the raw pathname; it appears in the index under its literal key but does not appear in the uncovered routes list (which is computed only against `KNOWN_ROUTES`) |
| Scenario steps visiting the same route multiple times | Both steps appear as separate visits (distinct `stepIndex`); no deduplication across steps |
| Manifest missing entirely (artifact absent) | `load()` throws; aspect renders the standard empty-state component |
| Route pattern `/` (root redirect) | `normalizeUrl` returns `/`; it is not in `KNOWN_ROUTES` so it won't appear as uncovered; it will appear in the unknown bucket in the index |

---

## 7. Implementation order

1. **Update fixture manifest** (`tools/dev-dashboard/tests/fixtures/scenarios/manifest.json`) — add `url` to step entries. This unblocks all downstream dashboard tests.

2. **Extend scenario step schema** (`tools/dev-dashboard/src/aspects/scenarios/types.ts`, `ScenariosAspect.tsx`) — add `url?: string` to `ScenarioStep`, thread it through `validate()`.

3. **Update real-schema regression test** (`tests/unit/scenarios.realschema.test.ts`) — add `url` to inline fixtures and the two new assertions. Run: `npm --prefix tools/dev-dashboard run test -- --run`. Must be green before proceeding.

4. **Implement `normalizeUrl.ts`** — pure function, no dependencies.

5. **Write `screens.normalizeUrl.test.ts`** — all 15 unit tests. Run and confirm green.

6. **Implement `screenIndex.ts`** — `buildScreenIndex` and `uncoveredScreens`.

7. **Write `screens.buildScreenIndex.test.ts`** — all 15 unit tests. Run and confirm green.

8. **Implement `ScreensIndexView.tsx` and `ScreenDetailView.tsx`** — UI components.

9. **Implement `ScreensAspect.tsx`** — wires load/render/routing.

10. **Register in `aspects/index.ts`**.

11. **Update smoke tests** — rename existing three-tabs test, add `'screens'` to the loop, add three new smoke tests. Update `fixtures.ts` `AspectId` union.

12. **Update scenario fixture** (`frontend/e2e/helpers/scenario.ts`) — add `url: string` to `ScenarioStepRecord`, capture in `StepCollector.run()`.

13. **Run full dashboard validation**: `npm --prefix tools/dev-dashboard run typecheck && npm --prefix tools/dev-dashboard run lint && npm --prefix tools/dev-dashboard run test -- --run && npm --prefix tools/dev-dashboard run smoke`

14. **Run frontend validation**: `npm run lint && npm run typecheck` (in `frontend/`) to verify scenario.ts change passes strict TS.

15. **Run `npm run e2e:scenarios`** from the `frontend/` directory to confirm scenario fixture change does not break existing scenario tests.

---

## 8. Risks / open questions

- **URL timing**: `page.url()` after `await base.step(name, fn)` captures the URL at the end of the step action. If the step navigates and the navigation is not yet reflected (e.g. client-side routing that's still animating), the URL may be the pre-navigation URL. The screenshot is also taken at this point, so the screenshot and URL will be consistent with each other. If this is a problem in practice, the implementer should note it and capture URL before the screenshot, not after. This does not require a plan revision unless it causes test failures.
- **Dashboard `suppressRefresh` for screens detail view**: the pattern mirrors `scenariosAspect`. If `parseScenariosHash` or the hash routing utilities are factored differently in the future, this may need revisiting. For now, implement it inline in `ScreensAspect.tsx`.
- **`aspects.config.mjs` staleness**: screens share the scenarios artifact. The staleness indicator for the screens tab will therefore show the same staleness state as the scenarios tab (stale when scenario source files are newer than `manifest.json`). This is correct behavior and requires no change to `aspects.config.mjs`.
- **Smoke test fixture coverage**: the fixture manifest after adding `url` covers `/login`, `/organizations`, and `/projects/:projectId` as covered screens, and leaves `/projects`, `/tickets/:ticketId`, `/epics/:epicId`, `/users` uncovered. The smoke tests must assert against these specific values to be meaningful.

---

## 9. Sign-off

- [x] User approved plan — 2026-04-15
- [x] Dashboard unit tests written and green
- [x] Dashboard smoke tests written and green
- [x] Scenario fixture updated and `npm run e2e:scenarios` green
- [x] Full validation suites green (dashboard + frontend)
- [x] code-reviewer sign-off

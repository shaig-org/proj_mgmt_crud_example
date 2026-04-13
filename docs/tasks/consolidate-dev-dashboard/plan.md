# Feature Plan: Consolidate Dev Dashboard

**Status**: 🟡 Draft
**Date**: 2026-04-13
**Stack**: Tooling (standalone static site under `tools/dev-dashboard/`). No product backend or product frontend changes.
**Detailed spec**: _N/A — internal developer tooling consolidation. Scope captured in this plan; supersedes parts of `docs/testing/scenario_walkthroughs.md` (scenarios viewer host) and `backend/evidence/capabilities/README.md` (capabilities viewer host)._

---

## 1. Requirements in scope

This is a tooling change without product REQ-IDs. The acceptance criteria are:

- **AC-DD-001**: A single command (`npm run dashboard`, run from `tools/dev-dashboard/`) launches one local dashboard that exposes three aspect tabs: Scenarios, Capabilities, Traces.
- **AC-DD-002**: Each aspect panel shows: title, last-generated timestamp of its primary artifact, a stale indicator when source files are newer than the artifact, and a copy-paste refresh command with the cwd it must run from.
- **AC-DD-003**: The Scenarios tab reproduces the visual experience of today's `frontend/src-walkthroughs-dashboard/` (filter sidebar, cards with hover-play GIF, detail view with video + steps + correlation ID).
- **AC-DD-004**: The Capabilities tab reads `backend/evidence/capabilities/baseline.json` and `report.json` and renders a route table with status (unchanged/expanded/reduced/new/removed) and a baseline-vs-current diff toggle.
- **AC-DD-005**: The Traces tab lists scenarios that have artifacts under `backend/.trace-artifacts/<scenario>/`, and per-scenario shows the rendered mermaid sequence diagram, an embedded `flame.html` iframe, and folded-stacks (collapsed by default).
- **AC-DD-006**: First-run / empty state: when an artifact is missing, the panel shows the refresh command and a friendly "not generated yet" message — never a blank screen or a stack trace.
- **AC-DD-007**: Adding a new aspect (e.g. static analysis) is a single new directory under `src/aspects/<aspect>/` plus one entry in the registry. The contract is documented and stable.
- **AC-DD-008**: The dashboard never calls the product FastAPI backend. View-only.

## 2. Out of scope

Deferred to v2 (call out in UI where relevant):

- Refresh-trigger server (clicking a button to spawn the refresh command).
- Dark mode.
- Per-entity cross-aspect view (e.g. one page per route showing scenarios + traces + capabilities at once).
- Real `.trace-index` (SQLite or custom-format) parsing inside the JS dashboard. v1 reads the per-scenario artifact dirs only.
- Scenario ↔ capability cross-linking (requires a join key that does not yet exist).
- History of capability diffs over time.
- Hosting the dashboard as a route in the product SPA, or serving it through FastAPI. Both explicitly rejected.
- Authentication of the dashboard (it is local-only and binds to localhost).
- Mobile / small-screen layouts.

## 3. Architecture

### 3.1 Hosting and runtime

Standalone Vite + React + TypeScript app at `tools/dev-dashboard/`. Launched by `npm run dashboard` from that directory; binds to `127.0.0.1` on a fixed port (proposed `5179`, chosen to avoid clashing with the product Vite dev server `5173`, the product preview `4173`, and Playwright report ports).

Vite serves the dashboard's own `src/` and exposes selected repo paths as static assets via `server.fs.allow` plus a tiny custom plugin that mounts read-only routes:

| URL prefix (dev server) | Filesystem path |
|---|---|
| `/artifacts/scenarios/` | `<repo>/frontend/walkthroughs/gallery/` |
| `/artifacts/capabilities/` | `<repo>/backend/evidence/capabilities/` |
| `/artifacts/traces/` | `<repo>/backend/.trace-artifacts/` |
| `/artifacts/staleness.json` | `<repo>/tools/dev-dashboard/.staleness.json` |

Reads only — the plugin refuses any non-GET request.

### 3.2 Why Vite + React (vs vanilla)

Picked: **Vite + React + TypeScript**. Reasons:

- The team already maintains Vite + React + TS in `frontend/`. Zero new tools to learn or pin.
- Aspect plugin model maps cleanly to React components and lazy `import()` for code-splitting per aspect.
- TypeScript gives us a checked `Aspect` interface, which directly enforces the "easy to add a new angle" goal (AC-DD-007).
- Inline mermaid rendering and iframe embedding are easier with a component model than with hand-rolled DOM.
- Vanilla matches the existing `backend/evidence/capabilities/index.html` style and is smaller, but every additional aspect (Traces especially) pushes vanilla toward ad-hoc DOM patches. The growth axis (more aspects) tilts the choice to React.

Cost: a `node_modules` and a build step in `tools/dev-dashboard/`. Acceptable; this directory is dev-only.

### 3.3 Project structure

```
tools/dev-dashboard/
  package.json
  vite.config.ts
  tsconfig.json
  index.html
  README.md
  scripts/
    check-staleness.mjs        # writes .staleness.json
  src/
    main.tsx
    App.tsx
    aspects/
      index.ts                 # registry: Aspect[]
      scenarios/
        ScenariosAspect.tsx
        CardGrid.tsx
        DetailView.tsx
        types.ts
      capabilities/
        CapabilitiesAspect.tsx
        RouteTable.tsx
        DiffToggle.tsx
        types.ts
      traces/
        TracesAspect.tsx
        ScenarioList.tsx
        MermaidView.tsx
        FlameFrame.tsx
        types.ts
    components/
      AspectShell.tsx          # header + last-generated + stale + refresh-command
      StaleBadge.tsx
      CommandBlock.tsx         # copy-to-clipboard
      LeftRail.tsx
      TopBar.tsx
      EmptyState.tsx
    lib/
      loadArtifact.ts          # fetch JSON / HTML w/ mtime
      staleness.ts             # consume .staleness.json
      registry.ts              # iterate aspects, resolve current
      clipboard.ts
    styles/
      tokens.css
      layout.css
  tests/
    unit/
      staleness.test.ts
      loadArtifact.test.ts
      registry.test.ts
    smoke/
      dashboard.smoke.spec.ts  # Playwright
```

### 3.4 Aspect plugin contract

The single extension point. Lives at `src/aspects/index.ts`.

```ts
// src/aspects/types.ts
export interface ArtifactRef {
  /** URL the dashboard fetches (relative to dev server root). */
  url: string;
  /** Human label, e.g. "manifest.json". */
  label: string;
  /** Repo-relative path, shown in UI for orientation. */
  repoPath: string;
}

export interface Aspect<TData = unknown> {
  /** Stable kebab-case id; used in URL hash (#/scenarios). */
  id: string;
  /** Tab label. */
  title: string;
  /** Inline SVG component or emoji string for the left-rail icon. */
  icon: React.ReactNode;
  /** Repo-relative directories whose mtimes determine staleness. */
  sourceRoots: string[];
  /** Artifacts this aspect consumes. First entry is the "primary"
   *  artifact whose mtime drives the last-generated timestamp. */
  artifacts: ArtifactRef[];
  /** Copy-pasteable command that regenerates the artifacts. */
  refreshCommand: string;
  /** Repo-relative cwd where refreshCommand must run. */
  refreshCwd: string;
  /** One-line description shown above the command block. */
  refreshDescription: string;
  /** Loader: fetches and parses the artifacts. Throws on missing. */
  load: () => Promise<TData>;
  /** Renderer: receives loaded data; never receives loader errors —
   *  AspectShell handles error/empty states uniformly. */
  render: (data: TData) => React.ReactNode;
}
```

Registry:

```ts
// src/aspects/index.ts
import { scenariosAspect } from './scenarios/ScenariosAspect';
import { capabilitiesAspect } from './capabilities/CapabilitiesAspect';
import { tracesAspect } from './traces/TracesAspect';

export const aspects: Aspect[] = [
  scenariosAspect,
  capabilitiesAspect,
  tracesAspect,
];
```

Adding an aspect = create `src/aspects/<id>/`, export an `Aspect`, append to the array. No other file changes.

### 3.5 Staleness detection

A small Node script `tools/dev-dashboard/scripts/check-staleness.mjs`:

1. Walks each aspect's `sourceRoots` (recursively, ignoring `node_modules`, `.git`, `dist`, `__pycache__`, `.trace-index`).
2. Records the max mtime across source files.
3. Stats each aspect's primary artifact and records its mtime (or `null` if missing).
4. Writes `tools/dev-dashboard/.staleness.json`:

```json
{
  "generatedAt": "2026-04-13T10:22:33Z",
  "aspects": {
    "scenarios": {
      "primaryArtifactMtime": "2026-04-12T08:00:00Z",
      "primaryArtifactExists": true,
      "newestSourceMtime": "2026-04-13T09:14:00Z",
      "stale": true,
      "newestSourceFile": "frontend/e2e/scenarios/org_create.scenario.spec.ts"
    },
    "capabilities": { "...": "..." },
    "traces": { "...": "..." }
  }
}
```

The script knows which aspect ids and source roots exist via a small declarative `tools/dev-dashboard/scripts/aspects.config.mjs` that is the single source of truth shared with the TS registry (the TS aspects `import` it; the script `import`s it). This avoids duplicating source-root paths.

`npm run dashboard` runs `check-staleness` as a `predashboard` script, then starts Vite. Manual refresh: `npm run dashboard:check`.

`.staleness.json` is gitignored.

### 3.6 Migration of existing surfaces

| Surface | Action | Notes |
|---|---|---|
| `frontend/src-walkthroughs-dashboard/` (vanilla viewer on :4173) | Port logic into `src/aspects/scenarios/`, then **delete** the standalone directory in the same change. | No compat shim. The new dashboard fully replaces it. The `scripts/walkthroughs-*` npm scripts that boot the old viewer are removed; replaced by docs pointing to `npm run dashboard`. |
| `backend/evidence/capabilities/index.html` + `viewer.css` + `viewer.js` | Keep `analyze_capabilities.py` generating `report.json` (the dashboard reads JSON). HTML/CSS/JS generation made optional behind `--emit-html` flag, default off. | Follow-up — out of v1 scope to delete the HTML; we just stop generating it by default. The standalone viewer files in `backend/evidence/capabilities/` are removed once the dashboard ships and the README is updated. |
| `backend/.trace-artifacts/<scenario>/` | No change. Dashboard reads existing files. | The `trace` CLI continues to exist and is the recommended way to *generate* artifacts. |
| `docs/testing/scenario_walkthroughs.md` | Update "how to view" section to point at `npm run dashboard`. | Single doc edit. |
| `backend/evidence/capabilities/README.md` | Update viewer instructions to point at `npm run dashboard`. | Single doc edit. |

### 3.7 FE/BE contract

**None.** The dashboard never calls the product FastAPI backend. It reads files from disk via the Vite dev server only. This is a deliberate architectural choice and is part of AC-DD-008.

---

## Part 1 — UX

### Mental model

> "I'm picking an angle to view my project from."

The user opens the dashboard with a question, not a feature in mind. The left rail is a list of *angles* (Scenarios = "what does the user see?", Capabilities = "what is each route allowed to do?", Traces = "what code did this scenario touch?"). Tabs are nouns that name a way of looking at the codebase, not verbs that name actions.

A second mental beat: every angle has *artifacts* generated by some command. The dashboard is a viewer, not a generator. When something is stale, the dashboard tells the user the exact command to fix it and where to run it; the user runs it in their own terminal and reloads.

### Primary user journeys

1. **"I just changed a route handler — did I expand capabilities?"**
   - Open dashboard. Capabilities tab has a stale dot in the rail.
   - Click Capabilities. Stale badge in header tells the user: "1 source file newer than the report." Refresh command shown.
   - User runs the command in another terminal, reloads the dashboard, sees a green "fresh" badge and the route table with the changed handler highlighted (status: `expanded`).
   - Click the row → side panel shows added vs removed capabilities.

2. **"Show me the scenario walkthrough for the org-create flow."**
   - Open dashboard, click Scenarios (default landing tab).
   - Filter sidebar: type "org" → cards filter live.
   - Hover a card → GIF plays.
   - Click → detail view with embedded video, ordered step list with screenshots, correlation ID, and (if traces exist for the same scenario name) a "View trace" button that switches to the Traces tab pre-selected on that scenario.

3. **"Which tests cover this file?"**
   - Click Traces tab. Search box: "covering file path."
   - User pastes `backend/project_management_crud_example/routers/projects_api.py`.
   - List of scenarios filters to those whose `summary.json` references that file. (v1: client-side scan over loaded summaries; v2: real `.trace-index` query.)
   - Click a scenario → mermaid diagram + flame iframe.

4. **"Is anything stale?"**
   - At a glance: the top bar shows `3 aspects: 1 stale`. The left rail shows a small amber dot next to any stale aspect.
   - Clicking an aspect shows what makes it stale (newest source file path + its mtime, vs artifact mtime).

### First-run / empty state

When `.staleness.json` reports `primaryArtifactExists: false`, the panel renders:

- Friendly heading: "No `<aspect>` artifacts yet."
- One paragraph explaining what this aspect *would* show.
- The exact refresh command in a copy block.
- The cwd it must be run from, formatted as a monospace path.
- Where the artifact will land (the `repoPath` of the primary artifact).

No spinners, no error styling, no stack trace. The empty state is an invitation, not a failure.

### Stale state

Detected by the staleness script (§3.5): an aspect is stale iff `newestSourceMtime > primaryArtifactMtime`.

Presented as:

- Amber dot on the left-rail tab.
- Amber `Stale` badge in the panel header, next to the last-generated timestamp.
- Tooltip on the badge: "Newest source file: `frontend/e2e/scenarios/org_create.scenario.spec.ts` (2026-04-13 09:14, 1h 8m newer than artifact). Refresh: `npm run scenarios:capture` (cwd: `frontend/`)."
- The refresh command block is unchanged in position (header) — staleness only changes its color.

### Refresh-command surface

Every panel header has a `CommandBlock`:

```
┌─ Refresh command ─────────────────────────────────────────────┐
│ $ npm run scenarios:capture                                    │ [copy]
│ Run from: frontend/                                            │
│ Generates: frontend/walkthroughs/gallery/manifest.json + media │
│ What this does: re-runs scenario tests headed and captures     │
│  GIFs, screenshots, and step transcripts.                      │
└────────────────────────────────────────────────────────────────┘
```

The `copy` button copies only the command itself (not the surrounding text). The `cwd` line is informational.

### Cross-aspect links

v1 includes only links the data already supports:

- **Scenario card → Trace**: if `backend/.trace-artifacts/<scenario_id>/` exists, the scenario detail view shows a "View trace" button that switches tabs.
- **Trace scenario → Scenario card**: reciprocal link in the trace view, if a scenarios manifest entry shares the id.

Not in v1 (call out in UI as "future"):

- Capability row → scenarios that exercise that route. Requires per-scenario route-coverage data we do not generate today.

---

## Part 2 — UI

### 2.1 Layout

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Dev Dashboard    repo: ~/proj/.../main      3 aspects · 1 stale   ⟳  ?    │  ← TopBar
├──────────┬─────────────────────────────────────────────────────────────────┤
│ ▣ Scenarios│  Scenarios                                       last gen:    │
│ ● Capabili-│  ────────────────────────────────────────────  2026-04-12 08:00│
│   ties     │  [STALE] frontend/e2e/scenarios/org_create.scenario.spec.ts   │
│ ▣ Traces   │  newer than manifest by 1h 8m                                  │
│            │                                                                 │
│            │  Refresh:  $ npm run scenarios:capture          [copy]         │
│            │            cwd: frontend/                                       │
│            │  ┌──────────────────────────────────────────────────────────┐ │
│            │  │ Aspect-specific body                                      │ │
│            │  │ (cards / table / trace viewer)                            │ │
│            │  └──────────────────────────────────────────────────────────┘ │
│            │                                                                 │
└──────────┴─────────────────────────────────────────────────────────────────┘
```

Top bar:
- Left: dashboard title, repo absolute path (read from `import.meta.env.VITE_REPO_ROOT`, set by Vite plugin at boot).
- Right: aggregate freshness summary, manual reload-staleness button, help (`?`) opens an inline panel describing the aspect contract.

Left rail:
- Width 220px, fixed.
- Each entry: icon (24px) + label + amber dot if stale.
- Active tab has a left border accent.

Main area:
- Scrollable.
- Header section is `AspectShell` (constant across aspects).
- Body is the aspect's `render(data)`.

### 2.2 Per-aspect panel template (`AspectShell`)

```
<AspectShell aspect={a} state={state}>
  <Title>{a.title}</Title>
  <LastGenerated mtime={state.primaryArtifactMtime} />
  {state.stale && <StaleBadge reason={state.reason} />}
  <CommandBlock
    command={a.refreshCommand}
    cwd={a.refreshCwd}
    description={a.refreshDescription}
    output={a.artifacts[0].repoPath}
  />
  <Body>{children}</Body>
</AspectShell>
```

If `state.primaryArtifactExists === false`, the body is `<EmptyState aspect={a} />` regardless of what the aspect provides.

### 2.3 Scenarios panel

Ports `frontend/src-walkthroughs-dashboard/`:

```
┌─ AspectShell header ─┐
├──────────────────────┴──────────────────────────────────────────────────┐
│ Filters (sticky)     │  Scenario cards                                  │
│  Search: [_______]   │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐                │
│  Tag:                │  │ GIF │ │ GIF │ │ GIF │ │ GIF │                │
│   [x] auth           │  │     │ │     │ │     │ │     │                │
│   [ ] org            │  │title│ │title│ │title│ │title│                │
│   [ ] project        │  └─────┘ └─────┘ └─────┘ └─────┘                │
│  Status:             │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐                │
│   [x] passing        │  │ ... │ │     │ │     │ │     │                │
│   [ ] failing        │  └─────┘ └─────┘ └─────┘ └─────┘                │
└──────────────────────┴──────────────────────────────────────────────────┘
```

Card hover: GIF auto-plays. Click → detail:

```
┌────────────────────────────────────────────────────────────────────┐
│ ← back      Scenario: Create an organization (auth flow)           │
│                                                                      │
│ ┌──────── video ────────┐    Steps:                                  │
│ │                       │    1. Open /signup                         │
│ │   [▶ play]            │    2. Fill admin form                      │
│ │                       │    3. Submit                               │
│ └───────────────────────┘    4. Org appears in list                  │
│                                                                      │
│ Correlation ID: 7f31...    [View trace →]  (only if trace exists)    │
└────────────────────────────────────────────────────────────────────┘
```

### 2.4 Capabilities panel

```
┌─ AspectShell header ─┐
├──────────────────────┴──────────────────────────────────────────────────────┐
│ Filter: [all ▾] [unchanged] [expanded] [reduced] [new] [removed]            │
│ Diff: ( ) baseline  (•) current  ( ) diff                                    │
│                                                                              │
│  Method  Path                          Handler              Capabilities    │
│  ─────── ─────────────────────────── ─────────────────── ────────────────── │
│  POST    /api/projects                 create_project       project:write    │
│  GET     /api/projects/{id}            get_project          project:read     │
│  PUT     /api/projects/{id}    [⚠ EXP] update_project       project:write,   │
│                                                              org:read (NEW)  │
│  ...                                                                         │
└──────────────────────────────────────────────────────────────────────────────┘
```

- Color: `unchanged` neutral, `expanded` amber, `reduced` blue, `new` green, `removed` strikethrough red.
- Click a row → side panel: capability list with per-cap source-of-truth (link to `baseline.json#L<line>` opened via the Vite static mount).
- "Diff" toggle re-renders the table from the symmetric difference of `baseline.json` and `report.json`.

### 2.5 Traces panel

```
┌─ AspectShell header ─┐
├──────────────────────┴──────────────────────────────────────────────────────┐
│  Scenarios with traces                Mermaid sequence (selected)           │
│  ┌──────────────────────────────┐   ┌─────────────────────────────────────┐ │
│  │ Search: covering file [____] │   │   actor User                         │ │
│  │                              │   │   User -> API: POST /projects        │ │
│  │ • org_create                 │   │   API -> Repo: create_project()      │ │
│  │ • project_create  ●stale     │   │   Repo -> ORM: insert(...)           │ │
│  │ • project_update             │   │   ...                                 │ │
│  │ • member_invite              │   └─────────────────────────────────────┘ │
│  │                              │                                            │
│  │                              │   Flame graph                              │
│  │                              │   ┌────────────────────────────────────┐ │
│  │                              │   │ <iframe src="flame.html"/>          │ │
│  │                              │   └────────────────────────────────────┘ │
│  │                              │                                            │
│  │                              │   ▸ Folded stacks (1.2 MB)  [expand]      │
│  └──────────────────────────────┘                                            │
└──────────────────────────────────────────────────────────────────────────────┘
```

- "Search: covering file" filters scenarios client-side by scanning each scenario's `summary.json` `coveredFiles` field (assumed present; if absent, search disabled with explanatory note).
- Mermaid: rendered with `mermaid` lib on demand; render failures show the raw mermaid text in a `<pre>` with an explanation.
- Flame: iframe sandboxed (`sandbox="allow-scripts allow-same-origin"`), height 480px, with a "open in new tab" button for full-screen inspection.
- Folded stacks: collapsed by default (the file can be multi-MB); only fetched when expanded.

### 2.6 Visual language

- Monospace (`ui-monospace, SFMono-Regular, Menlo`) for paths, commands, mermaid bodies, capability ids.
- Sans (`ui-sans-serif, system-ui`) for prose.
- Neutral palette: zinc-50 background, zinc-900 text, accent for active tab, amber for stale, green for fresh, red for removed, blue for reduced.
- No MUI, no Tailwind runtime — plain CSS modules + a small `tokens.css` (CSS variables for color/spacing). Keeps deps minimal; matches the "small standalone tool" intent.
- Dark mode: deferred to v2 (call out in README).

### 2.7 Accessibility

- Tabs in the left rail use `role="tablist"` / `role="tab"` with arrow-key navigation.
- Stale badge is text plus color, not color alone.
- All interactive elements have visible focus rings.
- Mermaid and flame iframes have `title` attributes naming the scenario.

---

## Part 3 — Implementation

### 3.1 Stack decision

See §3.2 above. Vite + React + TypeScript, plain CSS modules, `mermaid` for sequence rendering, no other runtime deps beyond `react`, `react-dom`. Dev deps: `vite`, `@vitejs/plugin-react`, `typescript`, `@playwright/test`, `vitest`, `@types/react`, `@types/react-dom`.

### 3.2 Project structure

Per §3.3.

### 3.3 Aspect plugin contract

Per §3.4. The interface is the stable extension point; all reviewers should evaluate new aspects against it.

### 3.4 Vite static-mount plugin

`vite.config.ts` registers a small plugin:

```ts
// pseudo, not implementation
function repoArtifactsPlugin(repoRoot: string) {
  return {
    name: 'dev-dashboard-artifacts',
    configureServer(server) {
      server.middlewares.use('/artifacts', (req, res, next) => {
        if (req.method !== 'GET') { res.statusCode = 405; res.end(); return; }
        // map /artifacts/scenarios/... → repoRoot/frontend/walkthroughs/gallery/...
        // serve via fs.createReadStream; set Content-Type by extension; 404 on miss
      });
    },
  };
}
```

`server.fs.allow` is extended to include the three artifact roots. Repo root is resolved by walking up from `tools/dev-dashboard/` until a `.git` directory is found, then exposed as `import.meta.env.VITE_REPO_ROOT`.

### 3.5 Staleness pipeline

Per §3.5. `scripts/aspects.config.mjs` is the shared declarative source. The TS registry imports it (via Vite's JS interop) and overlays `render`, `icon`, `load` (which are not data and cannot be expressed in JSON).

### 3.6 Loaders per aspect

- **Scenarios** `load()`:
  - `GET /artifacts/scenarios/manifest.json` → JSON.
  - Validates with a small zod-free hand-written guard (no extra deps).
  - Resolves media URLs to `/artifacts/scenarios/<rel>` so the browser fetches them through the same mount.
- **Capabilities** `load()`:
  - `GET /artifacts/capabilities/baseline.json` and `/artifacts/capabilities/report.json` in parallel.
  - If `report.json` is missing, fall back to baseline-only mode (no diff toggle, banner explains).
  - Joins by `(method, path)`; computes status per row.
- **Traces** `load()`:
  - `GET /artifacts/traces/index.json` if present, else `GET /artifacts/traces/` directory listing (provided by the static-mount plugin for directories — opt-in flag in the plugin).
  - For the selected scenario, lazy-loads `summary.json`, `mermaid.md`, and (on user expand) `folded.txt`. `flame.html` loaded by iframe `src`.

### 3.7 Migration tasks

Per §3.6. Listed for implementation order:

1. Build the new dashboard alongside the old surfaces.
2. Verify parity (smoke tests + manual eyeball).
3. In one commit: delete `frontend/src-walkthroughs-dashboard/`, remove its npm scripts, update `docs/testing/scenario_walkthroughs.md`.
4. In one commit: gate `analyze_capabilities.py` HTML emission behind `--emit-html` (default off), delete `backend/evidence/capabilities/index.html`, `viewer.css`, `viewer.js`, update `backend/evidence/capabilities/README.md`.

### 3.8 Test matrix

#### 3.8.1 Unit tests — `tools/dev-dashboard/tests/unit/` (Vitest)

| Test name | Verifies |
|---|---|
| `staleness_marks_aspect_stale_when_source_newer_than_artifact` | `staleness.ts` returns `stale: true` when `newestSourceMtime > primaryArtifactMtime`. |
| `staleness_marks_fresh_when_artifact_newer_than_sources` | `stale: false` when artifact mtime is later. |
| `staleness_marks_missing_when_artifact_does_not_exist` | `primaryArtifactExists: false`, `stale: false` (missing is its own state). |
| `staleness_handles_aspect_with_zero_source_files` | Empty source root → not stale; no crash. |
| `loadArtifact_returns_data_and_response_mtime` | Successful fetch returns parsed JSON plus `Last-Modified` header value. |
| `loadArtifact_throws_typed_error_on_404` | Missing artifact raises `ArtifactMissingError`, not generic Error. |
| `loadArtifact_throws_typed_error_on_invalid_json` | Malformed JSON raises `ArtifactMalformedError` with the path included. |
| `registry_resolves_aspect_by_id` | `getAspect('scenarios')` returns the scenarios aspect. |
| `registry_returns_undefined_for_unknown_id` | Unknown id returns undefined; consumer responsible for fallback. |
| `registry_aspect_ids_are_unique` | Sanity guard: duplicate ids throw at module load. |
| `clipboard_copies_only_the_command_string` | Given a CommandBlock spec, the clipboard payload equals `refreshCommand` exactly (no cwd, no description). |
| `capabilities_status_classifier_unchanged` | Row with identical baseline + current caps → status `unchanged`. |
| `capabilities_status_classifier_expanded` | Row with current ⊋ baseline → status `expanded`, returns added set. |
| `capabilities_status_classifier_reduced` | Row with current ⊊ baseline → status `reduced`, returns removed set. |
| `capabilities_status_classifier_new_route` | Route in current but not baseline → `new`. |
| `capabilities_status_classifier_removed_route` | Route in baseline but not current → `removed`. |

#### 3.8.2 Smoke tests — `tools/dev-dashboard/tests/smoke/dashboard.smoke.spec.ts` (Playwright)

Boots the dashboard's own dev server (separate from product `frontend/` Playwright). Uses fixture artifact dirs prepared per test.

| Test name | Verifies |
|---|---|
| `dashboard_boots_and_shows_three_aspect_tabs` | After `npm run dashboard`, all three tabs (`Scenarios`, `Capabilities`, `Traces`) render in the left rail. |
| `clicking_each_aspect_tab_renders_its_panel_header` | Each tab shows `AspectShell` header with title and refresh-command block. |
| `empty_state_appears_when_artifacts_are_missing` | With artifact dirs deleted, each panel shows the friendly empty-state copy and the refresh command. |
| `stale_badge_appears_when_source_file_newer_than_artifact` | `touch` a file under the aspect's source root after artifact mtime → reload → stale badge visible, amber dot in left rail. |
| `fresh_state_when_artifact_is_newer_than_all_sources` | Artifact mtime > source mtimes → no stale badge, green "fresh" indicator. |
| `refresh_command_block_copies_only_the_command_to_clipboard` | Click `[copy]` on the command block → clipboard payload equals the command string exactly. |
| `scenarios_panel_renders_card_grid_from_manifest` | Given a fixture `manifest.json` with 3 scenarios, 3 cards appear with their titles. |
| `scenarios_card_click_opens_detail_view_with_video_and_steps` | Clicking a card navigates to the detail view; video element present; step list rendered. |
| `capabilities_panel_renders_route_table_from_baseline_and_report` | Given fixture baseline + report, table rows match expected (method, path, status). |
| `capabilities_diff_toggle_filters_to_changed_rows` | Switching to `diff` mode hides `unchanged` rows. |
| `capabilities_falls_back_to_baseline_only_when_report_missing` | With `report.json` deleted, panel renders baseline rows and shows the explanatory banner; diff toggle disabled. |
| `traces_panel_lists_scenarios_with_artifacts` | Given two fixture trace dirs, both scenarios appear in the list. |
| `traces_selecting_scenario_renders_mermaid_and_flame_iframe` | Click a scenario → mermaid SVG present in DOM; iframe `src` ends with `flame.html`. |
| `traces_folded_stacks_collapsed_by_default` | Folded-stacks block is not in the DOM until expanded; expand renders it. |
| `traces_search_covering_file_filters_scenarios` | Type a known covered file path → list filters to scenarios whose `summary.json` references it. |
| `cross_link_scenario_to_trace_appears_only_when_trace_exists` | Scenario detail shows "View trace" iff matching trace dir exists; absent otherwise. |
| `top_bar_summarises_aggregate_freshness` | Top bar shows `3 aspects · N stale` matching the staleness file. |
| `unknown_aspect_id_in_url_hash_falls_back_to_first_aspect` | Visiting `#/nonsense` selects Scenarios and updates the hash. |
| `repo_root_is_displayed_in_top_bar` | Top bar displays the resolved repo absolute path. |

#### 3.8.3 Test fixtures

- `tools/dev-dashboard/tests/fixtures/scenarios/manifest.json` — three minimal scenarios with media file references to small generated `.gif`/`.mp4` stubs (or PNG placeholders).
- `tools/dev-dashboard/tests/fixtures/capabilities/baseline.json` and `report.json` — covering one row per status type (unchanged, expanded, reduced, new, removed).
- `tools/dev-dashboard/tests/fixtures/traces/<scenario>/{summary.json,mermaid.md,flame.html,folded.txt}` — two scenarios.
- A Playwright fixture `withArtifacts(layout: Layout)` that copies a chosen subset of fixture dirs into a temp repo-root and points the dashboard at it via env var.
- A Playwright fixture `touchSource(aspect: AspectId, relPath: string)` that sets a source file's mtime to `now + 60s` to deterministically trigger staleness.

#### 3.8.4 No backend / domain / repository / API / PBT / scenario tests

This feature changes no product code. There is no API surface, no domain model, no repository, no FastAPI route, and no user-facing product flow. Consequently:

- No `tests/api/`, `tests/dal/`, `tests/domain/`, `tests/property_based/` tests are added.
- **No `frontend/e2e/scenarios/*.scenario.spec.ts` is added.** The "scenario coverage for user-facing features" rule (principles §"Scenario coverage") explicitly exempts non-user-facing tooling. The dashboard *consumes* scenario walkthroughs; it is not itself a product feature a user invites teammates to.

This exemption is called out here so reviewers do not flag its absence.

### 3.9 FE/BE contract

**None.** Per §3.7 above and AC-DD-008. The dashboard reads files from the repo via its own Vite dev server. Calling this out as a deliberate architectural choice.

### 3.10 Implementation order

1. Scaffold `tools/dev-dashboard/` (package.json, vite config with the static-mount plugin, tsconfig, empty `App.tsx`).
2. Implement `lib/staleness.ts`, `lib/loadArtifact.ts`, `aspects/index.ts`, `Aspect` interface. Unit tests for each.
3. Implement `scripts/check-staleness.mjs` and `scripts/aspects.config.mjs`. Unit tests via Vitest (importing the module directly with a temp fixture tree).
4. Implement `components/AspectShell.tsx`, `LeftRail.tsx`, `TopBar.tsx`, `CommandBlock.tsx`, `StaleBadge.tsx`, `EmptyState.tsx`. No tests at this level — covered by smoke tests.
5. Implement Scenarios aspect (port from `frontend/src-walkthroughs-dashboard/`).
6. Implement Capabilities aspect (status classifier first, with unit tests; then UI).
7. Implement Traces aspect.
8. Write Playwright smoke suite. Each aspect's smoke tests added immediately after that aspect is implemented; full suite green before moving on.
9. Migration commit 1: delete `frontend/src-walkthroughs-dashboard/`, update docs.
10. Migration commit 2: flag-gate HTML emission in `analyze_capabilities.py`, delete the standalone capabilities viewer files, update its README.
11. Update top-level `CLAUDE.md` and `docs/testing/scenario_walkthroughs.md` to point at `npm run dashboard`.
12. Final validation: dashboard smoke suite green; product `npm run lint && npm run typecheck && npm run e2e` still green; backend `./devtools/run_all_agent_validations.sh` still green (the `--emit-html` change must not break existing capability analyzer tests — if any assert on the HTML being produced, update them in this commit).

---

## 4. Edge cases covered

| Edge case | Handling |
|---|---|
| Artifact directory missing entirely | `loadArtifact` throws `ArtifactMissingError`; AspectShell renders `EmptyState` with refresh command. |
| `manifest.json` malformed JSON | `loadArtifact` throws `ArtifactMalformedError`; panel shows error card with parsed-error message and the path; refresh command still shown. |
| `manifest.json` JSON-valid but missing required fields | Hand-written validator throws `ArtifactSchemaError` with field path; panel shows the same error card. |
| Mermaid render failure | Catch in `MermaidView`; render raw mermaid text in `<pre>` with a one-line note; do not break the panel. |
| Very large `flame.html` | Loaded only inside iframe (browser handles streaming); no JS parse needed. Iframe height capped; "open in new tab" link provided. |
| Scenario with no video, only screenshots | Detail view shows screenshot strip in place of the video element. |
| Scenario with no GIF | Card shows the first screenshot as a static thumbnail; hover does nothing. |
| Capabilities with zero routes | Table renders an empty-state row: "No routes found in current report." |
| Repo opened via symlinked path | Repo-root walk resolves real path via `fs.realpathSync`; staleness uses canonical paths so symlinks do not double-count. |
| Source file deleted but artifact still present | Staleness uses *max* source mtime; deletion lowers the max but never marks stale by itself. Unaffected. |
| Two aspects share a source root (future) | `aspects.config.mjs` walks each root once and caches. Not needed in v1; design admits it. |
| User runs dashboard from a non-git checkout (e.g. tarball) | Repo-root walk falls back to `tools/dev-dashboard/../..`; logs a warning to console; `.staleness.json` still works because it uses relative paths. |
| `.staleness.json` missing on first boot | Vite `predashboard` script generates it. If a user opens the dashboard without `.staleness.json` (e.g. opened the built site directly), the dashboard shows a top-bar warning: "Staleness data not generated; run `npm run dashboard:check`." |
| Clipboard API blocked (e.g. non-secure context) | Falls back to a `<textarea>`-select-all-execCommand path; same payload guarantees. |
| Trace `summary.json` lacks `coveredFiles` | Search box is disabled with tooltip explaining the field is missing; per-scenario view still works. |
| Capabilities `report.json` missing | Baseline-only mode (see test `capabilities_falls_back_to_baseline_only_when_report_missing`). |
| Two scenarios with the same id across manifests | Should not happen by construction; if it does, the staleness/loader logs a warning and the first wins. |
| Port 5179 already in use | Vite picks the next free port and prints it; documented in README. |

---

## 5. Risks / open questions

1. **`coveredFiles` in trace `summary.json`** — does it exist today, or is it a planned field? If absent in v1, the trace search journey degrades to a name search only. _Open: confirm with current pytest-tracer output schema before implementing the Traces aspect._
2. **Scenario id ↔ trace dir name** — the cross-aspect link assumes both surfaces use the same id (snake_case test name). If one uses path-derived ids and the other uses a separate slug, the link fails silently. _Open: spot-check both manifests before implementing the link._
3. **`mermaid` package size** — the lib is ~1MB. Acceptable for a dev tool. Lazy-imported only inside `TracesAspect` so other tabs don't pay the cost.
4. **`analyze_capabilities.py` HTML flag-gate** — gating may break existing tests that assert the HTML is generated. The migration commit must include those test updates; if any *agent validation* depends on the HTML existing, scope expands. _Open: grep capability analyzer tests before the migration commit._
5. **Vite static-mount of repo paths** — security is fine for localhost-only dev tools, but the README must clearly document "do not expose this server beyond localhost." Bind explicitly to `127.0.0.1`.
6. **Adding a new aspect = "small change"** — the contract aims for it, but the staleness script needs a config update too. The shared `aspects.config.mjs` keeps it to one file; this is the litmus test for the design.

---

## 6. Sign-off

- [ ] User approved plan — date/note
- [ ] `tools/dev-dashboard/` scaffolded; unit tests green
- [ ] Scenarios aspect implemented; smoke tests green
- [ ] Capabilities aspect implemented; smoke tests green
- [ ] Traces aspect implemented; smoke tests green
- [ ] Migration commits landed (`src-walkthroughs-dashboard` deleted; capabilities HTML gated/removed)
- [ ] Docs updated (`CLAUDE.md`, `docs/testing/scenario_walkthroughs.md`, capabilities `README.md`)
- [ ] Backend `./devtools/run_all_agent_validations.sh` green
- [ ] Product `npm run lint && npm run typecheck && npm run e2e` green
- [ ] code-reviewer sign-off

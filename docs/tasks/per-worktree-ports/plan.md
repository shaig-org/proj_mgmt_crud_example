# Feature Plan: Per-worktree ports (concurrent dev stacks + Claude Preview)

**Status**: Approved — ready to implement
**Date**: 2026-04-19 (revised)
**Stack**: Full-stack (build/dev-infrastructure — no runtime product behavior changes)
**Detailed spec**: N/A — this is dev-infrastructure, not a product feature. This plan is the authoritative design document. (Per `docs/architecture/principles.md` §Spec discipline: REQ IDs are reserved for product behavior requirements. Infra changes with no externally-observable product behavior are captured by the plan alone.)

---

## 1. Requirements in scope

Dev-infrastructure goals (no REQ-IDs — see above):

- **G1 — Concurrent worktrees**: Two or more git worktrees of this repo can boot full dev stacks (backend + frontend + dev-dashboard) simultaneously on 127.0.0.1 without port collisions.
- **G2 — Claude Preview MCP compatibility**: Each worktree has a deterministic, committed `.claude/launch.json` pointing Claude's `mcp__Claude_Preview__preview_start` at the frontend and dev-dashboard ports for that specific worktree. No manual edit per worktree.
- **G3 — Zero-touch on worktree creation**: `git worktree add <path>` (in a bootstrapped clone) produces a working `.claude/launch.json` and per-project `.env.local` files with no further commands. The post-checkout hook is the primary mechanism.
- **G4 — Backwards compatibility**: Worktrees or clones that have not run the generator (yet) still boot on the historical defaults `3000 / 5179 / 8000`.
- **G5 — Preserve existing flows**:
  - `cd backend && ./devtools/run_all_agent_validations.sh` stays green (and now additionally executes the new pytest-subprocess-based generator tests, since they live under `backend/tests/tools/`).
  - `npm --prefix frontend run lint|typecheck|e2e` stays green; new `npm --prefix frontend run test` (Vitest) is added and is also green.
  - `npm --prefix tools/dev-dashboard run typecheck|lint|test|smoke` stays green.
  - `./devtools/refresh-dashboard-artifacts.sh` continues to produce all artifacts (including scenario GIFs).
  - `frontend/playwright.config.ts`'s separate e2e bank (backend `18000`, frontend `13001`, `VITE_E2E_TESTING=true`) is **untouched** — dev-bank parameterization must not regress it.
- **G6 — Idempotent, observable, portable**: the generator is safe to re-run, prints the chosen ports, and runs on macOS and Linux bash (no `gnu-awk`, `lsof`, or other non-POSIX-on-macOS assumptions without a fallback).
- **G7 — Reusable recipe**: ship a standalone guide at `docs/guides/per-worktree-ports-setup.md` so the design pattern can be reproduced in other projects (this is part of definition-of-done — see §3.10 and §9).

## 2. Out of scope

- Unifying the Playwright e2e port bank (`18000` / `13001`) with the dev bank. They remain independent.
- Docker, devcontainers, or remote port forwarding.
- Solving the bootstrap problem where `core.hooksPath=githooks` is not yet set (first-ever clone). Documented as a limitation; `devtools/install-git-hooks.sh` remains the one-time bootstrap step.
- Running the backend under a process manager that auto-picks free ports (uvicorn remains invoked with an explicit `--port`).
- Health-check / auto-recovery of dead servers behind Claude Preview.
- Windows native support (bash generator script targets macOS + Linux; WSL works as Linux).
- Dynamic port reassignment mid-session (ports are fixed at generator-run time).
- Hot-migration of running stacks to new ports.
- Updating the product READMEs' narrative URLs (`README.md`, `DEMO_SETUP.md`, `frontend/README.md`) beyond a one-line "ports are per-worktree; see `.env.local`" note — a full rewrite of demo docs is out of scope.

---

## 3. Architecture

### 3.1 Artifact map

| Artifact | Kind | Path | Committed? |
|---|---|---|---|
| launch template | new | `.claude/launch.json.template` | yes |
| frontend env template | new | `.claude/env.frontend.template` | yes |
| dashboard env template | new | `.claude/env.dashboard.template` | yes |
| backend ports env template | new | `.claude/env.ports.template` | yes |
| generator | new | `devtools/setup-worktree-ports.sh` | yes |
| post-checkout hook | new | `githooks/post-checkout` | yes |
| reproducible-setup guide | new | `docs/guides/per-worktree-ports-setup.md` | yes |
| gitignore update | edit | `.gitignore` | yes |
| vite parameterization (frontend) | edit | `frontend/vite.config.ts` | yes |
| api base URL | edit | `frontend/src/services/api.ts` | yes |
| dashboard vite port | edit | `tools/dev-dashboard/vite.config.ts` (+ `package.json` script) | yes |
| postinstall backup | edit | `frontend/package.json`, `tools/dev-dashboard/package.json` | yes |
| vitest infra (frontend) | new | `frontend/vitest.config.ts`, `frontend/tests/unit/setup.ts`, devDeps | yes |
| `validate-frontend` skill text | edit | `.claude/skills/validate-frontend/*` (or wherever it lives) — see §3.7 | yes |
| backend run wrapper edit | edit | `backend/devtools/run_with_env.sh` (sources `.claude/env.ports` if present) | yes |
| refresh-dashboard message | edit | `devtools/refresh-dashboard-artifacts.sh` (one error string) | yes |
| CLAUDE.md pointer | edit | root `CLAUDE.md` (one short paragraph) | yes |
| dev-dashboard README pointer | edit | `tools/dev-dashboard/README.md` (one line) | yes |
| frontend CLAUDE.md pointer | edit | `frontend/CLAUDE.md` (one line) | yes |
| generated launch.json | generated | `.claude/launch.json` | no — gitignored |
| generated frontend env | generated | `frontend/.env.local` | no — gitignored |
| generated dashboard env | generated | `tools/dev-dashboard/.env.local` | no — gitignored |
| generated backend ports env | generated | `.claude/env.ports` | no — gitignored |

### 3.2 Env file layout — DECISION (option a)

**Decision: one `.env.local` per Vite project + one `.claude/env.ports` for the backend, all generated atomically from the same chosen offset.**

#### 3.2.1 Why not "one repo-root .env.local"

Vite's `envDir` defaults to the **project root** (the directory containing `vite.config.ts`), not the git repo root. Source: <https://vite.dev/config/shared-options.html#envdir> — "The directory from which `.env` files are loaded. Can be an absolute path, or a path relative to the project root. Default: `root`." `loadEnv(mode, envDir, prefix)` follows the same rule.

So a single repo-root `.env.local` would require **per-project overrides**:
- `frontend/vite.config.ts` would set `envDir: '..'` and call `loadEnv(mode, '..', '')`.
- `tools/dev-dashboard/vite.config.ts` would set `envDir: '../..'` and call `loadEnv(mode, '../..', '')`.

Two different `envDir` values for the same file is brittle:
- `loadEnv(mode, dir, '')` with empty prefix loads **all** env vars (including potentially-secret ones a developer might add to a repo-root `.env.local`).
- `npm ci` lifecycle hooks run from each `package.json`'s directory; sourcing a repo-root file from arbitrary cwd requires absolute paths or extra logic.
- VS Code's launch.json `envFile` paths, Playwright's `webServer.env`, future tools — all would need their own knowledge of "the env file is two levels up".

Option (b) — one repo-root file + wrapper scripts that source it before invoking `vite` — was considered. It works but is heavier: every `npm script` that touches Vite would need a `bash -c 'source ../.env.local && vite ...'` preamble, breaking direct `npx vite` invocation and adding shell coupling to npm scripts.

**Chosen approach** (option a): the generator is the single source of truth and writes **three** files from one chosen offset:
1. `frontend/.env.local` — Vite auto-loads (default `envDir`); dotenv-style key=value.
2. `tools/dev-dashboard/.env.local` — Vite auto-loads (default `envDir`); dotenv-style key=value.
3. `.claude/env.ports` — sourced by `backend/devtools/run_with_env.sh` (and by humans who `source .claude/env.ports`); plain shell `export FOO=bar` lines.

Plus the existing fourth output:
4. `.claude/launch.json` — rendered for Claude Preview MCP.

Trade-off accepted: three files instead of one. The generator writes them atomically, so they are always consistent. Each consumer reads the file most natural to it, with zero `envDir` overrides in either Vite config.

#### 3.2.2 File contents (single source of truth: the chosen offset N)

Where `FRONTEND_PORT = 3000+N`, `DASHBOARD_PORT = 5179+N`, `BACKEND_PORT = 8000+N`.

**`frontend/.env.local`** (consumed by `frontend/vite.config.ts`):
```
# Auto-generated by devtools/setup-worktree-ports.sh — do not edit.
# Regenerate with `--force` if ports become stale.
FRONTEND_PORT=<3000+N>
BACKEND_URL=http://localhost:<8000+N>
```

**`tools/dev-dashboard/.env.local`** (consumed by `tools/dev-dashboard/vite.config.ts`):
```
# Auto-generated by devtools/setup-worktree-ports.sh — do not edit.
# Regenerate with `--force` if ports become stale.
DASHBOARD_PORT=<5179+N>
```

**`.claude/env.ports`** (sourced by backend wrapper + humans):
```
# Auto-generated by devtools/setup-worktree-ports.sh — do not edit.
# Regenerate with `--force` if ports become stale.
export FRONTEND_PORT=<3000+N>
export DASHBOARD_PORT=<5179+N>
export BACKEND_PORT=<8000+N>
export BACKEND_URL=http://localhost:<8000+N>
```

**`.claude/launch.json`** (rendered from `.claude/launch.json.template`, see §3.4):
```
{
  "version": "0.0.1",
  "configurations": [
    {
      "name": "app",
      "runtimeExecutable": "npm",
      "runtimeArgs": ["--prefix", "frontend", "run", "dev"],
      "port": <3000+N>
    },
    {
      "name": "dashboard",
      "runtimeExecutable": "npm",
      "runtimeArgs": ["--prefix", "tools/dev-dashboard", "run", "dashboard"],
      "port": <5179+N>
    }
  ]
}
```

#### 3.2.3 The four consumers, with concrete invocation paths

1. **Vite frontend dev** — `npm --prefix frontend run dev`. Vite auto-loads `frontend/.env.local` (default `envDir`). The config calls `loadEnv(mode, process.cwd(), '')` so it can read non-`VITE_`-prefixed `FRONTEND_PORT` and `BACKEND_URL` (these stay server-side; they don't leak to the bundle). The config also `define`s `import.meta.env.VITE_BACKEND_URL` to `''` for client-side `api.ts`.

2. **Vite dashboard dev** — `npm --prefix tools/dev-dashboard run dashboard`. Vite auto-loads `tools/dev-dashboard/.env.local`. The config reads `process.env.DASHBOARD_PORT` (Vite injects it into `process.env` because `loadEnv` is also called explicitly with empty prefix to allow reading). Same pattern as frontend.

3. **Backend uvicorn** — `cd backend && ./devtools/run_with_env.sh uv run uvicorn project_management_crud_example.app:app --port "$BACKEND_PORT"`. The wrapper sources `../.claude/env.ports` (if present) before exec — so `$BACKEND_PORT` is in scope. Default fallback to `8000` if the file is absent. CLAUDE.md gets a one-line example so humans copy/paste the right form.

4. **Claude Preview MCP `preview_start`** — reads `.claude/launch.json` directly. Its `port` fields hard-code the integer the generator chose; no env-var indirection needed at preview-time.

Two consumers that **don't** need any env-file handling:
- **Playwright e2e** (`frontend/playwright.config.ts`) — keeps its own ports (`18000`, `13001`) hard-coded; the `vite.config.e2e.ts` `define`s `VITE_E2E_TESTING=true`; the `webServer.env` carries `E2E_TESTING=true` and `JWT_SECRET_KEY` to the backend. None of this touches the dev bank.
- **`refresh-dashboard-artifacts.sh`** — invokes its own backend on port 18000 for e2e and uses the dashboard's existing artifacts; no per-worktree port awareness needed except the one error-string update mentioned in §8.

#### 3.2.4 Env-flow diagram

```
generator: pick offset N → writes 4 files atomically
     │
     ├─► frontend/.env.local ──► Vite (frontend) auto-load
     │                            ├─ server.port = FRONTEND_PORT
     │                            ├─ server.proxy targets BACKEND_URL
     │                            └─ define VITE_BACKEND_URL="" → api.ts uses relative paths
     │
     ├─► tools/dev-dashboard/.env.local ──► Vite (dashboard) auto-load
     │                                       └─ server.port = DASHBOARD_PORT
     │
     ├─► .claude/env.ports ──► backend/devtools/run_with_env.sh (source)
     │                          └─ uvicorn --port $BACKEND_PORT
     │
     └─► .claude/launch.json ──► Claude Preview MCP
                                  └─ preview_start reads "port" fields verbatim
```

### 3.3 `.claude/launch.json.template`

```
{
  "version": "0.0.1",
  "configurations": [
    {
      "name": "app",
      "runtimeExecutable": "npm",
      "runtimeArgs": ["--prefix", "frontend", "run", "dev"],
      "port": ${FRONTEND_PORT}
    },
    {
      "name": "dashboard",
      "runtimeExecutable": "npm",
      "runtimeArgs": ["--prefix", "tools/dev-dashboard", "run", "dashboard"],
      "port": ${DASHBOARD_PORT}
    }
  ]
}
```

Substitution semantics: only `${FRONTEND_PORT}` and `${DASHBOARD_PORT}` are replaced. All other `$` or `{}` characters are literal. Generator uses `sed` with a fixed token list (not `envsubst`, which would require naming every env var).

### 3.4 Env file templates

**`.claude/env.frontend.template`**:
```
# Auto-generated by devtools/setup-worktree-ports.sh — do not edit.
# Regenerate with `--force` if ports become stale.
FRONTEND_PORT=${FRONTEND_PORT}
BACKEND_URL=http://localhost:${BACKEND_PORT}
```

**`.claude/env.dashboard.template`**:
```
# Auto-generated by devtools/setup-worktree-ports.sh — do not edit.
# Regenerate with `--force` if ports become stale.
DASHBOARD_PORT=${DASHBOARD_PORT}
```

**`.claude/env.ports.template`**:
```
# Auto-generated by devtools/setup-worktree-ports.sh — do not edit.
# Regenerate with `--force` if ports become stale.
export FRONTEND_PORT=${FRONTEND_PORT}
export DASHBOARD_PORT=${DASHBOARD_PORT}
export BACKEND_PORT=${BACKEND_PORT}
export BACKEND_URL=http://localhost:${BACKEND_PORT}
```

Generator substitutes `${FRONTEND_PORT}`, `${DASHBOARD_PORT}`, `${BACKEND_PORT}` only. Any other unresolved `${...}` token after substitution is an error (exit 1).

### 3.5 Generator — `devtools/setup-worktree-ports.sh`

```
devtools/setup-worktree-ports.sh [--force] [--print] [--worktree-root <path>]
```

**Behavior**:

1. Resolve worktree root: `--worktree-root` > `git rev-parse --show-toplevel` > `$PWD` (in that order). All output paths are relative to this root.
2. **Idempotency check**: if `.claude/launch.json` AND `frontend/.env.local` AND `tools/dev-dashboard/.env.local` AND `.claude/env.ports` all exist and `--force` is absent → log `"[setup-worktree-ports] all artifacts present; skipping (use --force to regenerate)"` and exit 0. (Checking all four — not just `launch.json` — closes a hole where a partially-generated state would be silently accepted.)
3. **Port probe**. Candidate offsets: `0, 10, 20, 30, …, 990` (100 candidates, covers `3000–3990 / 5179–6169 / 8000–8990`).
   - For each offset `N`, test all three of `3000+N`, `5179+N`, `8000+N` on `127.0.0.1`.
   - A port is "free" iff a `bash`-portable probe succeeds. The implementation uses the POSIX bash TCP probe (works on macOS bash 3.2 and Linux bash 4+, no `lsof` / `nc` / `ss`):
     ```
     # macOS-quirk note: bash's /dev/tcp redirection is hard-coded into bash itself
     # (it does not actually open /dev/tcp on the filesystem). Available on macOS's
     # default bash 3.2 but ONLY when invoked as bash, NOT as sh. The generator
     # uses `#!/usr/bin/env bash` to guarantee bash mode.
     (exec 3<>/dev/tcp/127.0.0.1/$PORT) 2>/dev/null
     ```
     If the connect **fails**, the port is free. If it succeeds, close fd3 and mark busy.
   - First offset where all three are free wins.
   - If no offset in `[0..990 step 10]` works → exit 2 with a clear message.
4. **`--print` mode**: after choosing, print `FRONTEND_PORT=<> DASHBOARD_PORT=<> BACKEND_PORT=<>` on one line to stdout and exit 0. Does not write any files.
5. **Normal mode**: write the four files atomically (write each to `*.tmp`, `mv` into place, in this order: `.claude/env.ports`, `frontend/.env.local`, `tools/dev-dashboard/.env.local`, `.claude/launch.json`). If any write fails, `mv`s already done are left as-is (the next run will detect partial state via the all-four idempotency check and re-render under `--force`).
6. Log one line to stdout: `[setup-worktree-ports] offset=<N> frontend=<P1> dashboard=<P2> backend=<P3>`.
7. **Exit codes**: `0` = wrote files OR skipped idempotently; `1` = template missing / unwritable paths / templating failure; `2` = no free port bank found; `3` = invalid CLI args.
8. **Template failure path**: if any of the four templates is missing or contains an unresolved `${VAR}` token after substitution, exit `1` with `"[setup-worktree-ports] template error: unresolved ${VAR} in <file>"` — do not `mv` any half-rendered file (the `.tmp` + `mv` scheme is what enforces this).

**Non-behaviors** (explicitly not done):
- Does not start any servers.
- Does not source or export env vars into the calling shell.
- Does not touch `.gitignore` (that's a committed edit, not generated).
- Does not `chmod` anything other than the four output files (`644`, default umask).

### 3.6 Hook — `githooks/post-checkout`

```
#!/usr/bin/env bash
# Git calls us with: $1 old_head, $2 new_head, $3 branch_checkout_flag
# Runs on: git checkout, git clone (if hooksPath already configured), git worktree add.
# Intentionally does NOT `set -e` — a generator failure must not block git itself.
REPO_ROOT="$(git rev-parse --show-toplevel)"
"$REPO_ROOT/devtools/setup-worktree-ports.sh" || {
  echo "[post-checkout] setup-worktree-ports failed (exit $?); checkout proceeds anyway." >&2
}
```

- Idempotent via the generator's own existence-check → a normal `git checkout` inside an established worktree is a no-op.
- Must be executable; `devtools/install-git-hooks.sh` already `chmod +x`'s every file in `githooks/` so no change to that script is required.

### 3.7 Code edits — exact shapes

**`frontend/vite.config.ts`** (replace whole file):

```ts
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  // Default envDir is the project root (frontend/), which is what we want.
  // Empty prefix lets us read FRONTEND_PORT and BACKEND_URL (no VITE_ prefix).
  // We do NOT expose these to the client bundle — that's controlled by `define` below.
  const env = { ...loadEnv(mode, process.cwd(), ''), ...process.env };
  const FRONTEND_PORT_RAW = Number(env.FRONTEND_PORT);
  const FRONTEND_PORT = Number.isFinite(FRONTEND_PORT_RAW) && FRONTEND_PORT_RAW > 0
    ? FRONTEND_PORT_RAW
    : 3000;
  const BACKEND_URL = env.BACKEND_URL && env.BACKEND_URL.length > 0
    ? env.BACKEND_URL
    : 'http://localhost:8000';

  return {
    plugins: [react()],
    server: {
      port: FRONTEND_PORT,
      proxy: {
        '/api': { target: BACKEND_URL, changeOrigin: false },
        '/health': { target: BACKEND_URL, changeOrigin: false },
        '/auth': { target: BACKEND_URL, changeOrigin: false },
      },
    },
    define: {
      // Empty string → api.ts falls back to the relative path (same-origin, proxied).
      'import.meta.env.VITE_BACKEND_URL': JSON.stringify(''),
    },
  };
});
```

Notes:
- `vite.config.e2e.ts` stays unchanged (still hard-codes `13001` and `VITE_E2E_TESTING=true`). That's the point of G5.
- `frontend/package.json`'s `"dev"` script drops `--port 3000` so the vite config is the sole source of truth: `"dev": "vite"`.

**`frontend/src/services/api.ts`** (replace lines 1–6):

```ts
import axios, { AxiosInstance } from 'axios';

function resolveBaseUrl(): string {
  if (import.meta.env.VITE_E2E_TESTING === 'true') return 'http://localhost:18000';
  const explicit = import.meta.env.VITE_BACKEND_URL;
  if (typeof explicit === 'string' && explicit.length > 0) return explicit;
  return ''; // relative — proxied by vite dev-server (dev) or served by SPA host (prod)
}

const API_BASE_URL = resolveBaseUrl();
```

Rest of the file is untouched. Endpoints remain `'/api/...'`, `'/auth/login'`, `'/health'`; with `API_BASE_URL = ''` the axios client issues `/api/projects` — which is proxied in dev and same-origin in any deployed scenario.

**`tools/dev-dashboard/vite.config.ts`** (modify `server` block + add `loadEnv` call):

```ts
// Near the top of buildConfig(), add (still inside async buildConfig):
const env = { ...require('vite').loadEnv('development', dashboardDir, ''), ...process.env };
const DASHBOARD_PORT_RAW = Number(env.DASHBOARD_PORT);
const DASHBOARD_PORT = Number.isFinite(DASHBOARD_PORT_RAW) && DASHBOARD_PORT_RAW > 0
  ? DASHBOARD_PORT_RAW
  : 5179;

// In the returned defineConfig({...}), server block:
server: {
  host: '127.0.0.1',
  port: DASHBOARD_PORT,
  strictPort: false,
  fs: { /* unchanged */ },
},
```

(Implementer: prefer ESM `import { loadEnv } from 'vite'` at the top — the snippet above shows the call site only.)

**`tools/dev-dashboard/package.json`** scripts:
- `"dashboard": "vite --host 127.0.0.1"` (drop `--port 5179`).
- `"preview": "vite preview --host 127.0.0.1"` (drop `--port 5179`).

**`backend/devtools/run_with_env.sh`** — source `.claude/env.ports` if present, before whatever it currently does (the file is short; the implementer reads it and prepends a `[ -f "$REPO_ROOT/.claude/env.ports" ] && . "$REPO_ROOT/.claude/env.ports"` line). Default fallback: if not present, leave env unchanged so existing callers passing `--port 8000` still work.

**`.gitignore` additions**:

```
# Per-worktree generated dev-stack config (per docs/tasks/per-worktree-ports/plan.md)
/.claude/launch.json
/.claude/env.ports
/frontend/.env.local
/tools/dev-dashboard/.env.local
```

**`devtools/refresh-dashboard-artifacts.sh:130`** — update the error string from
`"(requires backend on :8000 AND frontend on :5173/:3000)"` to
`"(requires backend on \$BACKEND_PORT AND frontend on \$FRONTEND_PORT; see .claude/env.ports)"`.

**`frontend/CLAUDE.md`** — change the line `Dev backend runs at \`http://localhost:8000\`.` to `Dev backend runs at the URL in \`$BACKEND_URL\` (see \`.claude/env.ports\`; default \`http://localhost:8000\`).`

**`tools/dev-dashboard/README.md`** — add one line under "Commands": `Per-worktree dashboard port lives in \`tools/dev-dashboard/.env.local\` (auto-generated; default 5179).`

**Root `CLAUDE.md`** — add this short section under "Project layout" (footnote, not a rewrite):

```
## Per-worktree dev ports
Each worktree's dev-stack ports (frontend / dashboard / backend) are auto-
generated by `githooks/post-checkout` (see `devtools/setup-worktree-ports.sh`).
Resolved values live in `.claude/launch.json`, `frontend/.env.local`,
`tools/dev-dashboard/.env.local`, and `.claude/env.ports` (all gitignored).
First clone still requires `./devtools/install-git-hooks.sh`. See
`docs/guides/per-worktree-ports-setup.md` to apply this pattern to other repos.
```

### 3.8 `postinstall` backup path

Two `package.json` edits so that a `npm ci` in a fresh worktree — where the post-checkout hook did not fire (e.g. fresh clone before `install-git-hooks.sh`) — still ends up with all four generated files:

- `frontend/package.json` → `"postinstall": "node -e \"require('node:child_process').spawnSync('bash', ['../devtools/setup-worktree-ports.sh'], { stdio: 'inherit' })\""`.
- `tools/dev-dashboard/package.json` → same, with `'../../devtools/setup-worktree-ports.sh'`.

Rationale for `spawnSync('bash', ...)`: avoids shell differences across platforms. Script is already idempotent, so running it twice (once from each `npm ci`) is safe.

### 3.9 FE/BE contract (unchanged, but now transport-agnostic)

The backend API contract does not change. What changes is how the **browser** reaches it:

- **Default dev flow (post-plan)**: browser → `http://localhost:<FRONTEND_PORT>/api/...` → vite dev-server proxy → `http://localhost:<BACKEND_PORT>/api/...`. Same-origin from the browser's perspective. CORS is a non-issue.
- **Explicit override**: setting `VITE_BACKEND_URL` in `frontend/.env.local` to e.g. `http://localhost:8000` reverts to direct cross-origin fetch. Used by storybook or consumers that don't proxy. Backend's CORS is `allow_origins=["*"]` for dev so this works for any port.
- **Playwright e2e**: `VITE_E2E_TESTING=true` → api.ts returns `http://localhost:18000`. Direct, cross-origin, matches existing wide-open CORS. Unchanged.

No request body / response shape changes. No new endpoints. No header changes.

### 3.10 Reproducible-setup guide — `docs/guides/per-worktree-ports-setup.md`

This guide is part of the deliverable. It captures the design pattern as a recipe so the user can apply it to other projects.

**Required structure** (the implementer fills in the prose; the reviewer checks the section list):

1. **Problem statement** — multiple worktrees, port conflicts, deterministic ports for tools like Claude Preview.
2. **Four moving parts** (generic, stack-agnostic):
   - **Parameterized code** — every place a port/URL is currently hard-coded must read from an env var with a sane default.
   - **Generator** — script that picks a free bank and renders templates atomically.
   - **Templates** — one per consumer file format (env files, JSON config, etc.).
   - **Trigger chain** — git `post-checkout` hook (primary) + `npm postinstall` (belt-and-suspenders) + manual `install-git-hooks.sh` bootstrap (first clone).
3. **Adoption checklist** (apply to your project):
   - [ ] Grep for hard-coded ports/URLs across:
     - Vite / Webpack / Next config files (`server.port`, `devServer.port`, `port`).
     - Backend launchers (uvicorn `--port`, gunicorn `--bind`, `app.run(port=)`).
     - HTTP client base URLs (axios `baseURL`, fetch wrappers).
     - Playwright / Cypress / Selenium `baseURL` and `webServer` blocks.
     - CORS `allow_origins` / `cors_allowed_origins`.
     - Docker compose port mappings (`"3000:3000"`).
     - IDE launch configs (`.vscode/launch.json`, JetBrains run configs).
     - README / DEMO / CONTRIBUTING narrative URLs (these may stay as documentation defaults).
   - [ ] Decide on env file layout per the trade-off in §3.2 — typically one `.env.local` per build tool's project root + one shell-source file for backend launchers, written from a single chosen offset by the generator.
   - [ ] Write a generator that:
     - Picks a free port bank with a portable probe (bash `/dev/tcp` is fine; document the macOS quirk that it requires actual `bash`, not `sh`).
     - Renders templates atomically (`.tmp` + `mv`).
     - Is idempotent (skip if all outputs present, force-regenerate via `--force`).
     - Has a `--print` mode for ad-hoc inspection.
     - Returns useful exit codes (`0/1/2/3` per §3.5) so callers can branch.
   - [ ] Add `githooks/post-checkout` (and any other relevant hooks: `post-merge`, `post-rewrite` if you want re-pickup after rebase).
   - [ ] Add `npm postinstall` entries on each Vite/Node project so `npm ci` re-runs the generator (closes the gap for first clone before hooks are wired).
   - [ ] Document the bootstrap step (`./devtools/install-git-hooks.sh`) prominently in the top-level README.
   - [ ] Add the generated files to `.gitignore` with leading `/` so only repo-root paths match.
4. **Bootstrap gap** — explicit explanation of the one manual step that is not automatable: on a brand-new clone, `core.hooksPath` is unset, so `post-checkout` does not fire. `npm ci` postinstall is the safety net but only runs if the dev installs deps before opening anything else. The clean fix is to direct first-time users to `./devtools/install-git-hooks.sh` in the README's "Setup" section.
5. **Concrete example appendix** — copy of this repo's chosen offsets, generator script outline, template file list, and the `.gitignore` block. Reader sees a working version end-to-end.
6. **Gotchas** — at minimum:
   - Vite env file location: `envDir` defaults to project root, not repo root. Don't try to share one repo-root file across multiple Vite projects without `envDir` overrides; instead generate one per project.
   - CORS: if your backend is not on the same origin as the frontend (i.e. you're not using the Vite proxy), `allow_origins` must list every per-worktree origin or use a regex / wildcard. This repo's backend uses `allow_origins=["*"]` for dev which sidesteps the problem.
   - Per-worktree smoke tests: if you have a Playwright/Cypress smoke that boots its own server (the dashboard's smoke uses `5279`), it needs its own port bank disjoint from the dev bank — don't reuse env vars from `.env.local` in those configs.
   - macOS bash 3.2 `/dev/tcp` quirk: only available when invoked via the `bash` interpreter (not `sh`); shebang must be `#!/usr/bin/env bash`. Documented in §3.5.
   - Idempotency check must look at **all** generated outputs; checking only one (e.g. `launch.json`) silently accepts partial state.

The guide is **not** a tutorial on this repo specifically — sections 1–4 and 6 are framework-agnostic; section 5 is the local example.

---

## 4. Test matrix

No backend domain / repository / API / PBT tests in scope — this plan changes zero backend runtime behavior. Test layers below cover the build-infra artifacts.

### 4.1 Generator subprocess tests — `backend/tests/tools/test_setup_worktree_ports.py` (NEW, pytest + pytest-subprocess)

**Decision**: drop bats-core. Tests live under `backend/tests/tools/` (alongside the existing capability-analyzer tests) and run via `pytest`, which is already wired into `run_all_agent_validations.sh`.

**Why pytest-subprocess** (vs. plain `subprocess.run` + asserts): the generator probes real TCP ports. We need to:
- run the real script (subprocess) for end-to-end assertions; and
- in a couple of cases, simulate "all ports busy" without binding 100 ports.

For the busy-port simulation we use real listeners (Python `socket.socket().bind()` + `listen()`) on the few ports we care about — that's deterministic and doesn't need pytest-subprocess. **`pytest-subprocess` (the package) is added to `[dependency-groups].dev` in `backend/pyproject.toml`** for the cases where we want to fake the script's invocation of `git rev-parse` (so the test doesn't depend on running inside a real git tree). Its `fp.register(["git", "rev-parse", "--show-toplevel"], stdout=tmp_path)` API is exactly what we need.

For each test, the harness creates a tmp dir via the `tmp_path` fixture, copies the four template files and the generator script into it, and invokes the script with `--worktree-root tmp_path`. Assertions are on file contents, exit codes, stdout/stderr.

| Test name | Verifies |
|---|---|
| `test_first_run_picks_offset_zero_when_all_ports_free` | With all three ports free, exit 0; `.claude/env.ports` contains `export FRONTEND_PORT=3000`, `export DASHBOARD_PORT=5179`, `export BACKEND_PORT=8000`, `export BACKEND_URL=http://localhost:8000`; `frontend/.env.local` has `FRONTEND_PORT=3000` and `BACKEND_URL=http://localhost:8000`; `tools/dev-dashboard/.env.local` has `DASHBOARD_PORT=5179`; `.claude/launch.json` parses as JSON and its two `port` fields equal `3000` and `5179`. |
| `test_first_run_renders_launch_json_with_no_unresolved_tokens` | After a run, `.claude/launch.json` contains the literal strings `"port": 3000` and `"port": 5179` and contains zero occurrences of `${`. |
| `test_first_run_renders_all_three_env_files_with_no_unresolved_tokens` | Same check for the three `.env*` files: contain the chosen integers, contain zero `${`. |
| `test_idempotent_second_run_is_noop_when_all_artifacts_exist` | Run once, capture mtimes of all four output files; run again with no flags; stdout contains `"skipping"`; all four mtimes unchanged; exit 0. |
| `test_force_flag_regenerates_when_all_artifacts_exist` | Run once; sleep 1.1s (mtime granularity); run again with `--force`; all four mtimes increase; ports unchanged because same offset still free. |
| `test_skips_occupied_frontend_port_picks_next_offset` | Bind 127.0.0.1:3000 with a Python `socket` listener; run generator; offset selected is 10; `frontend/.env.local` has `FRONTEND_PORT=3010`; backend env has `BACKEND_URL=http://localhost:8010`. |
| `test_skips_occupied_dashboard_port_picks_next_offset` | Bind 5179, run; `tools/dev-dashboard/.env.local` has `DASHBOARD_PORT=5189`. |
| `test_skips_occupied_backend_port_picks_next_offset` | Bind 8000, run; offset=10. |
| `test_skips_offset_when_only_one_of_three_is_busy` | Bind 5189 only; expect generator to reject offset=10 (because dashboard port 5189 is busy at offset 10) and pick offset=20 (since 3000/5179/8000 are also free, but they were rejected at offset 0 only if we ALSO bind one of those — refine: bind 5179 AND 5189, expect offset=20). |
| `test_print_mode_does_not_write_files` | `--print` prints one line containing `FRONTEND_PORT=3000 DASHBOARD_PORT=5179 BACKEND_PORT=8000` to stdout; none of the four output files are created. |
| `test_missing_launch_template_exits_one_with_clear_message` | Remove `.claude/launch.json.template` before running; stderr contains the word `template`; exit=1; no output files created (atomic-write guarantee). |
| `test_missing_frontend_env_template_exits_one_with_clear_message` | Same for `.claude/env.frontend.template`. |
| `test_missing_dashboard_env_template_exits_one_with_clear_message` | Same for `.claude/env.dashboard.template`. |
| `test_missing_ports_env_template_exits_one_with_clear_message` | Same for `.claude/env.ports.template`. |
| `test_template_with_unknown_token_exits_one_with_clear_message` | Inject a `${MYSTERY}` into one template; generator exits 1; stderr mentions `unresolved` and `MYSTERY` and the template file name; no output files written. |
| `test_no_free_offset_within_range_exits_two` | Bind every offset's bank up to a low test ceiling (use a test-only env var the generator honors, e.g. `WORKTREE_PORTS_MAX_OFFSET=20`, OR pytest-subprocess-fake the bash probe call) so all candidates fail; exit=2; stderr contains `"could not find a free port bank"`. |
| `test_worktree_root_flag_writes_files_into_that_root` | Pass `--worktree-root /tmp/alt`; files appear under `/tmp/alt/.claude/...`, `/tmp/alt/frontend/.env.local`, `/tmp/alt/tools/dev-dashboard/.env.local`; nothing under `$PWD`. |
| `test_unknown_flag_exits_three_with_usage` | `--nonsense` → exit 3, stderr contains `"usage"`. |
| `test_atomic_write_no_partial_on_failure` | Pre-create `.claude/` as `chmod 555`; expect exit 1; assert that no `*.tmp` and no final output files exist anywhere under the tmp root. |
| `test_stdout_log_line_has_expected_prefix_and_ports` | Stdout contains exactly one line matching the regex `^\[setup-worktree-ports\] offset=0 frontend=3000 dashboard=5179 backend=8000$`. |
| `test_idempotency_check_requires_all_four_outputs` | Pre-create only `.claude/launch.json` (not the three env files); run without `--force`; generator regenerates rather than skipping (because the all-four check fails); assert all four files now exist. |
| `test_runs_without_git_when_worktree_root_is_explicit` | Run with `--worktree-root tmp_path` outside a git tree (no `.git`); succeeds; `git rev-parse` is not invoked (asserted via pytest-subprocess `fp.register` recording invocations). |

**Helper module**: `backend/tests/tools/_port_helpers.py` (private — leading underscore so pytest doesn't collect it):
- `bind_listener(port: int) -> socket.socket` — binds and listens on 127.0.0.1:port; returns the socket. Caller closes via `with` or fixture teardown.
- `prepare_worktree(tmp_path: Path) -> Path` — copies the four templates and the generator script from the repo into `tmp_path`; returns `tmp_path`.

### 4.2 Hook tests — `backend/tests/tools/test_post_checkout_hook.py` (NEW, pytest)

| Test name | Verifies |
|---|---|
| `test_worktree_add_triggers_generator_and_creates_outputs` | In a tmp git repo where `core.hooksPath=githooks` is set, `git worktree add ../w2` creates `../w2/.claude/launch.json`, `../w2/.claude/env.ports`, `../w2/frontend/.env.local`, `../w2/tools/dev-dashboard/.env.local`. (Uses `subprocess.run` with `cwd=tmp_path`; the test sets up a minimal repo with the four templates + generator + hook copied from the repo under test.) |
| `test_checkout_in_existing_worktree_is_noop` | In a worktree that already has all four artifacts, `git checkout -b feature/x` runs the hook; the generator's idempotency check keeps all four mtimes stable. |
| `test_hook_failure_does_not_block_checkout` | Force the generator to fail (e.g. delete a template); `git checkout -b feature/y` exits 0; stderr from the hook contains the generator's error message; the working tree advances to the new branch. |

### 4.3 Frontend api.ts unit tests — `frontend/tests/unit/services/api.base-url.test.ts` (NEW, Vitest)

The frontend has no unit-test infra today. This plan adds a minimal Vitest setup:

- Add `vitest`, `jsdom`, `@vitest/ui` to `frontend/devDependencies`.
- Add `frontend/vitest.config.ts` (env: `jsdom`, globals: true, setupFiles: `['tests/unit/setup.ts']`).
- Add `npm --prefix frontend run test` script → `vitest run`.
- **Update the `validate-frontend` skill** to read `lint + typecheck + test + e2e` (was `lint + typecheck + e2e`). The skill file lives under `.claude/skills/validate-frontend/`; the implementer updates the skill text to match. (Note: `docs/architecture/principles.md` line 53 says the same three; update there too.)

| Test name | Verifies |
|---|---|
| `test_resolve_base_url_returns_e2e_port_when_vite_e2e_testing_true` | With `VITE_E2E_TESTING='true'`, both `VITE_BACKEND_URL` set and unset, returns `'http://localhost:18000'`. |
| `test_resolve_base_url_returns_vite_backend_url_when_set_and_e2e_unset` | With `VITE_E2E_TESTING` unset and `VITE_BACKEND_URL='http://example.test:9000'`, returns `'http://example.test:9000'`. |
| `test_resolve_base_url_returns_empty_string_when_both_unset` | With neither env var set (or both empty strings), returns `''` (relative — relies on Vite proxy). This covers the most common dev path. |
| `test_resolve_base_url_returns_empty_string_when_backend_url_is_empty_string` | With `VITE_E2E_TESTING` unset and `VITE_BACKEND_URL=''` (the literal empty string our `define` injects), returns `''`. Distinct from the previous case because here `VITE_BACKEND_URL` is *defined* to empty, not undefined. |
| `test_resolve_base_url_precedence_e2e_wins_over_backend_url` | With both `VITE_E2E_TESTING='true'` AND `VITE_BACKEND_URL='http://x:1'`, returns `'http://localhost:18000'` (e2e branch first). |
| `test_api_client_issues_relative_paths_when_base_url_empty` | Stub `axios.create` so the constructor records `baseURL`; with both env vars unset, `apiClient.getProjects()` (or any method) results in a request to URL `/api/projects` with no host. |
| `test_api_client_prefixes_base_url_when_configured` | Same stubbing; with `VITE_BACKEND_URL='http://example.test:9000'`, the request URL is `http://example.test:9000/api/projects`. |

### 4.4 Frontend vite-config unit tests — `frontend/tests/unit/vite-config.test.ts` (NEW, Vitest)

Imports `frontend/vite.config.ts`'s default export (a function `({mode}) => config`) and asserts on the resolved object. Each test sets/clears `process.env` then calls the factory.

| Test name | Verifies |
|---|---|
| `test_vite_config_frontend_port_defaults_to_3000_when_env_unset` | `delete process.env.FRONTEND_PORT`; resulting `config.server.port === 3000`. |
| `test_vite_config_frontend_port_reads_env` | `process.env.FRONTEND_PORT='3010'` → `server.port === 3010`. |
| `test_vite_config_frontend_port_falls_back_on_non_numeric_env` | `process.env.FRONTEND_PORT='abc'` → `server.port === 3000` (because `Number('abc')` is `NaN`, and the implementation must use `Number.isFinite` to detect this). |
| `test_vite_config_frontend_port_falls_back_on_zero_env` | `process.env.FRONTEND_PORT='0'` → `server.port === 3000` (because `> 0` filter rejects 0). |
| `test_vite_config_proxy_default_backend_url_is_localhost_8000` | `delete process.env.BACKEND_URL`; `server.proxy['/api'].target === 'http://localhost:8000'`. |
| `test_vite_config_proxy_reads_backend_url_env` | `BACKEND_URL='http://localhost:8010'` → all three proxy targets equal that string. |
| `test_vite_config_proxy_routes_cover_api_health_auth` | `Object.keys(server.proxy)` is exactly `['/api', '/health', '/auth']`. (Guard against silently dropping `/auth`, which would break login.) |
| `test_vite_config_define_sets_vite_backend_url_to_empty_string_literal` | `config.define['import.meta.env.VITE_BACKEND_URL'] === '""'` (JSON-stringified empty string). |

### 4.5 Dashboard vite-config unit tests — `tools/dev-dashboard/tests/unit/vite.port.test.ts` (NEW, Vitest)

The dashboard already has a Vitest suite. The dashboard's vite config is built by an `async buildConfig()` that's exported as a top-level `await`-resolved promise. The test imports the module, awaits the default export, and inspects `server.port`. Each test sets/clears `process.env.DASHBOARD_PORT` then re-imports (use Vitest's `vi.resetModules()` between tests).

| Test name | Verifies |
|---|---|
| `test_dashboard_vite_port_defaults_to_5179_when_env_unset` | `delete process.env.DASHBOARD_PORT`; resulting `server.port === 5179`. |
| `test_dashboard_vite_port_reads_dashboard_port_env` | `process.env.DASHBOARD_PORT='5189'` → `server.port === 5189`. |
| `test_dashboard_vite_port_falls_back_on_non_numeric_env` | `DASHBOARD_PORT='abc'` → `server.port === 5179` (drives `Number.isFinite` guard in the implementation). |
| `test_dashboard_vite_port_falls_back_on_zero_env` | `DASHBOARD_PORT='0'` → `server.port === 5179`. |

### 4.6 Postinstall smoke — `backend/tests/tools/test_postinstall_backup.py` (NEW, pytest)

| Test name | Verifies |
|---|---|
| `test_npm_ci_in_fresh_worktree_triggers_postinstall_and_generates_outputs` | In a tmp dir containing a minimal `frontend/package.json` (with the postinstall) + the generator + the four templates (symlinked into place), run `npm ci --ignore-scripts=false`; after completion, all four output files exist and `.claude/launch.json` is valid JSON. (Skip with `pytest.skip` if `npm` is not on PATH — leaves a clear message.) |
| `test_npm_ci_when_outputs_already_exist_does_not_clobber_them` | Pre-create all four artifacts with custom ports. Run `npm ci`. All four files' mtimes and contents unchanged (idempotency check fires). |

### 4.7 Backwards-compat — runtime smoke under default ports

Two assertions to lock G4. Implemented as pytest tests that boot the real Vite servers, since the generator-test framework already lives under `backend/tests/tools/`.

| Test name | File | Verifies |
|---|---|---|
| `test_frontend_vite_dev_default_port_when_no_env_file` | `backend/tests/tools/test_default_ports_smoke.py` | In a tmp dir with NO `frontend/.env.local`, run `npm --prefix <tmp>/frontend run dev` (background subprocess); poll `bash /dev/tcp/127.0.0.1/3000` (or `socket.connect`) until reachable or 15s timeout; SIGTERM the process. Assert connection succeeded. (Skip if `npm` not on PATH.) |
| `test_dashboard_vite_default_port_when_no_env_file` | same | Same pattern, `npm --prefix <tmp>/tools/dev-dashboard run dashboard`, port 5179. |

(`api.ts` empty-base-URL behavior is covered by §4.3 — no duplicate test here.)

### 4.8 End-to-end preservation — existing Playwright run

No new test files. Confirm via execution:
- `cd frontend && npm run e2e` still passes. The chromium project (uses `vite.config.e2e.ts` → `:13001` + `VITE_E2E_TESTING=true` → `:18000`) is unaffected.
- `cd frontend && npm run e2e:scenarios` still produces walkthrough artifacts (verifies `refresh-dashboard-artifacts.sh`'s Step 3 path).

### 4.9 Scenario test

**Not required.** Per principles §Scenario coverage rule, scenario tests are required for "user-facing features"; backend-only and pure refactors are exempt. This is dev-infrastructure with no user-visible UI affordance — the exemption applies. Explicitly excluded so a reviewer doesn't flag absence.

### 4.10 Capability analyzer

No capability changes (zero backend route changes). `cd backend && ./devtools/run_with_env.sh uv run python -m project_management_crud_example.tools.analyze_capabilities` must still exit 0 with no diff vs `baseline.json`. Listed in §9 sign-off.

### 4.11 Reproducible-setup guide review

The implementer writes `docs/guides/per-worktree-ports-setup.md` per §3.10. The reviewer (and the §9 sign-off) confirms it contains all six sections enumerated in §3.10 and that section 5 (concrete example appendix) reflects the ports/files actually shipped in this repo.

---

## 5. Test fixtures and helpers

### 5.1 Pytest helpers — `backend/tests/tools/_port_helpers.py` (NEW, private module)

- `bind_listener(port: int) -> socket.socket` — `socket.socket(AF_INET, SOCK_STREAM); s.bind(('127.0.0.1', port)); s.listen(1)`; returns the socket. Tests own teardown via `with contextlib.closing(...)`.
- `prepare_worktree(tmp_path: Path) -> Path` — copies the four template files from the actual repo (`docs/architecture/principles.md`-resolved repo root via `Path(__file__).parents[3]`) into `tmp_path/.claude/`, copies `devtools/setup-worktree-ports.sh` into `tmp_path/devtools/`, returns `tmp_path`.
- `run_generator(worktree: Path, *args: str) -> subprocess.CompletedProcess` — wraps `subprocess.run([str(worktree / 'devtools' / 'setup-worktree-ports.sh'), '--worktree-root', str(worktree), *args], capture_output=True, text=True)`.

### 5.2 Frontend Vitest fixtures (NEW)

- `frontend/vitest.config.ts` — `environment: 'jsdom'`, `globals: true`, `setupFiles: ['tests/unit/setup.ts']`.
- `frontend/tests/unit/setup.ts` — uses `vi.stubEnv` / `vi.unstubAllEnvs` in `beforeEach`/`afterEach` to reset `import.meta.env` between tests.

### 5.3 No backend domain/repository fixtures

No backend product-code changes → no pytest fixtures of the usual kind.

---

## 6. Edge cases covered

- **All three default ports busy** — generator picks +10. Covered by `test_skips_occupied_*_picks_next_offset` × 3.
- **One-of-three busy** — `test_skips_offset_when_only_one_of_three_is_busy`.
- **All offsets exhausted** — generator exits 2 with actionable message; `test_no_free_offset_within_range_exits_two`.
- **Two simultaneous worktree-add invocations** — both probe the same instant, both pick offset=0, the loser's server fails to bind. Documented as accepted behavior in §8 risks; user re-runs `--force`.
- **Generator run from subdir** — `git rev-parse --show-toplevel` resolves; covered indirectly because `test_runs_without_git_when_worktree_root_is_explicit` exercises the explicit path and the hook test exercises the implicit path.
- **Templates missing** — four separate tests, one per template file (`test_missing_*_template_exits_one_with_clear_message`).
- **Read-only `.claude/`** — `test_atomic_write_no_partial_on_failure`.
- **Partial pre-existing output** — `test_idempotency_check_requires_all_four_outputs`.
- **Non-numeric / zero env values for ports** — covered in §4.4 and §4.5 fall-back tests.
- **macOS bash 3.2 `/dev/tcp`** — generator uses `#!/usr/bin/env bash` shebang explicitly. Documented in §3.5 inline comment.
- **CORS collateral** — backend uses `allow_origins=["*"]` (verified at planning time in `backend/project_management_crud_example/app.py:102`). No CORS work required for any port. Listed in §8 as a closed risk.
- **Claude Preview lifecycle** — Preview caches the port. After a `--force` regenerate that picks a different offset, the user must stop and re-start the preview. Called out in CLAUDE.md and the guide.
- **Symlinked worktree paths on macOS** (`/private/var` vs `/var`) — `git rev-parse --show-toplevel` returns canonical path; non-issue.
- **Vite auto-loaded `.env.local`** — Vite's default `envDir = root` means each Vite project's own `.env.local` is auto-loaded. Our explicit `loadEnv(mode, process.cwd(), '')` in `vite.config.ts` makes the same vars available to the config file (server-side); `define` controls what reaches the bundle.
- **Playwright config overrides** — `vite.config.e2e.ts` defines its own `server` block with `port: 13001`; no conflict with the dev bank.
- **Postinstall during `npm ci` re-runs the generator twice** (once per package) — accepted; idempotency check makes the second a no-op (~50ms).

---

## 7. Implementation order

1. **Templates + generator** (§3.3, §3.4, §3.5): write the four template files in `.claude/` and `devtools/setup-worktree-ports.sh`. `chmod +x` the generator.
2. **Pytest helpers** (§5.1): add `backend/tests/tools/_port_helpers.py`.
3. **Add `pytest-subprocess` to `backend/pyproject.toml`** under `[dependency-groups].dev`.
4. **Generator tests** (§4.1) — `backend/tests/tools/test_setup_worktree_ports.py`. Must pass before moving on.
5. **Hook** (§3.6): add `githooks/post-checkout`. Verify `chmod +x` happens via `./devtools/install-git-hooks.sh`.
6. **Hook tests** (§4.2) — `backend/tests/tools/test_post_checkout_hook.py`.
7. **`.gitignore`** (§3.7): add the four entries.
8. **`backend/devtools/run_with_env.sh`** (§3.7): add the source-if-present line.
9. **Frontend Vitest infra** (§5.2): add `vitest`, `jsdom` deps; `vitest.config.ts`; `tests/unit/setup.ts`; `"test"` script in `frontend/package.json`.
10. **`frontend/src/services/api.ts`** edit (§3.7) + api-base tests (§4.3). Tests must pass.
11. **`frontend/vite.config.ts`** edit (§3.7) + vite-config tests (§4.4). Drop `--port 3000` from `frontend/package.json` `dev` script.
12. **`tools/dev-dashboard/vite.config.ts`** edit (§3.7) + dashboard vite-port tests (§4.5). Drop `--port 5179` from dashboard `package.json` `dashboard` and `preview` scripts.
13. **Default-port smoke** (§4.7): `backend/tests/tools/test_default_ports_smoke.py`.
14. **`postinstall`** entries on both `package.json`s (§3.8) + smoke test (§4.6).
15. **`devtools/refresh-dashboard-artifacts.sh`** error-string update (§3.7).
16. **Doc edits** (§3.7): root `CLAUDE.md`, `frontend/CLAUDE.md`, `tools/dev-dashboard/README.md`.
17. **Update `validate-frontend` skill text** (§4.3) — add `npm run test` to the contract; update `docs/architecture/principles.md:53` to match.
18. **Write the reproducible-setup guide** — `docs/guides/per-worktree-ports-setup.md` per §3.10. Mandatory deliverable.
19. **Full validation suite**:
    - `cd backend && ./devtools/run_all_agent_validations.sh` — green (now includes the new generator/hook/postinstall/smoke tests).
    - `npm --prefix frontend run lint && npm --prefix frontend run typecheck && npm --prefix frontend run test && npm --prefix frontend run e2e` (the new four-command contract).
    - `npm --prefix tools/dev-dashboard run typecheck && npm --prefix tools/dev-dashboard run lint && npm --prefix tools/dev-dashboard run test -- --run && npm --prefix tools/dev-dashboard run smoke`.
    - `./devtools/refresh-dashboard-artifacts.sh` — manual spot-check; all artifacts produced.
    - Capability analyzer exit 0 (no drift) — §4.10.
20. **Manual two-worktree exercise**: create a sibling worktree (`git worktree add`); confirm its `.claude/launch.json` and three env files generate with a non-zero offset if the first worktree is running; boot both stacks concurrently; hit both frontends in a browser.
21. **Commit** at natural checkpoints per repo policy.

---

## 8. Risks / open questions

- **Risk — `core.hooksPath` ordering on first clone.** On a fresh `git clone <repo>`, `post-checkout` does NOT fire because `core.hooksPath` is not yet set. Mitigations: (a) the `postinstall` backup in both `package.json`s fires on first `npm ci`; (b) CLAUDE.md and the new guide document `./devtools/install-git-hooks.sh` as the bootstrap step. Truly zero-touch first-clone is not achievable without external tooling and is out of scope.
- **Risk — race between two simultaneous `git worktree add` invocations.** Both hooks probe within the same few ms, both pick offset=0, conflicting writes. Accepted: the second server to start fails to bind; user re-runs `--force`. Not worth flock'ing; if it becomes common, revisit with a file lock on `.claude/.port-lock`.
- **Risk — remaining hardcodes of `localhost:8000` / `:3000` in narrative docs.** Plan decisions:
  - `backend/project_management_crud_example/bootstrap_rich_data.py:441,444` — hint strings for humans. Leave as-is (the user sees their actual ports in their terminal).
  - `README.md`, `DEMO_SETUP.md`, `frontend/README.md` — narrative URLs. Leave the bodies; CLAUDE.md / `frontend/CLAUDE.md` / dashboard README pointers (added per §3.7) point readers at `.claude/env.ports` and `.env.local`. Full README rewrite is out of scope.
  - `devtools/refresh-dashboard-artifacts.sh:130` — error string updated per §3.7.
  - `tools/dev-dashboard/playwright.config.ts:7` — `DASHBOARD_PORT = 5279`. Intentionally separate from dev bank (dashboard's smoke runs its own server). Untouched.
  - `frontend/playwright.config.ts:63` — `--port 18000` for e2e backend. Untouched (separate bank).
  - `frontend/vite.config.e2e.ts:9` — `:13001` for e2e frontend. Untouched (separate bank).
- **Closed — backend CORS for non-3000 origins.** Verified at planning time: `backend/project_management_crud_example/app.py:102` has `allow_origins=["*"]` for dev. Any per-worktree port works without CORS edits. No action needed.
- **Risk — `validate-frontend` skill expansion.** Adding `npm run test` (Vitest) to the frontend validation set is a new zero-tolerance gate. Update the skill file *and* the principles doc line that lists the three commands. CI pipelines (if any) pinned to the old three keep passing; the new step only runs when validate-frontend is invoked.
- **Closed — env file location.** Decided in §3.2: option (a) — one `.env.local` per Vite project + one `.claude/env.ports` for backend, all generated atomically from one chosen offset.
- **Open question — `frontend/package.json` `"dev": "vite --port 3000"` hardcoding.** Plan removes `--port 3000` so the vite config (and via it, env) is the sole source of truth. `npx vite` direct invocation falls back to vite's default 3000 (matches our fallback).
- **Open question — `postinstall` runs on every `npm ci` / `npm install`.** Acceptable because the generator is idempotent (skip path is ~50ms). Not worth gating.
- **Closed — bats-core dependency.** Dropped per orchestrator decision; tests now use pytest-subprocess and live under `backend/tests/tools/`. They run inside `run_all_agent_validations.sh` automatically.

---

## 9. Sign-off

- [ ] User approved plan — date/note
- [ ] Templates + generator committed; pytest-subprocess generator tests green (`backend/tests/tools/test_setup_worktree_ports.py`)
- [ ] Hook committed; hook tests green; manual two-worktree smoke verifies G1 + G2 + G3
- [ ] Frontend Vitest infra committed; api.ts + vite-config tests green
- [ ] Dashboard vite-config edit committed; dashboard vite-port tests green
- [ ] Backwards-compat default-port smoke green (G4)
- [ ] `npm run e2e` (frontend) still green (verifies G5)
- [ ] `./devtools/refresh-dashboard-artifacts.sh` still produces all tabs' artifacts
- [ ] `cd backend && ./devtools/run_all_agent_validations.sh` green (includes new tests)
- [ ] `validate-frontend` skill text updated to `lint + typecheck + test + e2e`; principles.md line 53 updated to match
- [ ] Capability analyzer exit 0 (no drift) — §4.10
- [ ] CLAUDE.md + `frontend/CLAUDE.md` + `tools/dev-dashboard/README.md` pointers added
- [ ] **`docs/guides/per-worktree-ports-setup.md` written**, contains all six sections from §3.10, and the appendix reflects the actually-shipped files
- [ ] `code-reviewer` sign-off (must explicitly confirm the guide is present and complete)

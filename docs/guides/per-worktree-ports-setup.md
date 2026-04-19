# Per-worktree dev ports: a reproducible recipe

A pattern you can apply to any full-stack repo to let multiple `git worktree`s
run their dev stacks concurrently on 127.0.0.1 without port collisions — and
to keep tools that cache port numbers (IDE launch configs, preview MCPs,
agent integrations) in sync with whichever bank each worktree ends up on.

This guide is stack-agnostic. Sections 1–4 and 6 describe the pattern; section
5 is a concrete appendix from the example repo this guide ships in.

---

## 1. Problem statement

Running two git worktrees of the same repo at once means running two of
everything: two Vite dev servers, two API servers, two dashboards. If each
server hardcodes `127.0.0.1:3000` / `:8000` / etc., only one worktree can
boot at a time. Meanwhile, tools that need a fixed port to point at — IDE
launch configs, browser-preview MCP integrations, containerized webhooks —
can't just "let the OS pick a port" because they cache the number and need
it to be deterministic per-worktree.

You want:

- Each worktree gets its own port bank, assigned the first time the worktree
  is used and stable from then on.
- Banks are probed against actually-free ports — no scraping `lsof` or
  forcing specific numbers.
- Generation is zero-touch on `git worktree add`. First-clone bootstrap
  (wiring `core.hooksPath`) happens inside the same `npm ci` the developer
  already has to run to get `node_modules` — no separate manual step.
- Tooling that caches ports sees a file it can re-read. A browser preview
  MCP just points at `.claude/launch.json`; it does not need to know about
  git or probing.
- Ports fall back to the historical defaults when no generated file is
  present, so a fresh clone still boots.

---

## 2. Four moving parts

Regardless of stack, the pattern decomposes into the same four things.

### 2.1 Parameterized code

Every place that currently says `port: 3000` or `http://localhost:8000` has to
read from an env var (or equivalent indirection) with a sane default if the
env var is absent. Common offenders:

- Vite / Webpack / Next dev-server configs (`server.port`, `devServer.port`).
- Backend launchers (uvicorn `--port`, gunicorn `--bind`, `app.run(port=)`).
- HTTP clients (`axios.baseURL`, fetch wrappers, generated SDK clients).
- Playwright / Cypress / Selenium `baseURL` and `webServer` blocks.
- CORS `allow_origins` / `cors_allowed_origins`.
- `docker-compose.yml` port mappings.
- IDE launch configs (`.vscode/launch.json`, JetBrains run configs).
- AI / browser-preview MCP config files.

### 2.2 Generator

A script — one file, few hundred lines — that:

1. Probes 127.0.0.1 for the first free bank via a portable mechanism.
2. Renders each consumer's preferred config file atomically.
3. Is idempotent: rerun it with no flags and it's a no-op if all outputs
   already exist; rerun with `--force` and it recomputes.
4. Uses a portable port probe. Bash's built-in `/dev/tcp` redirection is
   enough on macOS + Linux (see §6 for the caveat).

### 2.3 Templates

One template per consumer file format. Common shapes:

- dotenv-style `KEY=VALUE` per line, for Vite auto-loaded `.env.local`.
- `export KEY=VALUE` per line, for backend launcher shells that `source` the file.
- JSON, for IDE launch configs and MCP definitions.

Templates contain simple `${VAR}` tokens that the generator substitutes.

### 2.4 Trigger chain

The generator needs to run at a few natural points in a developer's workflow:

- **`post-checkout` git hook (primary after bootstrap)** — fires on
  `git worktree add`, on `git checkout`, and after a `git clone` that has
  `core.hooksPath` already wired.
- **`postinstall` npm script (primary on first install + bootstrap)** —
  fires on `npm ci` in each Node-managed package. It does TWO things, in
  order: (1) runs `install-git-hooks.sh` to wire `core.hooksPath=githooks`,
  (2) runs the port generator to write the artifacts. Because `npm ci` is
  mandatory to get `node_modules` anyway, this closes the first-clone gap
  with no extra developer action — the one command they already had to run
  bootstraps everything.

---

## 3. Adoption checklist

Apply to your project:

- [ ] Grep for hard-coded ports and URLs across:
  - [ ] Vite / Webpack / Next config files (`server.port`, `devServer.port`, `port`).
  - [ ] Backend launchers (uvicorn `--port`, gunicorn `--bind`, `app.run(port=)`).
  - [ ] HTTP client base URLs (axios `baseURL`, fetch wrappers, SDK constructors).
  - [ ] Playwright / Cypress / Selenium `baseURL` and `webServer` blocks.
  - [ ] CORS `allow_origins` / `cors_allowed_origins`.
  - [ ] Docker compose port mappings (`"3000:3000"`).
  - [ ] IDE launch configs (`.vscode/launch.json`, JetBrains run configs).
  - [ ] README / DEMO / CONTRIBUTING narrative URLs — these may stay as
        documentation defaults; pointers-to-`.env.local` are enough.
- [ ] Decide on env-file layout: typically one `.env.local` per build tool's
      project root + one shell-source file for backend launchers, written
      from a single chosen offset by the generator.
- [ ] Write a generator that:
  - [ ] Picks a free port bank with a portable probe (`bash /dev/tcp` is
        fine; document the macOS quirk that requires a real `bash` shebang,
        not `sh`).
  - [ ] Renders templates atomically (`*.tmp` + `mv`).
  - [ ] Is idempotent (skip if all outputs present, force-regenerate via `--force`).
  - [ ] Has a `--print` mode for ad-hoc inspection.
  - [ ] Returns useful exit codes so callers can branch
        (`0`=ok, `1`=template/IO error, `2`=no free bank, `3`=CLI usage).
- [ ] Add `githooks/post-checkout` (and optionally `post-merge`,
      `post-rewrite` if you want re-pickup after rebase). Do NOT `set -e` —
      a generator failure must not abort the git operation itself.
- [ ] Add `npm postinstall` entries on each Vite / Node project that run,
      in order, `install-git-hooks.sh` then `setup-worktree-ports.sh`.
      Closes the first-clone gap inside the `npm ci` the developer already
      has to run; no separate manual bootstrap step needed.
- [ ] Add the generated files to `.gitignore` with a leading `/` so only
      repo-root paths match.

---

## 4. The bootstrap: piggyback on `npm ci`

On a brand-new `git clone`, `core.hooksPath` is unset by default, so
`post-checkout` will not fire for anything. Git refuses to auto-trust
repo-tracked hooks without an explicit opt-in — that's a security feature.

The trick: the first `npm ci` is mandatory anyway (no `node_modules` means
nothing runs), so make `npm ci` do the bootstrap. Put two commands in the
`postinstall` of each Vite / Node project, in order:

1. `install-git-hooks.sh` — sets `core.hooksPath=githooks` (and, if the repo
   opts into `extensions.worktreeConfig`, sweeps stale per-worktree
   `core.hookspath` overrides — see the gotchas section).
2. `setup-worktree-ports.sh` — writes `launch.json` + env files for this
   worktree.

Both are idempotent, so re-installs are cheap (~50ms). Result: no
developer-facing "remember to run install-git-hooks.sh" step. After `npm ci`
has happened once in the clone, every subsequent `git worktree add`
auto-bootstraps via `post-checkout` without any manual intervention.

The single remaining requirement — that the developer run `npm ci` at some
point — is something they have to do regardless of this pattern, so the
pattern adds zero cognitive load.

---

## 5. Concrete example (this repo)

Port bank in this repo:

| Consumer | Default | Offset source |
|---|---|---|
| Frontend (Vite) | 3000 | `3000 + N` |
| Dev-dashboard (Vite) | 5179 | `5179 + N` |
| Backend (uvicorn) | 8000 | `8000 + N` |

Where `N` is the first offset in `{0, 10, 20, …, 990}` whose triple of ports
is free on 127.0.0.1. This gives 100 disjoint worktrees before we'd need to
expand the range.

### 5.1 Files

Committed:

- `.claude/launch.json.template` — JSON with `${FRONTEND_PORT}` / `${DASHBOARD_PORT}`.
- `.claude/env.frontend.template` — `FRONTEND_PORT=` / `BACKEND_URL=`.
- `.claude/env.dashboard.template` — `DASHBOARD_PORT=`.
- `.claude/env.ports.template` — `export …=` lines for shell source.
- `devtools/setup-worktree-ports.sh` — the generator.
- `githooks/post-checkout` — thin dispatcher to the generator.
- `.gitignore` — adds the four generated paths so they never get committed.

Generated per worktree (gitignored):

- `.claude/launch.json` — read by Claude Preview MCP's `preview_start`.
- `.claude/env.ports` — `source`d by `backend/devtools/run_with_env.sh`
  so uvicorn sees `$BACKEND_PORT`.
- `frontend/.env.local` — Vite auto-loads; `FRONTEND_PORT`, `BACKEND_URL`.
- `tools/dev-dashboard/.env.local` — Vite auto-loads; `DASHBOARD_PORT`.

### 5.2 `.gitignore` block

```
# Per-worktree generated dev-stack config (per docs/tasks/per-worktree-ports/plan.md)
/.claude/launch.json
/.claude/env.ports
/frontend/.env.local
/tools/dev-dashboard/.env.local
```

### 5.3 Generator contract

```
devtools/setup-worktree-ports.sh [--force] [--print] [--worktree-root <path>]
```

Exit codes:

| Code | Meaning |
|---|---|
| 0 | Wrote files OR skipped idempotently OR `--print` succeeded |
| 1 | Template missing / unwritable path / templating failure |
| 2 | No free port bank found within `[0..990 step 10]` |
| 3 | Invalid CLI args |

Stdout on success: one line `[setup-worktree-ports] offset=<N> frontend=<P1> dashboard=<P2> backend=<P3>`.

### 5.4 Hook dispatcher

```bash
#!/usr/bin/env bash
# githooks/post-checkout
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
[ -z "$REPO_ROOT" ] && exit 0
GENERATOR="$REPO_ROOT/devtools/setup-worktree-ports.sh"
[ -x "$GENERATOR" ] || exit 0
"$GENERATOR" --worktree-root "$REPO_ROOT" || {
  echo "[post-checkout] setup-worktree-ports failed (exit $?); checkout proceeds anyway." >&2
}
exit 0
```

Note: no `set -e` — a generator failure must not abort the git checkout.

### 5.5 Postinstall hook (example from `frontend/package.json`)

```json
"postinstall": "node -e \"const { spawnSync } = require('node:child_process'); ['../devtools/install-git-hooks.sh', '../devtools/setup-worktree-ports.sh'].forEach(s => spawnSync('bash', [s], { stdio: 'inherit' }))\""
```

Two shell scripts run in order on every `npm ci`: `install-git-hooks.sh`
wires `core.hooksPath=githooks` (and sweeps stale per-worktree overrides),
then `setup-worktree-ports.sh` generates the port artifacts. Both are
idempotent, so re-runs are cheap.

Why `spawnSync('bash', ...)`? Because npm runs scripts in the package's
directory via its own minimal shell; portable bash invocation via Node's
`child_process` avoids Windows/PowerShell surprises.

---

## 6. Gotchas

- **Vite `envDir` defaults to the project root, not the repo root.** Don't
  try to share one repo-root `.env.local` across multiple Vite projects
  without `envDir` overrides — it's brittle (empty-prefix `loadEnv` leaks
  secrets; cwd-relative paths break inconsistently; IDE tooling loses track).
  Generate one per Vite project.
- **CORS collateral.** If your backend is not same-origin with the frontend
  (i.e. you skipped the Vite proxy), `allow_origins` must list every
  per-worktree origin or use a permissive wildcard. The example repo uses
  `allow_origins=["*"]` in dev, which sidesteps the problem.
- **Per-worktree smoke tests have their own bank.** If you have a
  Playwright / Cypress smoke suite that boots its own server, give it a
  separate port bank, disjoint from the dev bank (the example repo's
  dashboard smoke uses `5279`; e2e backend uses `18000`). Don't reuse env
  vars from `.env.local` inside those configs.
- **macOS bash 3.2 `/dev/tcp` quirk.** Bash's TCP redirection is hard-coded
  into bash itself and is only available when the script is invoked via
  `bash` — NOT `sh`. Your generator's shebang must be `#!/usr/bin/env bash`.
- **Idempotency check must cover all generated outputs.** A single-file
  check (e.g. "skip if `launch.json` exists") silently accepts partial
  state. Check every output you render.
- **Claude Preview (and similar port-caching MCPs) cache the port.** After
  a `--force` regenerate that picks a different offset, stop and restart
  the preview. Worth calling out in CLAUDE.md.
- **Race condition on simultaneous `git worktree add`s.** Two hooks probing
  in the same few milliseconds both pick offset 0 and conflict. Acceptable
  behavior: the loser fails to bind, user reruns with `--force`. If this
  becomes common, add a `flock` around the probe-and-write section of the
  generator keyed on `.claude/.port-lock`.
- **Symlinked worktree paths on macOS** (`/private/var` vs `/var`) —
  `git rev-parse --show-toplevel` returns the canonical path, so this is a
  non-issue if your generator resolves via git.
- **`extensions.worktreeConfig=true` + per-worktree `core.hookspath`
  overrides.** If a repo opts into `worktreeConfig`, each worktree can
  override `core.hooksPath` in its own `.git/worktrees/<name>/config.worktree`.
  Tools like VS Code and some Claude Desktop integrations have been observed
  writing an absolute `core.hookspath=.../.git/hooks` override at worktree
  creation time, which silently breaks the repo-tracked hook. Symptom: the
  hook runs fine when invoked by hand but never fires on `git worktree add`
  or `git checkout`. Diagnosis: `git config --worktree --get core.hookspath`
  (run from each worktree) should return empty or the same relative
  `githooks` path the repo config uses. Fix: `git config --worktree --unset
  core.hookspath` in the affected worktree. Worth including a check in your
  `install-git-hooks.sh`.
- **`postinstall` runs on every `npm ci` / `npm install`.** That's fine:
  the idempotent skip path is ~50ms. Not worth gating.

---

## Appendix: see also

- This repo's implementation plan: `docs/tasks/per-worktree-ports/plan.md`.
- The generator script, end-to-end: `devtools/setup-worktree-ports.sh`.
- The hook: `githooks/post-checkout`.
- Template files: `.claude/*.template`.
- Tests: `backend/tests/tools/test_setup_worktree_ports.py`,
  `backend/tests/tools/test_post_checkout_hook.py`,
  `backend/tests/tools/test_postinstall_backup.py`,
  `backend/tests/tools/test_default_ports_smoke.py`.

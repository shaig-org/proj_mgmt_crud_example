#!/usr/bin/env bash
# Regenerate every artifact the dev-dashboard reads — one command, all tabs.
#
# Use this whenever the dashboard looks stale/empty. Steps run in parallel
# where they can (no shared outputs); the only dependency is Step 4 → Step 3
# and Step 6 → everything. A failure in one step does NOT abort the rest, so
# optional pieces (pytest-tracer, e2e) can be missing without blocking the
# rest.
#
# DEPENDENCY GRAPH:
#
#   ┌─ Step 1 (analyze_capabilities)  ─┐
#   ├─ Step 2 (diff_capabilities)     ─┤
#   ├─ Step 3 (e2e:scenarios) ─► Step 4 (walkthroughs:generate)
#   └─ Step 5 (build_trace_artifacts) ─┘
#                                       │
#                                       ▼
#                                     Step 6 (check-staleness)
#
# ARTIFACT MAP — which step produces what, consumed by which dashboard tab:
#
#   Step 1  analyze_capabilities
#           → backend/evidence/capabilities/report.json
#           → backend/evidence/capabilities/baseline.json (only if drifted)
#           consumed by: Capabilities tab (route table)
#
#   Step 2  diff_capabilities --from <auto> --to HEAD
#           → backend/evidence/capabilities/git-diff.json
#           consumed by: Capabilities tab → Git Diff section
#
#   Step 3  npm run e2e:scenarios   (needs backend + frontend running)
#           → backend/e2e-traces/<scenario>/…     (per-request call traces)
#           → frontend/test-results/<scenario>/…  (Playwright screenshots, videos)
#           consumed by: Scenarios tab (flame charts on individual scenarios),
#                        input for Step 4
#
#   Step 4  npm run walkthroughs:generate
#           → frontend/walkthroughs/gallery/manifest.json
#           → frontend/walkthroughs/gallery/gifs/*.gif
#           → frontend/walkthroughs/gallery/screenshots/**/*.png
#           → frontend/walkthroughs/gallery/videos/*.webm
#           consumed by: Scenarios tab (GIF cards, screenshot strips),
#                        Screens tab (per-route screenshot index)
#
#   Step 5  build_trace_artifacts.sh
#           → backend/.trace-artifacts/<scenario>/mermaid.md + .svg + folded stacks
#           → backend/.trace-index/index.db
#           consumed by: Traces tab
#
#   Step 6  dev-dashboard check-staleness.mjs
#           → tools/dev-dashboard/.staleness.json
#           consumed by: the "X stale" indicator in the dashboard header
#
# Usage (from repo root):
#   ./devtools/refresh-dashboard-artifacts.sh          # full refresh
#   ./devtools/refresh-dashboard-artifacts.sh --skip-e2e
#   ./devtools/refresh-dashboard-artifacts.sh --diff-from v1.0
#   ./devtools/refresh-dashboard-artifacts.sh --serial # disable parallelism (debug)
#
# Shortcuts:
#   npm --prefix tools/dev-dashboard run dashboard:refresh
#
# Flags:
#   --skip-e2e      Skip Playwright scenarios + walkthrough generation (Steps 3+4).
#                   Useful when backend/frontend aren't running or you just want
#                   to refresh capability artifacts.
#   --diff-from REF Override the git ref used for the capability git diff
#                   (default: auto-pick the first ancestor where baseline.json
#                    differs from HEAD; falls back to "main").
#   --serial        Run steps sequentially (debugging, or when you want
#                   interleaved output). Normal mode runs independent steps
#                   in parallel and surfaces each step's log only on failure.
#   -h, --help      Print this header and exit.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

SKIP_E2E=0
DIFF_FROM=""
SERIAL=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-e2e) SKIP_E2E=1; shift ;;
    --diff-from) DIFF_FROM="$2"; shift 2 ;;
    --serial) SERIAL=1; shift ;;
    -h|--help)
      # Print the top-of-file header only: everything up to the first blank line
      # after the shebang. Stops before in-script step-divider comments.
      awk 'NR==1{next} /^[^#]/{exit} {sub(/^# ?/,""); print}' "$0"
      exit 0
      ;;
    *) echo "Unknown flag: $1" >&2; exit 2 ;;
  esac
done

# Auto-pick DIFF_FROM up front so parallel Step 2 has it.
if [[ -z "$DIFF_FROM" ]]; then
  DIFF_FROM="$(git log --format=%H -- backend/evidence/capabilities/baseline.json \
               | awk 'NR>1 {print; exit}')"
  if [[ -z "$DIFF_FROM" ]]; then
    DIFF_FROM="main"
  fi
fi

# Per-step logs so parallel stderr/stdout doesn't interleave.
LOG_DIR=$(mktemp -d -t dashboard-refresh.XXXXXX)
trap 'rm -rf "$LOG_DIR"' EXIT

step() { printf "\n\033[1;34m==> %s\033[0m\n" "$*"; }
warn() { printf "\033[1;33m[skip] %s\033[0m\n" "$*"; }
fail() { printf "\033[1;31m[fail] %s\033[0m\n" "$*"; }
ok()   { printf "\033[1;32m[ok]   %s\033[0m\n" "$*"; }

# Bash 3.2 has no associative arrays, so we stash pid + label per step in
# files inside $LOG_DIR.

# Launch a step in background; captures stdout+stderr to $LOG_DIR/<name>.log
# and exit code to $LOG_DIR/<name>.status.
launch() {
  local name=$1
  local label=$2
  shift 2
  local log="$LOG_DIR/$name.log"
  local status_file="$LOG_DIR/$name.status"
  printf '%s' "$label" > "$LOG_DIR/$name.label"
  (
    if "$@" > "$log" 2>&1; then
      echo 0 > "$status_file"
    else
      echo $? > "$status_file"
    fi
  ) &
  echo "$!" > "$LOG_DIR/$name.pid"
}

# Wait for a named step; emit ok/fail with log-dump on fail.
await() {
  local name=$1
  local pid
  pid=$(cat "$LOG_DIR/$name.pid")
  wait "$pid"
  local status
  status=$(cat "$LOG_DIR/$name.status")
  local label
  label=$(cat "$LOG_DIR/$name.label")
  if [[ "$status" == "0" ]]; then
    ok "$label"
  else
    fail "$label"
    cat "$LOG_DIR/$name.log"
  fi
  return "$status"
}

# --- Step bodies as functions so --serial can reuse them ----------------------

do_analyze_capabilities() {
  (cd backend && ./devtools/run_with_env.sh uv run python -m project_management_crud_example.tools.analyze_capabilities)
}

do_diff_capabilities() {
  (cd backend && ./devtools/run_with_env.sh uv run python -m project_management_crud_example.tools.diff_capabilities --from "$DIFF_FROM" --to HEAD)
}

do_e2e_scenarios() {
  (cd frontend && npm run e2e:scenarios -- --reporter=line)
}

do_walkthroughs() {
  (cd frontend && npm run walkthroughs:generate)
}

do_build_traces() {
  if [[ -x backend/devtools/build_trace_artifacts.sh ]]; then
    (cd backend && ./devtools/build_trace_artifacts.sh)
  else
    echo "[warn] backend/devtools/build_trace_artifacts.sh missing" >&2
    return 0
  fi
}

do_check_staleness() {
  (cd tools/dev-dashboard && node scripts/check-staleness.mjs)
}

# -----------------------------------------------------------------------------
# Serial mode — old behavior, for debugging / interleaved logs.
# -----------------------------------------------------------------------------
if [[ "$SERIAL" -eq 1 ]]; then
  step "analyze_capabilities"
  if do_analyze_capabilities; then ok "analyze_capabilities"; else fail "analyze_capabilities"; fi

  step "diff_capabilities (from $DIFF_FROM → HEAD)"
  if do_diff_capabilities; then ok "diff_capabilities"; else fail "diff_capabilities"; fi

  if [[ "$SKIP_E2E" -eq 1 ]]; then
    warn "e2e:scenarios (--skip-e2e)"
    warn "walkthroughs:generate (--skip-e2e)"
  else
    step "e2e:scenarios"
    if do_e2e_scenarios; then
      ok "e2e:scenarios"
      step "walkthroughs:generate"
      if do_walkthroughs; then ok "walkthroughs:generate"; else fail "walkthroughs:generate"; fi
    else
      fail "e2e:scenarios"
    fi
  fi

  step "build_trace_artifacts.sh"
  if do_build_traces; then ok "build_trace_artifacts.sh"; else fail "build_trace_artifacts.sh"; fi

  step "check-staleness.mjs"
  if do_check_staleness; then ok "check-staleness"; else fail "check-staleness"; fi

  printf "\n\033[1;32mDone. Open the dashboard (npm --prefix tools/dev-dashboard run dashboard) to see the refreshed artifacts.\033[0m\n"
  exit 0
fi

# -----------------------------------------------------------------------------
# Parallel mode (default) — fan out independent steps.
# -----------------------------------------------------------------------------

echo "Refreshing dashboard artifacts in parallel… (use --serial for sequential output)"
echo "diff ref: $DIFF_FROM → HEAD"

# Kick off Steps 1, 2, 3, 5 concurrently.
launch analyze     "analyze_capabilities"           do_analyze_capabilities
launch diffcaps    "diff_capabilities"              do_diff_capabilities
launch traces      "build_trace_artifacts.sh"       do_build_traces

if [[ "$SKIP_E2E" -eq 1 ]]; then
  warn "e2e:scenarios (--skip-e2e)"
  warn "walkthroughs:generate (--skip-e2e)"
  E2E_OK=0
else
  launch e2e       "e2e:scenarios"                  do_e2e_scenarios
fi

# Step 3 (e2e) gates Step 4 (walkthroughs). Wait for it first.
E2E_OK=1
if [[ "$SKIP_E2E" -ne 1 ]]; then
  if await e2e; then
    launch walkthroughs "walkthroughs:generate" do_walkthroughs
  else
    warn "walkthroughs:generate (skipped because e2e:scenarios failed)"
    E2E_OK=0
  fi
fi

# Wait for Steps 1, 2, 5 in order so output reads top-to-bottom.
await analyze    || true
await diffcaps   || true
await traces     || true
if [[ "$E2E_OK" -eq 1 && "$SKIP_E2E" -ne 1 ]]; then
  await walkthroughs || true
fi

# Step 6 last — must see every artifact's final mtime.
step "check-staleness.mjs"
if do_check_staleness; then ok "check-staleness"; else fail "check-staleness"; fi

printf "\n\033[1;32mDone. Open the dashboard (npm --prefix tools/dev-dashboard run dashboard) to see the refreshed artifacts.\033[0m\n"

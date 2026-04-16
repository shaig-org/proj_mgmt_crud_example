#!/usr/bin/env bash
# Regenerate every artifact the dev-dashboard reads — one command, all tabs.
#
# Use this whenever the dashboard looks stale/empty. Each step is independent
# and a failure in one does NOT abort the rest, because some steps depend on
# optional tooling (pytest-tracer) or running services (backend + frontend).
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
# Both kinds of traces ARE covered: e2e-traces (Step 3) + pytest-tracer
# .trace-artifacts via build_trace_artifacts.sh (Step 5).
#
# Usage (from repo root):
#   ./devtools/refresh-dashboard-artifacts.sh          # full refresh
#   ./devtools/refresh-dashboard-artifacts.sh --skip-e2e
#   ./devtools/refresh-dashboard-artifacts.sh --diff-from v1.0
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
#   -h, --help      Print this header and exit.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

SKIP_E2E=0
DIFF_FROM=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-e2e) SKIP_E2E=1; shift ;;
    --diff-from) DIFF_FROM="$2"; shift 2 ;;
    -h|--help)
      # Print the top-of-file header only: everything up to the first blank line
      # after the shebang. Stops before in-script step-divider comments.
      awk 'NR==1{next} /^[^#]/{exit} {sub(/^# ?/,""); print}' "$0"
      exit 0
      ;;
    *) echo "Unknown flag: $1" >&2; exit 2 ;;
  esac
done

step() { printf "\n\033[1;34m==> %s\033[0m\n" "$*"; }
warn() { printf "\033[1;33m[skip] %s\033[0m\n" "$*"; }
fail() { printf "\033[1;31m[fail] %s\033[0m\n" "$*"; }
ok()   { printf "\033[1;32m[ok]   %s\033[0m\n" "$*"; }

# -----------------------------------------------------------------------------
# 1. Capability analyzer — report.json + baseline.json (if drift)
# -----------------------------------------------------------------------------
step "analyze_capabilities (report.json, baseline.json)"
if (cd backend && ./devtools/run_with_env.sh uv run python -m project_management_crud_example.tools.analyze_capabilities); then
  ok "analyze_capabilities"
else
  fail "analyze_capabilities"
fi

# -----------------------------------------------------------------------------
# 2. Git diff — compare baseline.json between two refs
# -----------------------------------------------------------------------------
step "diff_capabilities (git-diff.json)"
if [[ -z "$DIFF_FROM" ]]; then
  # Auto-pick: walk backward from HEAD until baseline.json bytes change.
  DIFF_FROM="$(git log --format=%H -- backend/evidence/capabilities/baseline.json \
               | awk 'NR>1 {print; exit}')"
  if [[ -z "$DIFF_FROM" ]]; then
    DIFF_FROM="main"
  fi
fi
echo "using --from $DIFF_FROM --to HEAD"
if (cd backend && ./devtools/run_with_env.sh uv run python -m project_management_crud_example.tools.diff_capabilities --from "$DIFF_FROM" --to HEAD); then
  ok "diff_capabilities"
else
  fail "diff_capabilities"
fi

# -----------------------------------------------------------------------------
# 3. Playwright scenarios — produces backend/e2e-traces/ (E2eTracingMiddleware
#    writes per-request call traces here during scenario runs) plus the raw
#    Playwright test-results that Step 4 turns into GIFs/screenshots.
# -----------------------------------------------------------------------------
if [[ "$SKIP_E2E" -eq 1 ]]; then
  warn "e2e:scenarios (--skip-e2e)"
  warn "walkthroughs:generate (--skip-e2e)"
else
  step "e2e:scenarios — backend/e2e-traces/ + raw Playwright recordings"
  if (cd frontend && npm run e2e:scenarios -- --reporter=line); then
    ok "e2e:scenarios"
  else
    fail "e2e:scenarios (requires backend on :8000 AND frontend on :5173/:3000)"
  fi

  # -----------------------------------------------------------------------------
  # 4. Walkthroughs — turns Step 3's raw recordings into GIFs + manifest.
  #    Feeds both the Scenarios tab and the Screens tab.
  # -----------------------------------------------------------------------------
  step "walkthroughs:generate — frontend/walkthroughs/gallery/ (GIFs, screenshots, manifest)"
  if (cd frontend && npm run walkthroughs:generate); then
    ok "walkthroughs:generate"
  else
    fail "walkthroughs:generate"
  fi
fi

# -----------------------------------------------------------------------------
# 5. Trace artifacts — backend/.trace-artifacts/ + backend/.trace-index/
#    (Traces tab). Runs the repo-owned build_trace_artifacts.sh, which under
#    the hood invokes pytest-tracer's collect + trace subcommands and packs the
#    output (folded-compact, mermaid, flame) into per-scenario directories.
# -----------------------------------------------------------------------------
step "build_trace_artifacts.sh — backend/.trace-artifacts/ (Traces tab)"
if [[ -x backend/devtools/build_trace_artifacts.sh ]]; then
  if (cd backend && ./devtools/build_trace_artifacts.sh >/dev/null 2>&1); then
    ok "build_trace_artifacts.sh"
  else
    fail "build_trace_artifacts.sh (re-run manually to see stderr: cd backend && ./devtools/build_trace_artifacts.sh)"
  fi
else
  warn "build_trace_artifacts.sh missing — Traces tab will stay empty"
fi

# -----------------------------------------------------------------------------
# 6. Dashboard staleness — reads mtimes of all sources → .staleness.json
#    Always runs last so it picks up every file touched above.
# -----------------------------------------------------------------------------
step "check-staleness.mjs (.staleness.json)"
if (cd tools/dev-dashboard && node scripts/check-staleness.mjs); then
  ok "check-staleness"
else
  fail "check-staleness"
fi

printf "\n\033[1;32mDone. Open the dashboard (npm --prefix tools/dev-dashboard run dashboard) to see the refreshed artifacts.\033[0m\n"

#!/usr/bin/env bash
# Run every fast validation across the whole repo in parallel.
#
#   backend : ruff-fix + ruff-format + ty + pytest   (~30s, dominates)
#   frontend: lint + typecheck                       (~4s)
#   dashboard: lint + typecheck + vitest             (~5s)
#
# Runs all three in parallel; total wall time ≈ backend (30s) since the
# others complete well inside that window. Per-step stdout/stderr is
# captured and only printed on failure — concise on pass, verbose on fail
# (same contract the other orchestrators in this repo use).
#
# E2E (Playwright, ~75s after the auth-seeding refactor in
# frontend/e2e/utils/auth.ts) and dashboard smoke tests are opt-in
# because they need the dev servers running and are slower.
#
# When --with-e2e is passed, E2E runs AFTER the parallel fast checks
# finish — not alongside them. Running E2E concurrently with backend
# pytest (8 xdist workers + 4 Playwright workers both hitting the same
# machine) causes cascading login timeouts on the shared backend due to
# bcrypt CPU contention. Serializing keeps E2E stable.
#
# Usage (from repo root or anywhere):
#   ./devtools/run-all-validations.sh            # backend + frontend + dashboard fast checks
#   ./devtools/run-all-validations.sh --with-e2e # additionally run frontend Playwright
#   ./devtools/run-all-validations.sh --serial   # debug: run sequentially
#
# Exit code: non-zero if any step fails.

set -u

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

WITH_E2E=0
SERIAL=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-e2e) WITH_E2E=1; shift ;;
    --serial)   SERIAL=1; shift ;;
    -h|--help)
      awk 'NR==1{next} /^[^#]/{exit} {sub(/^# ?/,""); print}' "$0"
      exit 0
      ;;
    *) echo "Unknown flag: $1" >&2; exit 2 ;;
  esac
done

LOG_DIR=$(mktemp -d -t run-all-validations.XXXXXX)
trap 'rm -rf "$LOG_DIR"' EXIT

ok()   { printf "\033[1;32m[ok]   %s\033[0m\n" "$*"; }
fail() { printf "\033[1;31m[fail] %s\033[0m\n" "$*"; }
skip() { printf "\033[1;33m[skip] %s\033[0m\n" "$*"; }

# Launch a step in background; capture stdout+stderr and exit code.
launch() {
  local name=$1
  local label=$2
  shift 2
  printf '%s' "$label" > "$LOG_DIR/$name.label"
  (
    if "$@" > "$LOG_DIR/$name.log" 2>&1; then
      echo 0 > "$LOG_DIR/$name.status"
    else
      echo $? > "$LOG_DIR/$name.status"
    fi
  ) &
  echo "$!" > "$LOG_DIR/$name.pid"
}

# Wait for a named step; print ok/fail with log-dump on fail.
await() {
  local name=$1
  wait "$(cat "$LOG_DIR/$name.pid")" 2>/dev/null || true
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

# --- Step bodies --------------------------------------------------------------

do_backend() {
  "$REPO_ROOT/backend/devtools/run_all_agent_validations.sh"
}

do_frontend_lint()      { npm --prefix "$REPO_ROOT/frontend" run lint; }
do_frontend_typecheck() { npm --prefix "$REPO_ROOT/frontend" run typecheck; }

do_dashboard_lint()      { npm --prefix "$REPO_ROOT/tools/dev-dashboard" run lint; }
do_dashboard_typecheck() { npm --prefix "$REPO_ROOT/tools/dev-dashboard" run typecheck; }
do_dashboard_test()      { npm --prefix "$REPO_ROOT/tools/dev-dashboard" run test -- --run; }

do_frontend_e2e() { npm --prefix "$REPO_ROOT/frontend" run e2e -- --reporter=line; }

# --- Serial mode (debug) ------------------------------------------------------

if [[ "$SERIAL" -eq 1 ]]; then
  RC=0
  for step in backend frontend_lint frontend_typecheck dashboard_lint dashboard_typecheck dashboard_test; do
    echo "==> $step"
    if do_$step; then ok "$step"; else fail "$step"; RC=1; fi
  done
  if [[ "$WITH_E2E" -eq 1 ]]; then
    echo "==> frontend_e2e"
    if do_frontend_e2e; then ok "frontend_e2e"; else fail "frontend_e2e"; RC=1; fi
  fi
  exit $RC
fi

# --- Parallel mode (default) --------------------------------------------------

SECONDS_START=$SECONDS
echo "Running all validations in parallel…"

launch backend           "backend: ruff + ty + pytest"     do_backend
launch fe_lint           "frontend: lint"                  do_frontend_lint
launch fe_tc             "frontend: typecheck"             do_frontend_typecheck
launch db_lint           "dashboard: lint"                 do_dashboard_lint
launch db_tc             "dashboard: typecheck"            do_dashboard_typecheck
launch db_test           "dashboard: test"                 do_dashboard_test

RC=0
await fe_lint    || RC=1
await fe_tc      || RC=1
await db_lint    || RC=1
await db_tc      || RC=1
await db_test    || RC=1
await backend    || RC=1

# E2E runs AFTER the fast checks. Running it concurrently with backend
# pytest hammers the machine's CPU (bcrypt), causing cascading login
# timeouts. See header comment.
if [[ "$WITH_E2E" -eq 1 ]]; then
  launch fe_e2e          "frontend: e2e (Playwright)"      do_frontend_e2e
  await fe_e2e || RC=1
else
  skip "frontend: e2e (Playwright) — pass --with-e2e to include"
fi

ELAPSED=$(( SECONDS - SECONDS_START ))
if [[ $RC -eq 0 ]]; then
  printf "\n\033[1;32m✅ All validations passed in %ss\033[0m\n" "$ELAPSED"
else
  printf "\n\033[1;31m❌ One or more validations failed (elapsed %ss)\033[0m\n" "$ELAPSED"
fi
exit $RC

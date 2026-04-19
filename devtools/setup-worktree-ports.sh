#!/usr/bin/env bash
# Per-worktree dev-port generator.
#
# Picks a free port bank (frontend/dashboard/backend) for this worktree and
# renders four artifacts atomically:
#   - .claude/env.ports               (sourced by backend/devtools/run_with_env.sh)
#   - frontend/.env.local             (Vite auto-load)
#   - tools/dev-dashboard/.env.local  (Vite auto-load)
#   - .claude/launch.json             (Claude Preview MCP)
#
# Usage:
#   devtools/setup-worktree-ports.sh [--force] [--print] [--worktree-root <path>]
#
# Flags:
#   --force             Regenerate even if all four artifacts already exist.
#   --print             Print "FRONTEND_PORT=<> DASHBOARD_PORT=<> BACKEND_PORT=<>"
#                       for the first free offset and exit without writing files.
#   --worktree-root DIR Use DIR as the worktree root (overrides git + $PWD).
#
# Exit codes:
#   0  wrote files, OR skipped idempotently, OR --print succeeded
#   1  template missing / unwritable path / templating failure
#   2  no free port bank found within the candidate range
#   3  invalid CLI args
#
# Port probe uses bash's built-in /dev/tcp redirection (hard-coded into bash;
# no actual file open). Available on macOS bash 3.2 and Linux bash 4+ but ONLY
# when the script is invoked as bash (NOT sh). The shebang above guarantees
# bash mode.

# Intentionally do NOT `set -e` — we want to emit clear errors ourselves, not
# die on the first failed `(exec 3<>/dev/tcp/...)` which intentionally fails
# when a port is free.
set -u

# -----------------------------------------------------------------------------
# CLI parsing
# -----------------------------------------------------------------------------

FORCE=0
PRINT=0
WORKTREE_ROOT=""

while [ $# -gt 0 ]; do
  case "$1" in
    --force) FORCE=1; shift ;;
    --print) PRINT=1; shift ;;
    --worktree-root)
      if [ $# -lt 2 ]; then
        echo "[setup-worktree-ports] --worktree-root requires a path argument" >&2
        echo "usage: setup-worktree-ports.sh [--force] [--print] [--worktree-root <path>]" >&2
        exit 3
      fi
      WORKTREE_ROOT="$2"
      shift 2
      ;;
    -h|--help)
      # Print top-of-file help comment (up to first blank line after shebang).
      awk 'NR==1{next} /^[^#]/{exit} {sub(/^# ?/,""); print}' "$0"
      exit 0
      ;;
    *)
      echo "[setup-worktree-ports] unknown flag: $1" >&2
      echo "usage: setup-worktree-ports.sh [--force] [--print] [--worktree-root <path>]" >&2
      exit 3
      ;;
  esac
done

# -----------------------------------------------------------------------------
# Resolve worktree root.
# Priority: --worktree-root > git rev-parse --show-toplevel > $PWD.
# -----------------------------------------------------------------------------

if [ -z "$WORKTREE_ROOT" ]; then
  if WORKTREE_ROOT_GIT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
    WORKTREE_ROOT="$WORKTREE_ROOT_GIT"
  else
    WORKTREE_ROOT="$PWD"
  fi
fi

if [ ! -d "$WORKTREE_ROOT" ]; then
  echo "[setup-worktree-ports] worktree root does not exist: $WORKTREE_ROOT" >&2
  exit 1
fi

TEMPLATE_LAUNCH="$WORKTREE_ROOT/.claude/launch.json.template"
TEMPLATE_ENV_FRONTEND="$WORKTREE_ROOT/.claude/env.frontend.template"
TEMPLATE_ENV_DASHBOARD="$WORKTREE_ROOT/.claude/env.dashboard.template"
TEMPLATE_ENV_PORTS="$WORKTREE_ROOT/.claude/env.ports.template"

OUT_LAUNCH="$WORKTREE_ROOT/.claude/launch.json"
OUT_ENV_FRONTEND="$WORKTREE_ROOT/frontend/.env.local"
OUT_ENV_DASHBOARD="$WORKTREE_ROOT/tools/dev-dashboard/.env.local"
OUT_ENV_PORTS="$WORKTREE_ROOT/.claude/env.ports"

# -----------------------------------------------------------------------------
# Idempotency: if all four outputs exist and --force absent, skip.
# -----------------------------------------------------------------------------

if [ "$FORCE" -eq 0 ] && [ "$PRINT" -eq 0 ] \
   && [ -f "$OUT_LAUNCH" ] \
   && [ -f "$OUT_ENV_FRONTEND" ] \
   && [ -f "$OUT_ENV_DASHBOARD" ] \
   && [ -f "$OUT_ENV_PORTS" ]; then
  echo "[setup-worktree-ports] all artifacts present; skipping (use --force to regenerate)"
  exit 0
fi

# -----------------------------------------------------------------------------
# Template existence check (before we probe any ports).
# -----------------------------------------------------------------------------

for tpl in "$TEMPLATE_LAUNCH" "$TEMPLATE_ENV_FRONTEND" "$TEMPLATE_ENV_DASHBOARD" "$TEMPLATE_ENV_PORTS"; do
  if [ ! -f "$tpl" ]; then
    echo "[setup-worktree-ports] template error: missing template file $tpl" >&2
    exit 1
  fi
done

# -----------------------------------------------------------------------------
# Port probe: first offset in {0, 10, 20, ..., MAX_OFFSET} where
# 3000+N, 5179+N, 8000+N are all free on 127.0.0.1.
# WORKTREE_PORTS_MAX_OFFSET override is for tests; default 990.
# -----------------------------------------------------------------------------

MAX_OFFSET="${WORKTREE_PORTS_MAX_OFFSET:-990}"
# Test overrides: allow the test harness to pick an unrelated high port base
# that is guaranteed free on the developer's box. Production defaults below
# are the plan's 3000 / 5179 / 8000.
FRONTEND_BASE="${WORKTREE_PORTS_FRONTEND_BASE:-3000}"
DASHBOARD_BASE="${WORKTREE_PORTS_DASHBOARD_BASE:-5179}"
BACKEND_BASE="${WORKTREE_PORTS_BACKEND_BASE:-8000}"

port_is_free() {
  # Returns 0 iff a TCP connect to 127.0.0.1:$1 fails (nothing is listening).
  local port="$1"
  if (exec 3<>/dev/tcp/127.0.0.1/"$port") 2>/dev/null; then
    # Connect succeeded → port busy. Close fd3 and return 1.
    exec 3<&- 2>/dev/null || true
    exec 3>&- 2>/dev/null || true
    return 1
  fi
  return 0
}

pick_offset() {
  local n=0
  while [ "$n" -le "$MAX_OFFSET" ]; do
    local f=$((FRONTEND_BASE + n))
    local d=$((DASHBOARD_BASE + n))
    local b=$((BACKEND_BASE + n))
    if port_is_free "$f" && port_is_free "$d" && port_is_free "$b"; then
      echo "$n"
      return 0
    fi
    n=$((n + 10))
  done
  return 1
}

OFFSET="$(pick_offset)" || {
  echo "[setup-worktree-ports] could not find a free port bank in offsets 0..$MAX_OFFSET step 10" >&2
  exit 2
}

FRONTEND_PORT=$((FRONTEND_BASE + OFFSET))
DASHBOARD_PORT=$((DASHBOARD_BASE + OFFSET))
BACKEND_PORT=$((BACKEND_BASE + OFFSET))

# -----------------------------------------------------------------------------
# --print mode: just report and bail.
# -----------------------------------------------------------------------------

if [ "$PRINT" -eq 1 ]; then
  echo "FRONTEND_PORT=$FRONTEND_PORT DASHBOARD_PORT=$DASHBOARD_PORT BACKEND_PORT=$BACKEND_PORT"
  exit 0
fi

# -----------------------------------------------------------------------------
# Render templates. Substitution targets exactly three tokens:
#   ${FRONTEND_PORT}, ${DASHBOARD_PORT}, ${BACKEND_PORT}
# Anything else remaining as ${...} after substitution is an error.
# Writes go to *.tmp, then atomic mv. If any .tmp write fails we abort before
# any mv, so existing outputs are never partially overwritten.
# -----------------------------------------------------------------------------

render_template() {
  # render_template <src_template> <dest_path>
  local src="$1"
  local dest="$2"
  local tmp="$dest.tmp"

  # Ensure parent directory exists (tests/fresh clones may lack frontend/ etc.)
  local dest_dir
  dest_dir="$(dirname "$dest")"
  if ! mkdir -p "$dest_dir" 2>/dev/null; then
    echo "[setup-worktree-ports] could not create directory $dest_dir" >&2
    return 1
  fi

  # sed with three explicit substitutions. `|` delimiter to avoid clashing
  # with URL `/` chars in BACKEND_URL lines.
  if ! sed \
      -e "s|\${FRONTEND_PORT}|$FRONTEND_PORT|g" \
      -e "s|\${DASHBOARD_PORT}|$DASHBOARD_PORT|g" \
      -e "s|\${BACKEND_PORT}|$BACKEND_PORT|g" \
      "$src" > "$tmp" 2>/dev/null; then
    echo "[setup-worktree-ports] failed to render template $src → $tmp" >&2
    rm -f "$tmp"
    return 1
  fi

  # Detect any unresolved ${VAR} token left in the rendered output.
  if grep -o '\${[A-Za-z_][A-Za-z0-9_]*}' "$tmp" >/dev/null 2>&1; then
    local unresolved
    unresolved="$(grep -o '\${[A-Za-z_][A-Za-z0-9_]*}' "$tmp" | head -1)"
    echo "[setup-worktree-ports] template error: unresolved $unresolved in $src" >&2
    rm -f "$tmp"
    return 1
  fi

  return 0
}

# Render all four to .tmp files FIRST. Only after all four succeed do we mv.
# This gives us stronger atomicity: a failure in rendering #4 does not leave
# files #1-3 in their new state.

if ! render_template "$TEMPLATE_ENV_PORTS" "$OUT_ENV_PORTS"; then
  rm -f "$OUT_ENV_PORTS.tmp" "$OUT_ENV_FRONTEND.tmp" "$OUT_ENV_DASHBOARD.tmp" "$OUT_LAUNCH.tmp"
  exit 1
fi
if ! render_template "$TEMPLATE_ENV_FRONTEND" "$OUT_ENV_FRONTEND"; then
  rm -f "$OUT_ENV_PORTS.tmp" "$OUT_ENV_FRONTEND.tmp" "$OUT_ENV_DASHBOARD.tmp" "$OUT_LAUNCH.tmp"
  exit 1
fi
if ! render_template "$TEMPLATE_ENV_DASHBOARD" "$OUT_ENV_DASHBOARD"; then
  rm -f "$OUT_ENV_PORTS.tmp" "$OUT_ENV_FRONTEND.tmp" "$OUT_ENV_DASHBOARD.tmp" "$OUT_LAUNCH.tmp"
  exit 1
fi
if ! render_template "$TEMPLATE_LAUNCH" "$OUT_LAUNCH"; then
  rm -f "$OUT_ENV_PORTS.tmp" "$OUT_ENV_FRONTEND.tmp" "$OUT_ENV_DASHBOARD.tmp" "$OUT_LAUNCH.tmp"
  exit 1
fi

# Atomic moves. If any mv fails (read-only fs etc.), report and exit 1 —
# earlier successful mvs remain, but the next run will detect partial state
# via the all-four idempotency check (or --force).
for pair in \
    "$OUT_ENV_PORTS.tmp:$OUT_ENV_PORTS" \
    "$OUT_ENV_FRONTEND.tmp:$OUT_ENV_FRONTEND" \
    "$OUT_ENV_DASHBOARD.tmp:$OUT_ENV_DASHBOARD" \
    "$OUT_LAUNCH.tmp:$OUT_LAUNCH"; do
  src="${pair%%:*}"
  dst="${pair##*:}"
  if ! mv "$src" "$dst" 2>/dev/null; then
    echo "[setup-worktree-ports] failed to write $dst (read-only path?)" >&2
    # Cleanup any leftover .tmp files.
    rm -f "$OUT_ENV_PORTS.tmp" "$OUT_ENV_FRONTEND.tmp" "$OUT_ENV_DASHBOARD.tmp" "$OUT_LAUNCH.tmp"
    exit 1
  fi
done

echo "[setup-worktree-ports] offset=$OFFSET frontend=$FRONTEND_PORT dashboard=$DASHBOARD_PORT backend=$BACKEND_PORT"
exit 0

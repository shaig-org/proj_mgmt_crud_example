#!/usr/bin/env bash
# PostToolUse hook: runs a fast check on edited files.
# Reads the tool input from stdin (JSON) to learn which file changed.
# Outputs any issues to stderr; exit 0 always (non-blocking — advisory only).

set -u

payload="$(cat)"
file_path="$(printf '%s' "$payload" | grep -o '"file_path"[^,}]*' | head -n1 | sed 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')"

[ -z "$file_path" ] && exit 0

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
rel="${file_path#$repo_root/}"

case "$rel" in
  backend/*.py|backend/**/*.py)
    # Fast lint only — full validation is left to the validate-backend skill.
    if command -v uv >/dev/null 2>&1; then
      (cd "$repo_root/backend" && uv run ruff check --quiet "$file_path" 2>&1) >&2 || true
    fi
    ;;
  frontend/src/*.ts|frontend/src/*.tsx|frontend/e2e/*.ts|frontend/**/*.ts|frontend/**/*.tsx)
    # Fast lint only.
    if [ -f "$repo_root/frontend/package.json" ]; then
      (cd "$repo_root/frontend" && npx --no-install eslint "$file_path" 2>&1) >&2 || true
    fi
    ;;
esac

exit 0

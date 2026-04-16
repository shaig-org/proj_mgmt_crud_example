#!/usr/bin/env bash
# Compare capability surfaces at two git revisions.
# Writes backend/evidence/capabilities/git-diff.json (served by dev dashboard).
#
# Usage (from repo root or backend/):
#   ./backend/devtools/diff_capabilities.sh              # main → HEAD
#   ./backend/devtools/diff_capabilities.sh --from v1.0.0 --to HEAD
#   ./backend/devtools/diff_capabilities.sh --from main --to feature-branch
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

cd "$BACKEND_DIR"
exec ./devtools/run_with_env.sh uv run python -m project_management_crud_example.tools.diff_capabilities "$@"

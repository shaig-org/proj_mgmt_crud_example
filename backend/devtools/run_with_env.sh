#!/usr/bin/env bash
# Wrapper: sets test env vars and runs the given command. Used so agents can
# invoke python/pytest/uv with required env vars via a pre-approved path.
#
# Also sources the per-worktree port file (.claude/env.ports) if present, so
# callers can reference $BACKEND_PORT / $BACKEND_URL without manual export.
# See devtools/setup-worktree-ports.sh for how that file is produced.
set -euo pipefail
export JWT_SECRET_KEY="${JWT_SECRET_KEY:-test_secret_key_minimum_32_characters_long_xxxxx}"
export BCRYPT_ROUNDS="${BCRYPT_ROUNDS:-4}"

# Resolve worktree root (two levels up from this script: backend/devtools/..).
# Guard against the file being absent (first clone before install-git-hooks.sh).
_WRAPPER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_REPO_ROOT="$(cd "$_WRAPPER_DIR/../.." && pwd)"
if [ -f "$_REPO_ROOT/.claude/env.ports" ]; then
  # shellcheck disable=SC1091
  . "$_REPO_ROOT/.claude/env.ports"
fi
unset _WRAPPER_DIR _REPO_ROOT

exec "$@"

#!/usr/bin/env bash
# Wire the repo-tracked hooks in githooks/ into this clone.
# Idempotent — safe to re-run.
set -euo pipefail

REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
git -C "$REPO_ROOT" config core.hooksPath githooks
chmod +x "$REPO_ROOT"/githooks/*

# When extensions.worktreeConfig=true, some tooling (VS Code, Claude Desktop
# integrations, etc.) has been observed writing a per-worktree core.hookspath
# override that silently breaks the repo-tracked hooks for THIS worktree.
# Sweep every known worktree and unset the override so the shared
# core.hooksPath=githooks takes effect. Skip if worktreeConfig is off.
if [ "$(git -C "$REPO_ROOT" config --get extensions.worktreeConfig || echo false)" = "true" ]; then
  # Iterate worktrees and unset any per-worktree core.hookspath override.
  while IFS= read -r wt; do
    # `--worktree --unset` can only run from inside the target worktree.
    # It exits 5 when the key isn't set, which we swallow.
    git -C "$wt" config --worktree --unset core.hookspath 2>/dev/null || true
    git -C "$wt" config --worktree --unset core.hooksPath 2>/dev/null || true
  done < <(git -C "$REPO_ROOT" worktree list --porcelain | awk '/^worktree /{print $2}')
fi

echo "[install-git-hooks] core.hooksPath=githooks (active hooks:)"
ls "$REPO_ROOT/githooks/"

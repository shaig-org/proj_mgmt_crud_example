#!/usr/bin/env bash
# Wire the repo-tracked hooks in githooks/ into this clone.
# Idempotent — safe to re-run.
set -euo pipefail

REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
git -C "$REPO_ROOT" config core.hooksPath githooks
chmod +x "$REPO_ROOT"/githooks/*
echo "[install-git-hooks] core.hooksPath=githooks (active hooks:)"
ls "$REPO_ROOT/githooks/"

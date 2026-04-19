"""Tests for `githooks/post-checkout`.

The hook is a thin dispatcher to `devtools/setup-worktree-ports.sh`. These
tests build a minimal git repo in tmp_path, copy the hook + generator +
templates into it, wire `core.hooksPath=githooks`, and exercise real git
checkouts / worktree-adds via subprocess.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from tests.tools._port_helpers import (
    GENERATOR_REL_PATH,
    REPO_ROOT,
    TEMPLATE_FILES,
    reserved_port_bases,
)

HOOK_REL_PATH = "githooks/post-checkout"


def _prepare_git_repo(tmp_path: Path) -> Path:
    """Create a minimal git repo at tmp_path/repo containing:

    - `.git/` initialized
    - `core.hooksPath=githooks` set
    - `githooks/post-checkout` copied from the real repo (chmod +x)
    - `devtools/setup-worktree-ports.sh` copied from the real repo (chmod +x)
    - the four `.claude/*.template` files copied from the real repo
    - an initial commit so `git checkout -b <x>` works

    Returns the repo directory path.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    # git init without worktree prompts / global config interference.
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(repo)],
        check=True,
        capture_output=True,
    )
    # Use per-repo user identity so commits work in CI with no global config.
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test User"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "core.hooksPath", "githooks"], check=True)

    # Copy hooks + generator + templates.
    (repo / "githooks").mkdir()
    shutil.copy2(REPO_ROOT / HOOK_REL_PATH, repo / HOOK_REL_PATH)
    (repo / HOOK_REL_PATH).chmod(0o755)

    (repo / "devtools").mkdir()
    shutil.copy2(REPO_ROOT / GENERATOR_REL_PATH, repo / GENERATOR_REL_PATH)
    (repo / GENERATOR_REL_PATH).chmod(0o755)

    (repo / ".claude").mkdir()
    for rel in TEMPLATE_FILES:
        shutil.copy2(REPO_ROOT / rel, repo / rel)

    # Pre-create the parent directories for generator output targets so the
    # generator (which mkdir -p's anyway) isn't the one fighting umask.
    (repo / "frontend").mkdir()
    (repo / "tools" / "dev-dashboard").mkdir(parents=True)

    # Initial commit — so `git checkout -b <branch>` works.
    (repo / "README.md").write_text("seed\n")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-q", "-m", "seed"],
        check=True,
        capture_output=True,
    )

    return repo


def _git_env_with_bases(frontend: int, dashboard: int, backend: int) -> dict[str, str]:
    env = os.environ.copy()
    env["WORKTREE_PORTS_FRONTEND_BASE"] = str(frontend)
    env["WORKTREE_PORTS_DASHBOARD_BASE"] = str(dashboard)
    env["WORKTREE_PORTS_BACKEND_BASE"] = str(backend)
    return env


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_worktree_add_triggers_generator_and_creates_outputs(tmp_path: Path) -> None:
    """`git worktree add` fires post-checkout which runs the generator."""
    repo = _prepare_git_repo(tmp_path)
    worktree_path = tmp_path / "w2"

    with reserved_port_bases() as (fe, db, be):
        env = _git_env_with_bases(fe, db, be)
        result = subprocess.run(
            ["git", "-C", str(repo), "worktree", "add", "-b", "feature/w2", str(worktree_path)],
            env=env,
            capture_output=True,
            text=True,
        )

    assert result.returncode == 0, f"stdout={result.stdout} stderr={result.stderr}"
    assert (worktree_path / ".claude" / "launch.json").exists(), "launch.json not created in new worktree"
    assert (worktree_path / ".claude" / "env.ports").exists()
    assert (worktree_path / "frontend" / ".env.local").exists()
    assert (worktree_path / "tools" / "dev-dashboard" / ".env.local").exists()

    env_ports = (worktree_path / ".claude" / "env.ports").read_text()
    assert f"export FRONTEND_PORT={fe}" in env_ports


def test_checkout_in_existing_worktree_is_noop(tmp_path: Path) -> None:
    """Re-running the hook in a bootstrapped worktree leaves files untouched."""
    repo = _prepare_git_repo(tmp_path)

    with reserved_port_bases() as (fe, db, be):
        env = _git_env_with_bases(fe, db, be)

        # First: bootstrap via an explicit generator run (same effect as a
        # post-checkout on first worktree-add).
        generator = repo / GENERATOR_REL_PATH
        subprocess.run(
            [str(generator), "--worktree-root", str(repo)],
            env=env,
            check=True,
            capture_output=True,
        )

        targets = [
            repo / ".claude" / "launch.json",
            repo / ".claude" / "env.ports",
            repo / "frontend" / ".env.local",
            repo / "tools" / "dev-dashboard" / ".env.local",
        ]
        original_mtimes = {p: p.stat().st_mtime_ns for p in targets}

        # Now trigger the hook via a real checkout.
        result = subprocess.run(
            ["git", "-C", str(repo), "checkout", "-q", "-b", "feature/x"],
            env=env,
            capture_output=True,
            text=True,
        )

    assert result.returncode == 0, result.stderr
    for p in targets:
        assert p.stat().st_mtime_ns == original_mtimes[p], f"{p} was rewritten by no-op checkout"


def test_hook_failure_does_not_block_checkout(tmp_path: Path) -> None:
    """If the generator fails, checkout must still succeed (exit 0)."""
    repo = _prepare_git_repo(tmp_path)

    # Break the generator: remove a template so it exits 1.
    (repo / ".claude" / "launch.json.template").unlink()

    with reserved_port_bases() as (fe, db, be):
        env = _git_env_with_bases(fe, db, be)
        result = subprocess.run(
            ["git", "-C", str(repo), "checkout", "-q", "-b", "feature/y"],
            env=env,
            capture_output=True,
            text=True,
        )

    assert result.returncode == 0, f"checkout failed: stdout={result.stdout} stderr={result.stderr}"
    # The hook should have surfaced the generator's error on stderr.
    assert "setup-worktree-ports" in result.stderr
    # And the working tree advanced to the new branch.
    branch = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert branch.stdout.strip() == "feature/y"

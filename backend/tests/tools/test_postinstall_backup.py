"""Tests for the `npm postinstall` backup path.

The frontend and dashboard `package.json`s each carry a `postinstall` that
invokes `bash devtools/setup-worktree-ports.sh` (via `node -e
"spawnSync('bash', ['<rel>/devtools/setup-worktree-ports.sh'], {stdio:'inherit'})"`).

We do NOT run `npm ci` here — per the plan's test-matrix, we exercise the
shell generator via a direct subprocess invocation from each of the two
package-root directories. That verifies:
  1. The relative path from each package root to the generator is correct.
  2. The generator, when invoked with no explicit --worktree-root, discovers
     the worktree root correctly (via `git rev-parse --show-toplevel` fails
     and falls back to $PWD; we pass an explicit --worktree-root to pin the
     behavior).
  3. Idempotent re-invocation (two package-scoped postinstalls in a row)
     leaves the generated artifacts unchanged.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from tests.tools._port_helpers import (
    prepare_worktree,
    reserved_port_bases,
)


def _invoke_from_package_root(
    package_root: Path,
    rel_generator_path: str,
    worktree: Path,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    """Simulate `postinstall` from `package_root`:
        bash <rel>/devtools/setup-worktree-ports.sh --worktree-root <worktree>

    The relative path is what the postinstall npm script uses. We pass
    --worktree-root explicitly because the tmp worktree isn't a git tree;
    this matches how the hook passes it on a real worktree.
    """
    cmd = [
        "bash",
        rel_generator_path,
        "--worktree-root",
        str(worktree),
    ]
    return subprocess.run(
        cmd,
        cwd=package_root,
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=30,
    )


def test_postinstall_from_frontend_package_root_generates_all_outputs(tmp_path: Path) -> None:
    """Simulates `frontend/package.json`'s postinstall: runs the generator
    via the relative path `../devtools/setup-worktree-ports.sh`.
    """
    worktree = prepare_worktree(tmp_path)

    with reserved_port_bases() as (fe, db, be):
        env = os.environ.copy()
        env["WORKTREE_PORTS_FRONTEND_BASE"] = str(fe)
        env["WORKTREE_PORTS_DASHBOARD_BASE"] = str(db)
        env["WORKTREE_PORTS_BACKEND_BASE"] = str(be)

        result = _invoke_from_package_root(
            package_root=worktree / "frontend",
            rel_generator_path="../devtools/setup-worktree-ports.sh",
            worktree=worktree,
            env=env,
        )

    assert result.returncode == 0, f"stdout={result.stdout} stderr={result.stderr}"
    # All four expected artifacts are present.
    assert (worktree / ".claude" / "launch.json").exists()
    assert (worktree / ".claude" / "env.ports").exists()
    assert (worktree / "frontend" / ".env.local").exists()
    assert (worktree / "tools" / "dev-dashboard" / ".env.local").exists()
    # launch.json parses as valid JSON.
    launch = json.loads((worktree / ".claude" / "launch.json").read_text())
    assert "configurations" in launch


def test_postinstall_from_dashboard_package_root_generates_all_outputs(tmp_path: Path) -> None:
    """Simulates `tools/dev-dashboard/package.json`'s postinstall: runs the
    generator via the relative path `../../devtools/setup-worktree-ports.sh`.
    """
    worktree = prepare_worktree(tmp_path)

    with reserved_port_bases() as (fe, db, be):
        env = os.environ.copy()
        env["WORKTREE_PORTS_FRONTEND_BASE"] = str(fe)
        env["WORKTREE_PORTS_DASHBOARD_BASE"] = str(db)
        env["WORKTREE_PORTS_BACKEND_BASE"] = str(be)

        result = _invoke_from_package_root(
            package_root=worktree / "tools" / "dev-dashboard",
            rel_generator_path="../../devtools/setup-worktree-ports.sh",
            worktree=worktree,
            env=env,
        )

    assert result.returncode == 0, f"stdout={result.stdout} stderr={result.stderr}"
    assert (worktree / ".claude" / "launch.json").exists()
    assert (worktree / ".claude" / "env.ports").exists()
    assert (worktree / "frontend" / ".env.local").exists()
    assert (worktree / "tools" / "dev-dashboard" / ".env.local").exists()


def test_postinstall_when_outputs_already_exist_does_not_clobber_them(tmp_path: Path) -> None:
    """Running the postinstall command twice in a row is a no-op the second time.

    Matches the real flow where both frontend/ and tools/dev-dashboard/ will
    each invoke postinstall during a single `npm ci`.
    """
    worktree = prepare_worktree(tmp_path)

    with reserved_port_bases() as (fe, db, be):
        env = os.environ.copy()
        env["WORKTREE_PORTS_FRONTEND_BASE"] = str(fe)
        env["WORKTREE_PORTS_DASHBOARD_BASE"] = str(db)
        env["WORKTREE_PORTS_BACKEND_BASE"] = str(be)

        first = _invoke_from_package_root(
            package_root=worktree / "frontend",
            rel_generator_path="../devtools/setup-worktree-ports.sh",
            worktree=worktree,
            env=env,
        )
        assert first.returncode == 0

        targets = [
            worktree / ".claude" / "launch.json",
            worktree / ".claude" / "env.ports",
            worktree / "frontend" / ".env.local",
            worktree / "tools" / "dev-dashboard" / ".env.local",
        ]
        original_mtimes = {p: p.stat().st_mtime_ns for p in targets}

        # Let mtime resolution settle.
        time.sleep(1.1)

        second = _invoke_from_package_root(
            package_root=worktree / "tools" / "dev-dashboard",
            rel_generator_path="../../devtools/setup-worktree-ports.sh",
            worktree=worktree,
            env=env,
        )

    assert second.returncode == 0
    assert "skipping" in second.stdout
    for p in targets:
        assert p.stat().st_mtime_ns == original_mtimes[p], f"{p} was rewritten by the second postinstall"

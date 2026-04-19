"""Tests for `devtools/setup-worktree-ports.sh`.

Each test provisions a fresh tmp worktree (templates + generator copied from
the real repo) and invokes the script as a subprocess. Port-busy cases use
real `socket.bind + listen` on 127.0.0.1 — no mocking of the bash `/dev/tcp`
probe.

To keep tests robust against whatever the developer has running locally
(e.g. Vite on :3000), the generator exposes three test-only env overrides:
`WORKTREE_PORTS_FRONTEND_BASE`, `WORKTREE_PORTS_DASHBOARD_BASE`,
`WORKTREE_PORTS_BACKEND_BASE`. Each test reserves a fresh high-port triple
via `reserved_port_bases()` and uses those as the "defaults" its subprocess sees.

The test names encode what they verify (plan §4.1).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from tests.tools._port_helpers import (
    GENERATOR_REL_PATH,
    bind_listener,
    prepare_worktree,
    reserved_port_bases,
    run_generator,
)


def _env_with_bases(frontend: int, dashboard: int, backend: int) -> dict[str, str]:
    env = os.environ.copy()
    env["WORKTREE_PORTS_FRONTEND_BASE"] = str(frontend)
    env["WORKTREE_PORTS_DASHBOARD_BASE"] = str(dashboard)
    env["WORKTREE_PORTS_BACKEND_BASE"] = str(backend)
    return env


# ---------------------------------------------------------------------------
# Baseline: all ports free
# ---------------------------------------------------------------------------


def test_first_run_picks_offset_zero_when_all_ports_free(tmp_path: Path) -> None:
    worktree = prepare_worktree(tmp_path)

    with reserved_port_bases() as (fe, db, be):
        env = _env_with_bases(fe, db, be)
        result = run_generator(worktree, env=env)
    assert result.returncode == 0, result.stderr

    env_ports = (worktree / ".claude" / "env.ports").read_text()
    assert f"export FRONTEND_PORT={fe}" in env_ports
    assert f"export DASHBOARD_PORT={db}" in env_ports
    assert f"export BACKEND_PORT={be}" in env_ports
    assert f"export BACKEND_URL=http://localhost:{be}" in env_ports

    env_frontend = (worktree / "frontend" / ".env.local").read_text()
    assert f"FRONTEND_PORT={fe}" in env_frontend
    assert f"BACKEND_URL=http://localhost:{be}" in env_frontend

    env_dashboard = (worktree / "tools" / "dev-dashboard" / ".env.local").read_text()
    assert f"DASHBOARD_PORT={db}" in env_dashboard

    launch = json.loads((worktree / ".claude" / "launch.json").read_text())
    ports = [cfg["port"] for cfg in launch["configurations"]]
    assert ports == [fe, db]


def test_first_run_renders_launch_json_with_no_unresolved_tokens(tmp_path: Path) -> None:
    worktree = prepare_worktree(tmp_path)

    with reserved_port_bases() as (fe, db, be):
        env = _env_with_bases(fe, db, be)
        result = run_generator(worktree, env=env)
    assert result.returncode == 0, result.stderr

    launch_text = (worktree / ".claude" / "launch.json").read_text()
    assert f'"port": {fe}' in launch_text
    assert f'"port": {db}' in launch_text
    assert "${" not in launch_text


def test_first_run_renders_all_three_env_files_with_no_unresolved_tokens(tmp_path: Path) -> None:
    worktree = prepare_worktree(tmp_path)

    with reserved_port_bases() as (fe, db, be):
        env = _env_with_bases(fe, db, be)
        result = run_generator(worktree, env=env)
    assert result.returncode == 0, result.stderr

    for rel in (
        ".claude/env.ports",
        "frontend/.env.local",
        "tools/dev-dashboard/.env.local",
    ):
        text = (worktree / rel).read_text()
        assert "${" not in text, f"unresolved token in {rel}: {text!r}"


# ---------------------------------------------------------------------------
# Idempotency & --force
# ---------------------------------------------------------------------------


def test_idempotent_second_run_is_noop_when_all_artifacts_exist(tmp_path: Path) -> None:
    worktree = prepare_worktree(tmp_path)

    with reserved_port_bases() as (fe, db, be):
        env = _env_with_bases(fe, db, be)
        first = run_generator(worktree, env=env)
        assert first.returncode == 0

        targets = [
            worktree / ".claude" / "launch.json",
            worktree / ".claude" / "env.ports",
            worktree / "frontend" / ".env.local",
            worktree / "tools" / "dev-dashboard" / ".env.local",
        ]
        original_mtimes = {p: p.stat().st_mtime_ns for p in targets}

        second = run_generator(worktree, env=env)
    assert second.returncode == 0
    assert "skipping" in second.stdout

    for p in targets:
        assert p.stat().st_mtime_ns == original_mtimes[p], f"{p} was rewritten during a no-op run"


def test_force_flag_regenerates_when_all_artifacts_exist(tmp_path: Path) -> None:
    worktree = prepare_worktree(tmp_path)

    with reserved_port_bases() as (fe, db, be):
        env = _env_with_bases(fe, db, be)
        first = run_generator(worktree, env=env)
        assert first.returncode == 0

        targets = [
            worktree / ".claude" / "launch.json",
            worktree / ".claude" / "env.ports",
            worktree / "frontend" / ".env.local",
            worktree / "tools" / "dev-dashboard" / ".env.local",
        ]
        original_mtimes = {p: p.stat().st_mtime_ns for p in targets}

        # Sleep past mtime granularity so mtimes must differ if rewritten.
        time.sleep(1.1)

        second = run_generator(worktree, "--force", env=env)
    assert second.returncode == 0
    assert "skipping" not in second.stdout

    for p in targets:
        assert p.stat().st_mtime_ns > original_mtimes[p], f"{p} mtime unchanged after --force"

    # Port contents unchanged (offset 0 still free).
    env_ports = (worktree / ".claude" / "env.ports").read_text()
    assert f"export FRONTEND_PORT={fe}" in env_ports


# ---------------------------------------------------------------------------
# Port collision → next offset
# ---------------------------------------------------------------------------


def test_skips_occupied_frontend_port_picks_next_offset(tmp_path: Path) -> None:
    worktree = prepare_worktree(tmp_path)

    with reserved_port_bases() as (fe, db, be):
        env = _env_with_bases(fe, db, be)
        with bind_listener(fe):
            result = run_generator(worktree, env=env)
        assert result.returncode == 0, result.stderr

        env_frontend = (worktree / "frontend" / ".env.local").read_text()
        assert f"FRONTEND_PORT={fe + 10}" in env_frontend
        assert f"BACKEND_URL=http://localhost:{be + 10}" in env_frontend


def test_skips_occupied_dashboard_port_picks_next_offset(tmp_path: Path) -> None:
    worktree = prepare_worktree(tmp_path)

    with reserved_port_bases() as (fe, db, be):
        env = _env_with_bases(fe, db, be)
        with bind_listener(db):
            result = run_generator(worktree, env=env)
        assert result.returncode == 0, result.stderr

        env_dashboard = (worktree / "tools" / "dev-dashboard" / ".env.local").read_text()
        assert f"DASHBOARD_PORT={db + 10}" in env_dashboard


def test_skips_occupied_backend_port_picks_next_offset(tmp_path: Path) -> None:
    worktree = prepare_worktree(tmp_path)

    with reserved_port_bases() as (fe, db, be):
        env = _env_with_bases(fe, db, be)
        with bind_listener(be):
            result = run_generator(worktree, env=env)
        assert result.returncode == 0, result.stderr

        env_ports = (worktree / ".claude" / "env.ports").read_text()
        assert f"export BACKEND_PORT={be + 10}" in env_ports
        assert f"export FRONTEND_PORT={fe + 10}" in env_ports


def test_skips_offset_when_only_one_of_three_is_busy(tmp_path: Path) -> None:
    """Bind dashboard at offset 0 AND offset 10.

    Offset 0 rejected because dashboard (base) is busy.
    Offset 10 rejected because dashboard (base+10) is busy.
    Offset 20 should win.
    """
    worktree = prepare_worktree(tmp_path)

    with reserved_port_bases() as (fe, db, be):
        env = _env_with_bases(fe, db, be)
        with bind_listener(db), bind_listener(db + 10):
            result = run_generator(worktree, env=env)
        assert result.returncode == 0, result.stderr

        env_dashboard = (worktree / "tools" / "dev-dashboard" / ".env.local").read_text()
        assert f"DASHBOARD_PORT={db + 20}" in env_dashboard
        env_frontend = (worktree / "frontend" / ".env.local").read_text()
        assert f"FRONTEND_PORT={fe + 20}" in env_frontend


# ---------------------------------------------------------------------------
# --print mode
# ---------------------------------------------------------------------------


def test_print_mode_does_not_write_files(tmp_path: Path) -> None:
    worktree = prepare_worktree(tmp_path)

    with reserved_port_bases() as (fe, db, be):
        env = _env_with_bases(fe, db, be)
        result = run_generator(worktree, "--print", env=env)
    assert result.returncode == 0, result.stderr
    assert f"FRONTEND_PORT={fe}" in result.stdout
    assert f"DASHBOARD_PORT={db}" in result.stdout
    assert f"BACKEND_PORT={be}" in result.stdout

    assert not (worktree / ".claude" / "launch.json").exists()
    assert not (worktree / ".claude" / "env.ports").exists()
    assert not (worktree / "frontend" / ".env.local").exists()
    assert not (worktree / "tools" / "dev-dashboard" / ".env.local").exists()


# ---------------------------------------------------------------------------
# Template missing / invalid → exit 1
# ---------------------------------------------------------------------------


def _assert_no_outputs_written(worktree: Path) -> None:
    for rel in (
        ".claude/launch.json",
        ".claude/env.ports",
        "frontend/.env.local",
        "tools/dev-dashboard/.env.local",
    ):
        assert not (worktree / rel).exists(), f"{rel} should not exist when generator fails early"
    tmp_leftovers = list(worktree.rglob("*.tmp"))
    assert tmp_leftovers == [], f"leftover .tmp files: {tmp_leftovers}"


def test_missing_launch_template_exits_one_with_clear_message(tmp_path: Path) -> None:
    worktree = prepare_worktree(tmp_path)
    (worktree / ".claude" / "launch.json.template").unlink()

    with reserved_port_bases() as (fe, db, be):
        env = _env_with_bases(fe, db, be)
        result = run_generator(worktree, env=env)
    assert result.returncode == 1
    assert "template" in result.stderr.lower()
    _assert_no_outputs_written(worktree)


def test_missing_frontend_env_template_exits_one_with_clear_message(tmp_path: Path) -> None:
    worktree = prepare_worktree(tmp_path)
    (worktree / ".claude" / "env.frontend.template").unlink()

    with reserved_port_bases() as (fe, db, be):
        env = _env_with_bases(fe, db, be)
        result = run_generator(worktree, env=env)
    assert result.returncode == 1
    assert "template" in result.stderr.lower()
    _assert_no_outputs_written(worktree)


def test_missing_dashboard_env_template_exits_one_with_clear_message(tmp_path: Path) -> None:
    worktree = prepare_worktree(tmp_path)
    (worktree / ".claude" / "env.dashboard.template").unlink()

    with reserved_port_bases() as (fe, db, be):
        env = _env_with_bases(fe, db, be)
        result = run_generator(worktree, env=env)
    assert result.returncode == 1
    assert "template" in result.stderr.lower()
    _assert_no_outputs_written(worktree)


def test_missing_ports_env_template_exits_one_with_clear_message(tmp_path: Path) -> None:
    worktree = prepare_worktree(tmp_path)
    (worktree / ".claude" / "env.ports.template").unlink()

    with reserved_port_bases() as (fe, db, be):
        env = _env_with_bases(fe, db, be)
        result = run_generator(worktree, env=env)
    assert result.returncode == 1
    assert "template" in result.stderr.lower()
    _assert_no_outputs_written(worktree)


def test_template_with_unknown_token_exits_one_with_clear_message(tmp_path: Path) -> None:
    worktree = prepare_worktree(tmp_path)
    bad_template = worktree / ".claude" / "env.frontend.template"
    bad_template.write_text(bad_template.read_text() + "\nMYSTERY=${MYSTERY}\n")

    with reserved_port_bases() as (fe, db, be):
        env = _env_with_bases(fe, db, be)
        result = run_generator(worktree, env=env)
    assert result.returncode == 1
    assert "unresolved" in result.stderr.lower()
    assert "MYSTERY" in result.stderr
    # No .tmp leftovers (atomic-write-per-file cleans them on failure).
    assert list(worktree.rglob("*.tmp")) == []


# ---------------------------------------------------------------------------
# No free offset → exit 2
# ---------------------------------------------------------------------------


def test_no_free_offset_within_range_exits_two(tmp_path: Path) -> None:
    """Cap the offset range and bind every candidate frontend port."""
    worktree = prepare_worktree(tmp_path)

    with reserved_port_bases() as (fe, db, be):
        env = _env_with_bases(fe, db, be)
        env["WORKTREE_PORTS_MAX_OFFSET"] = "10"

        with bind_listener(fe), bind_listener(fe + 10):
            result = run_generator(worktree, env=env)

    assert result.returncode == 2
    assert "could not find a free port bank" in result.stderr.lower() or "no free" in result.stderr.lower()


# ---------------------------------------------------------------------------
# --worktree-root flag
# ---------------------------------------------------------------------------


def test_worktree_root_flag_writes_files_into_that_root(tmp_path: Path) -> None:
    worktree = prepare_worktree(tmp_path)

    cwd_before = Path.cwd()
    os.chdir(tmp_path.parent)
    try:
        with reserved_port_bases() as (fe, db, be):
            env = _env_with_bases(fe, db, be)
            result = run_generator(worktree, env=env)
    finally:
        os.chdir(cwd_before)

    assert result.returncode == 0
    assert (worktree / ".claude" / "launch.json").exists()
    assert (worktree / ".claude" / "env.ports").exists()
    assert (worktree / "frontend" / ".env.local").exists()
    assert (worktree / "tools" / "dev-dashboard" / ".env.local").exists()


# ---------------------------------------------------------------------------
# Invalid args → exit 3
# ---------------------------------------------------------------------------


def test_unknown_flag_exits_three_with_usage(tmp_path: Path) -> None:
    worktree = prepare_worktree(tmp_path)

    with reserved_port_bases() as (fe, db, be):
        env = _env_with_bases(fe, db, be)
        result = run_generator(worktree, "--nonsense", env=env)
    assert result.returncode == 3
    assert "usage" in result.stderr.lower()


# ---------------------------------------------------------------------------
# Read-only .claude/ → exit 1 atomically
# ---------------------------------------------------------------------------


def test_atomic_write_no_partial_on_failure(tmp_path: Path) -> None:
    """A read-only .claude/ forces template renders to fail.

    Assert: no `.tmp` files remain, no final output files are created for the
    read-only outputs, and the script exits non-zero.
    """
    worktree = prepare_worktree(tmp_path)
    (worktree / ".claude").chmod(0o555)
    try:
        with reserved_port_bases() as (fe, db, be):
            env = _env_with_bases(fe, db, be)
            result = run_generator(worktree, env=env)
    finally:
        (worktree / ".claude").chmod(0o755)

    assert result.returncode == 1, result.stdout + result.stderr
    assert list(worktree.rglob("*.tmp")) == []
    assert not (worktree / ".claude" / "env.ports").exists()
    assert not (worktree / ".claude" / "launch.json").exists()


# ---------------------------------------------------------------------------
# Stdout log format
# ---------------------------------------------------------------------------


def test_stdout_log_line_has_expected_prefix_and_ports(tmp_path: Path) -> None:
    worktree = prepare_worktree(tmp_path)

    with reserved_port_bases() as (fe, db, be):
        env = _env_with_bases(fe, db, be)
        result = run_generator(worktree, env=env)
    assert result.returncode == 0
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    expected = f"[setup-worktree-ports] offset=0 frontend={fe} dashboard={db} backend={be}"
    assert expected in lines, f"expected log line not in stdout: {result.stdout!r}"


# ---------------------------------------------------------------------------
# Partial pre-existing state
# ---------------------------------------------------------------------------


def test_idempotency_check_requires_all_four_outputs(tmp_path: Path) -> None:
    worktree = prepare_worktree(tmp_path)

    # Pre-create only one of the four expected outputs — stale content.
    (worktree / ".claude" / "launch.json").write_text("{}\n")

    with reserved_port_bases() as (fe, db, be):
        env = _env_with_bases(fe, db, be)
        result = run_generator(worktree, env=env)
    assert result.returncode == 0, result.stderr
    assert (worktree / ".claude" / "launch.json").exists()
    assert (worktree / ".claude" / "env.ports").exists()
    assert (worktree / "frontend" / ".env.local").exists()
    assert (worktree / "tools" / "dev-dashboard" / ".env.local").exists()
    launch = json.loads((worktree / ".claude" / "launch.json").read_text())
    assert "configurations" in launch


# ---------------------------------------------------------------------------
# Explicit --worktree-root works outside any git repo
# ---------------------------------------------------------------------------


def test_runs_without_git_when_worktree_root_is_explicit(tmp_path: Path) -> None:
    """Even when tmp_path is not a git tree, --worktree-root makes it work."""
    worktree = prepare_worktree(tmp_path)
    scratch = tmp_path / "no-git-here"
    scratch.mkdir()

    cwd_before = Path.cwd()
    os.chdir(scratch)
    try:
        with reserved_port_bases() as (fe, db, be):
            env = _env_with_bases(fe, db, be)
            result = run_generator(worktree, env=env)
    finally:
        os.chdir(cwd_before)

    assert result.returncode == 0, result.stderr
    assert (worktree / ".claude" / "launch.json").exists()


# ---------------------------------------------------------------------------
# Sanity check on the real repo
# ---------------------------------------------------------------------------


def test_helper_generator_path_resolves_in_real_repo() -> None:
    """Sanity: the real repo ships an executable generator at the expected path."""
    from tests.tools._port_helpers import REPO_ROOT

    gen = REPO_ROOT / GENERATOR_REL_PATH
    assert gen.is_file()
    assert os.access(gen, os.X_OK), f"{gen} must be executable"

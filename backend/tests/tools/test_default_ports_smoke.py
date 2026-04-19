"""Backwards-compat smoke for G4 — default ports.

Locks in that `frontend/vite.config.ts` and `tools/dev-dashboard/vite.config.ts`
still bind their historical defaults (3000 / 5179) when no `.env.local` is
present.

Both tests boot the real Vite dev server via `npm run <script>` against the
real on-disk `frontend/` or `tools/dev-dashboard/` directory (so the test
sees the frontend-engineer's parameterized configs). The test:

  1. Ensures `node_modules` is already installed (skip if not — we don't do
     network installs inside pytest).
  2. Verifies the target default port is free on 127.0.0.1 before launching
     (skip if already busy — running dev server on the developer's box).
  3. Temporarily renames any existing `.env.local` so the Vite config sees
     the empty default.
  4. Launches vite in a background subprocess.
  5. Polls the target port with TCP connect until reachable (15s timeout).
  6. SIGTERMs the subprocess and asserts it reached the port before timeout.

Both tests skip cleanly when the environment isn't ready, so they don't block
the agent validation suite on a fresh clone / in CI that doesn't `npm install`.
"""

from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pytest

from tests.tools._port_helpers import REPO_ROOT


def _port_free(port: int) -> bool:
    """Return True iff the port is free on BOTH IPv4 and IPv6 localhost.

    Vite checks both families; a bind-fail on either means "port in use".
    """
    for family, addr in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
        try:
            s = socket.socket(family, socket.SOCK_STREAM)
        except OSError:
            continue  # family not supported on this host
        try:
            s.settimeout(0.25)
            try:
                s.connect((addr, port))
                return False  # something is listening
            except (ConnectionRefusedError, socket.timeout, OSError):
                pass
        finally:
            s.close()
    return True


def _wait_for_port(port: int, timeout: float = 15.0) -> bool:
    """Poll both IPv4 and IPv6 localhost until something accepts on port."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for family, addr in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
            try:
                s = socket.socket(family, socket.SOCK_STREAM)
            except OSError:
                continue
            try:
                s.settimeout(0.5)
                try:
                    s.connect((addr, port))
                    return True
                except (ConnectionRefusedError, socket.timeout, OSError):
                    pass
            finally:
                s.close()
        time.sleep(0.25)
    return False


@contextmanager
def _temporarily_hide_env_local(project_root: Path) -> Iterator[None]:
    """Rename `<project_root>/.env.local` (if present) during the test so that
    Vite sees no env file and falls back to the in-config defaults.
    """
    env_local = project_root / ".env.local"
    backup = project_root / ".env.local.smoke-bak"
    had_original = env_local.exists()
    if had_original:
        env_local.rename(backup)
    try:
        yield
    finally:
        if had_original and backup.exists():
            if env_local.exists():
                env_local.unlink()
            backup.rename(env_local)


def _require_npm() -> None:
    if shutil.which("npm") is None:
        pytest.skip("npm not on PATH")


def _require_node_modules(project_root: Path) -> None:
    if not (project_root / "node_modules").is_dir():
        pytest.skip(f"{project_root}/node_modules missing — skip (run npm ci first)")


def _boot_vite_and_check_port(
    project_root: Path,
    npm_script: str,
    default_port: int,
) -> None:
    _require_npm()
    _require_node_modules(project_root)
    if not _port_free(default_port):
        pytest.skip(f"port {default_port} already in use on this host")

    with _temporarily_hide_env_local(project_root):
        env = os.environ.copy()
        # Belt-and-suspenders: strip the port env overrides that might be set
        # from the test worktree's own .claude/env.ports inherited into pytest.
        for k in ("FRONTEND_PORT", "DASHBOARD_PORT", "BACKEND_URL", "BACKEND_PORT"):
            env.pop(k, None)

        proc = subprocess.Popen(
            ["npm", "--prefix", str(project_root), "run", npm_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            # New process group so we can SIGTERM the whole tree on cleanup.
            start_new_session=True,
        )
        try:
            reached = _wait_for_port(default_port, timeout=15.0)
        finally:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait(timeout=5)

    assert reached, f"vite did not bind {default_port} within 15s"


def test_frontend_vite_dev_default_port_when_no_env_file() -> None:
    _boot_vite_and_check_port(
        project_root=REPO_ROOT / "frontend",
        npm_script="dev",
        default_port=3000,
    )


def test_dashboard_vite_default_port_when_no_env_file() -> None:
    _boot_vite_and_check_port(
        project_root=REPO_ROOT / "tools" / "dev-dashboard",
        npm_script="dashboard",
        default_port=5179,
    )

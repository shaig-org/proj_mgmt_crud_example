"""Test helpers for the setup-worktree-ports generator suite.

Private module: leading underscore prevents pytest from collecting it as a
test file. Tests import from here explicitly.
"""

from __future__ import annotations

import contextlib
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Iterator

# Repo root, resolved by walking up from this file. This module lives at
# backend/tests/tools/_port_helpers.py, so the repo root is parents[3].
REPO_ROOT: Path = Path(__file__).resolve().parents[3]

GENERATOR_REL_PATH: str = "devtools/setup-worktree-ports.sh"
TEMPLATE_FILES: tuple[str, ...] = (
    ".claude/launch.json.template",
    ".claude/env.frontend.template",
    ".claude/env.dashboard.template",
    ".claude/env.ports.template",
)


@contextlib.contextmanager
def bind_listener(port: int) -> Iterator[socket.socket]:
    """Bind 127.0.0.1:port and listen. Yields the socket; caller closes on exit."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Intentionally do NOT set SO_REUSEADDR — we want bind() to fail loudly if
    # the port is already in use (which would confuse our tests).
    try:
        sock.bind(("127.0.0.1", port))
        sock.listen(1)
        yield sock
    finally:
        sock.close()


def reserve_free_port_base(step: int = 10, total_ports: int = 3001) -> int:
    """Return a high port base B such that B, B+step, ..., B+total_ports-1 are all bind-free.

    `total_ports` is the FULL range the caller needs probed — by default 3001,
    which covers the three port groups used by `reserved_port_bases`
    (frontend [0..1000], dashboard [1000..2000], backend [2000..3000]) PLUS
    the generator's probe window at each. Earlier this only probed the first
    1000 ports starting at `base`, leaving the dashboard's upper half and the
    entire backend range unverified — which produced a flaky failure under
    parallel test load when an ephemeral connection happened to live inside
    one of the unverified slices.

    Stays out of the macOS / Linux ephemeral-port ranges (49152+ on macOS,
    32768+ on Linux) by capping bases at 30000.
    """
    import random

    # Try up to 10 random high bases. Each attempt probes `total_ports` ports.
    for _ in range(10):
        # Pick a base in [10000, 30000] aligned to 1000. This avoids:
        #   - <10000: well-known service collisions
        #   - >30000: Linux's default ephemeral range (32768-60999)
        #   - >49152: macOS's default ephemeral range (49152-65535)
        # so the probed window is always outside any host's ephemeral range.
        base = random.randrange(10000, 30000, 1000)
        ok = True
        for n in range(0, total_ports, step):
            candidate = base + n
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.bind(("127.0.0.1", candidate))
            except OSError:
                ok = False
                s.close()
                break
            else:
                s.close()
        if ok:
            return base
    raise RuntimeError("could not find a free high port base for tests")


@contextlib.contextmanager
def reserved_port_bases() -> Iterator[tuple[int, int, int]]:
    """Yield three disjoint high port bases (frontend, dashboard, backend)
    guaranteed bind-free across the full 3000-port window the generator scans.

    Bases are spaced 1000 apart so tests can reason about offset arithmetic
    (e.g. base+10 for "offset 10") without port-range collisions. The
    generator probes 100 offsets per group, so the underlying reserve covers
    all 3 * 1001 = 3003 candidate ports (rounded up to 3001 for cleanliness;
    the extra one ensures `frontend + 2000 + 990` is included).
    """
    frontend = reserve_free_port_base()
    dashboard = frontend + 1000
    backend = frontend + 2000
    yield (frontend, dashboard, backend)


def prepare_worktree(tmp_path: Path) -> Path:
    """Copy generator + the four templates from the repo into tmp_path.

    Layout after this call:
        tmp_path/
            devtools/setup-worktree-ports.sh   (chmod +x)
            .claude/launch.json.template
            .claude/env.frontend.template
            .claude/env.dashboard.template
            .claude/env.ports.template
    """
    (tmp_path / "devtools").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    # Pre-create the output-target parent directories so the generator doesn't
    # have to (it does anyway, but tests that poke these paths benefit).
    (tmp_path / "frontend").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tools" / "dev-dashboard").mkdir(parents=True, exist_ok=True)

    src_generator = REPO_ROOT / GENERATOR_REL_PATH
    dst_generator = tmp_path / GENERATOR_REL_PATH
    shutil.copy2(src_generator, dst_generator)
    dst_generator.chmod(0o755)

    for rel in TEMPLATE_FILES:
        shutil.copy2(REPO_ROOT / rel, tmp_path / rel)

    return tmp_path


def run_generator(
    worktree: Path,
    *args: str,
    env: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> subprocess.CompletedProcess[str]:
    """Invoke the generator with --worktree-root <worktree>.

    Extra positional args are passed verbatim. Returns the CompletedProcess.
    """
    cmd = [
        str(worktree / GENERATOR_REL_PATH),
        "--worktree-root",
        str(worktree),
        *args,
    ]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
        check=False,
    )

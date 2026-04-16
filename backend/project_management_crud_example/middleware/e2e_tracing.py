"""E2E request call tracer — captures server-side function call traces per HTTP request.

Only active when E2E_TESTING=true and the request carries X-E2E-Scenario-ID.
Uses sys.monitoring (Python 3.12+) with contextvars for async-safe per-request isolation.
Writes backend/e2e-traces/{correlation_id}/req-{NNN}.json after each request.
"""

import asyncio
import json
import os
import sys
import time
import types
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

_TOOL_ID = sys.monitoring.PROFILER_ID

_FILTER_SUBSTRINGS: tuple[str, ...] = (
    "site-packages",
    "/lib/python",
    "/lib64/python",
    "/.venv/",
    "/venv/",
    "importlib",
    "starlette/",
    "fastapi/",
    "uvicorn/",
    "anyio/",
    "asyncio",
    "middleware/e2e_tracing",  # skip self
)

# Module-level project root for path filtering
# __file__ = .../middleware/e2e_tracing.py → parent.parent = project_management_crud_example/
_MODULE_ROOT = str(Path(__file__).resolve().parent.parent)

_current_buffer: ContextVar[Optional["RequestTraceBuffer"]] = ContextVar("e2e_trace_buffer", default=None)
_tracer_active = False


@dataclass
class CallEvent:
    event: str
    file: str
    function: str
    line: int
    depth: int
    timestamp_ns: int


@dataclass
class RequestTraceBuffer:
    seq: int
    method: str
    path: str
    start_ns: int = field(default_factory=time.monotonic_ns)
    start_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    events: list[CallEvent] = field(default_factory=list)
    depth: int = 0


def _should_trace(filename: str) -> bool:
    if not filename.startswith(_MODULE_ROOT):
        return False
    for s in _FILTER_SUBSTRINGS:
        if s in filename:
            return False
    return True


def _on_py_start(code: types.CodeType, _instruction_offset: int) -> None:
    buf = _current_buffer.get()
    if buf is None:
        return
    filename: str = code.co_filename
    if not _should_trace(filename):
        return
    rel = filename[len(_MODULE_ROOT) + 1 :]  # strip module root prefix
    buf.events.append(
        CallEvent(
            event="call",
            file=rel,
            function=code.co_qualname,
            line=code.co_firstlineno,
            depth=buf.depth,
            timestamp_ns=time.monotonic_ns() - buf.start_ns,
        )
    )
    buf.depth += 1


def _on_py_return(code: types.CodeType, _instruction_offset: int, _retval: object) -> None:
    buf = _current_buffer.get()
    if buf is None:
        return
    filename: str = code.co_filename
    if not _should_trace(filename):
        return
    buf.depth = max(0, buf.depth - 1)
    rel = filename[len(_MODULE_ROOT) + 1 :]
    buf.events.append(
        CallEvent(
            event="return",
            file=rel,
            function=code.co_qualname,
            line=code.co_firstlineno,
            depth=buf.depth,
            timestamp_ns=time.monotonic_ns() - buf.start_ns,
        )
    )


def _start_tracer() -> None:
    global _tracer_active
    if _tracer_active:
        return
    sys.monitoring.use_tool_id(_TOOL_ID, "e2e-tracer")
    sys.monitoring.register_callback(_TOOL_ID, sys.monitoring.events.PY_START, _on_py_start)
    sys.monitoring.register_callback(_TOOL_ID, sys.monitoring.events.PY_RETURN, _on_py_return)
    sys.monitoring.set_events(_TOOL_ID, sys.monitoring.events.PY_START | sys.monitoring.events.PY_RETURN)
    _tracer_active = True


class E2eTracingMiddleware(BaseHTTPMiddleware):
    """Records per-request server-side call traces during E2E scenario runs.

    Only activates when E2E_TESTING=true and X-E2E-Scenario-ID header is present.
    Writes backend/e2e-traces/{correlation_id}/req-{NNN}.json for each traced request.
    Output directory configurable via E2E_TRACES_DIR env var (default: backend/e2e-traces/).
    """

    _seq_locks: dict[str, asyncio.Lock] = {}
    _seq_counters: dict[str, int] = {}

    def _get_output_dir(self) -> Path:
        # parents[2] of middleware/e2e_tracing.py = backend/
        default = Path(__file__).resolve().parents[2] / "e2e-traces"
        return Path(os.environ.get("E2E_TRACES_DIR", str(default)))

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if os.environ.get("E2E_TESTING") != "true":
            return await call_next(request)

        scenario_id = request.headers.get("X-E2E-Scenario-ID")
        if not scenario_id:
            return await call_next(request)

        _start_tracer()

        # Atomic creation of the per-scenario lock (setdefault is thread-safe in CPython)
        self._seq_locks.setdefault(scenario_id, asyncio.Lock())
        async with self._seq_locks[scenario_id]:
            seq = self._seq_counters.get(scenario_id, 0) + 1
            self._seq_counters[scenario_id] = seq

        buf = RequestTraceBuffer(seq=seq, method=request.method, path=str(request.url.path))
        token = _current_buffer.set(buf)
        start = time.monotonic()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration_ms = int((time.monotonic() - start) * 1000)
            _current_buffer.reset(token)
            await self._write_trace(scenario_id, buf, status_code, duration_ms)

    async def _write_trace(
        self,
        scenario_id: str,
        buf: RequestTraceBuffer,
        status_code: int,
        duration_ms: int,
    ) -> None:
        out_dir = self._get_output_dir() / scenario_id
        out_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "seq": buf.seq,
            "method": buf.method,
            "path": buf.path,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "timestamp_ms": buf.start_ms,
            "call_events": [
                {
                    "event": e.event,
                    "file": e.file,
                    "function": e.function,
                    "line": e.line,
                    "depth": e.depth,
                    "timestamp_ns": e.timestamp_ns,
                }
                for e in buf.events
            ],
        }
        out_file = out_dir / f"req-{buf.seq:03d}.json"
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: out_file.write_text(json.dumps(data, indent=2), encoding="utf-8"),
        )

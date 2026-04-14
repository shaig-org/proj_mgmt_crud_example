# Plan: Add E2E Request Tracing to Scenarios

## Overview

Connect Playwright scenario tests to server-side call traces via HTTP correlation headers. Each E2E scenario already generates a `correlationId` (injected as `window.__CORRELATION_ID` in `frontend/e2e/helpers/scenario.ts`). We propagate this via the `X-E2E-Scenario-ID` HTTP header, capture it in a FastAPI middleware, and record per-request call traces using Python's `sys.monitoring` (Python 3.12+). The dev dashboard gets a new "E2E Traces" aspect to display them.

## Architecture

```
Playwright scenario test
  └── correlationId: "create-project-1734567890123-w0"
      injected into window.__CORRELATION_ID
      
Frontend (api.ts axios interceptor)
  └── reads window.__CORRELATION_ID
      adds X-E2E-Scenario-ID header on every API request

Backend E2eTracingMiddleware (passive in normal runs)
  ├── skips if E2E_TESTING != "true"  (env checked at request time)
  ├── skips if X-E2E-Scenario-ID header absent
  ├── sets contextvars.ContextVar[RequestTraceBuffer] (async-safe per-request isolation)
  ├── sys.monitoring.PROFILER_ID captures call/return events (project files only)
  │   filters: site-packages, stdlib, fastapi, starlette, uvicorn, asyncio, and itself
  └── writes backend/e2e-traces/{correlation_id}/req-{NNN}.json on response

Dev Dashboard — new "E2E Traces" aspect
  ├── artifact URL: /artifacts/e2e-traces/ → backend/e2e-traces/
  ├── lists correlation ID directories (each is a scenario run)
  ├── shows request list (method, path, status, duration_ms) for selected scenario
  └── shows collapsible call event tree (depth-indented) for selected request
```

## Output Format

`backend/e2e-traces/{correlation_id}/req-001.json`:
```json
{
  "seq": 1,
  "method": "POST",
  "path": "/auth/login",
  "status_code": 200,
  "duration_ms": 12,
  "timestamp_ms": 1734567890123,
  "call_events": [
    {"event": "call",   "file": "routers/auth_api.py",       "function": "login",                "line": 45, "depth": 0, "timestamp_ns": 0},
    {"event": "call",   "file": "capabilities/__init__.py",  "function": "AuthCapability.login", "line": 88, "depth": 1, "timestamp_ns": 210},
    {"event": "return", "file": "capabilities/__init__.py",  "function": "AuthCapability.login", "line": 88, "depth": 1, "timestamp_ns": 990},
    {"event": "return", "file": "routers/auth_api.py",       "function": "login",                "line": 45, "depth": 0, "timestamp_ns": 1200}
  ]
}
```

## Files to Create / Modify

### Backend

| File | Action | Purpose |
|------|--------|---------|
| `backend/project_management_crud_example/middleware/__init__.py` | **Create** | Package marker |
| `backend/project_management_crud_example/middleware/e2e_tracing.py` | **Create** | Middleware + call tracer |
| `backend/project_management_crud_example/app.py` | **Modify** | Register middleware unconditionally |
| `backend/tests/api/test_e2e_tracing_middleware.py` | **Create** | API tests for middleware |
| `.gitignore` (root) | **Modify** | Add `backend/e2e-traces/` |

### Frontend

| File | Action | Purpose |
|------|--------|---------|
| `frontend/src/services/api.ts` | **Modify** | Add `X-E2E-Scenario-ID` header in axios interceptor |

### Dev Dashboard

| File | Action | Purpose |
|------|--------|---------|
| `tools/dev-dashboard/src/aspects/e2e-traces/types.ts` | **Create** | TypeScript types |
| `tools/dev-dashboard/src/aspects/e2e-traces/E2eTracesAspect.tsx` | **Create** | UI component |
| `tools/dev-dashboard/src/aspects/index.ts` | **Modify** | Register `e2eTracesAspect` |
| `tools/dev-dashboard/scripts/aspects.config.mjs` | **Modify** | Add e2e-traces config entry |
| `tools/dev-dashboard/vite.config.ts` | **Modify** | Add `/e2e-traces` mount + `fs.allow` entry |
| `tools/dev-dashboard/tests/fixtures/e2e-traces/test-scenario-123/req-001.json` | **Create** | Fixture for unit tests |
| `tools/dev-dashboard/tests/fixtures/e2e-traces/test-scenario-123/req-002.json` | **Create** | Fixture for unit tests |
| `tools/dev-dashboard/tests/unit/e2eTraces.test.ts` | **Create** | Unit tests for aspect loader |
| `tools/dev-dashboard/tests/smoke/fixtures.ts` | **Modify** | Add `e2eTraces: boolean` to Layout |
| `tools/dev-dashboard/tests/smoke/dashboard.smoke.spec.ts` | **Modify** | Test E2E Traces tab |

## Backend Implementation Details

### `middleware/e2e_tracing.py`

```python
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
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

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

_current_buffer: ContextVar[Optional["RequestTraceBuffer"]] = ContextVar(
    "e2e_trace_buffer", default=None
)

_tracer_active = False
_project_root: str = ""


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
```

Key design points:
- `_current_buffer` is a `ContextVar` — each asyncio task (= each request) has its own value
- `depth` is stored on the buffer (not a global) so concurrent requests track their own depth
- `_tracer_active` is a module-level bool; tracer starts once on first traced request, never stops
- Project root determined at startup: `Path(__file__).resolve().parents[2]` (3 levels up from `middleware/e2e_tracing.py` lands at the package root under `backend/`)

Actually, the project root for path filtering should be the backend package root: `backend/project_management_crud_example/`. The `_should_trace()` function checks `filename.startswith(_project_root)`.

`_project_root` is set to `str(Path(__file__).resolve().parent.parent)` — that's `backend/project_management_crud_example/`.

For the output directory default: `Path(__file__).resolve().parents[3] / "e2e-traces"` (going up from `middleware/e2e_tracing.py` → `middleware/` → `project_management_crud_example/` → `backend/` → repo root... wait, no):
- `__file__` = `backend/project_management_crud_example/middleware/e2e_tracing.py`
- `.parent` = `backend/project_management_crud_example/middleware/`
- `.parent.parent` = `backend/project_management_crud_example/`
- `.parent.parent.parent` = `backend/`
- `.parent.parent.parent / "e2e-traces"` = `backend/e2e-traces/`

Yes, that's correct. But use `E2E_TRACES_DIR` env var override for testability.

### `app.py` changes

Add at the top of includes (AFTER CORSMiddleware, which must be outermost):
```python
from project_management_crud_example.middleware.e2e_tracing import E2eTracingMiddleware

app.add_middleware(E2eTracingMiddleware)
```

Add this BEFORE the CORSMiddleware line (Starlette applies middleware in reverse order — last-added runs outermost). Since we want CORS to run first, add E2eTracingMiddleware AFTER CORSMiddleware (it runs second/inner).

Actually Starlette middleware is a stack: the first `add_middleware` call creates the outermost layer. CORSMiddleware should be outermost. So:
```python
app.add_middleware(CORSMiddleware, ...)   # outermost (first added)
app.add_middleware(E2eTracingMiddleware)  # inner (second added)
```

This is the current order — CORSMiddleware is added first, so it's outermost. Adding E2eTracingMiddleware after means it's inner. This is correct because CORS headers need to be added even to traced requests.

### Test approach

```python
# test_e2e_tracing_middleware.py
class TestE2eTracingMiddleware:
    def test_no_trace_without_header(self, client, monkeypatch, tmp_path):
        monkeypatch.setenv("E2E_TESTING", "true")
        monkeypatch.setenv("E2E_TRACES_DIR", str(tmp_path))
        response = client.get("/health")  # no X-E2E-Scenario-ID header
        assert response.status_code == 200
        assert not any(tmp_path.iterdir())  # no files written

    def test_trace_file_written_with_header(self, client, monkeypatch, tmp_path):
        monkeypatch.setenv("E2E_TESTING", "true")
        monkeypatch.setenv("E2E_TRACES_DIR", str(tmp_path))
        response = client.get(
            "/health",
            headers={"X-E2E-Scenario-ID": "test-scenario-123"}
        )
        assert response.status_code == 200
        trace_dir = tmp_path / "test-scenario-123"
        assert trace_dir.exists()
        files = sorted(trace_dir.glob("req-*.json"))
        assert len(files) == 1

    def test_trace_file_format(self, client, monkeypatch, tmp_path):
        monkeypatch.setenv("E2E_TESTING", "true")
        monkeypatch.setenv("E2E_TRACES_DIR", str(tmp_path))
        client.get("/health", headers={"X-E2E-Scenario-ID": "test-scenario-fmt"})
        trace_file = next((tmp_path / "test-scenario-fmt").glob("req-*.json"))
        data = json.loads(trace_file.read_text())
        assert data["seq"] == 1
        assert data["method"] == "GET"
        assert data["path"] == "/health"
        assert data["status_code"] == 200
        assert isinstance(data["duration_ms"], int)
        assert isinstance(data["timestamp_ms"], int)
        assert isinstance(data["call_events"], list)

    def test_call_events_present(self, client, monkeypatch, tmp_path):
        monkeypatch.setenv("E2E_TESTING", "true")
        monkeypatch.setenv("E2E_TRACES_DIR", str(tmp_path))
        client.get("/health", headers={"X-E2E-Scenario-ID": "test-scenario-events"})
        trace_file = next((tmp_path / "test-scenario-events").glob("req-*.json"))
        data = json.loads(trace_file.read_text())
        assert len(data["call_events"]) > 0
        for evt in data["call_events"]:
            assert evt["event"] in ("call", "return")
            assert "file" in evt
            assert "function" in evt
            assert isinstance(evt["depth"], int)

    def test_call_events_filtered_to_project_files(self, client, monkeypatch, tmp_path):
        monkeypatch.setenv("E2E_TESTING", "true")
        monkeypatch.setenv("E2E_TRACES_DIR", str(tmp_path))
        client.get("/health", headers={"X-E2E-Scenario-ID": "test-scenario-filter"})
        trace_file = next((tmp_path / "test-scenario-filter").glob("req-*.json"))
        data = json.loads(trace_file.read_text())
        for evt in data["call_events"]:
            assert "site-packages" not in evt["file"]
            assert "starlette/" not in evt["file"]
            assert "fastapi/" not in evt["file"]

    def test_multiple_requests_get_sequential_files(self, client, monkeypatch, tmp_path):
        monkeypatch.setenv("E2E_TESTING", "true")
        monkeypatch.setenv("E2E_TRACES_DIR", str(tmp_path))
        cid = "test-scenario-multi"
        client.get("/health", headers={"X-E2E-Scenario-ID": cid})
        client.get("/health", headers={"X-E2E-Scenario-ID": cid})
        files = sorted((tmp_path / cid).glob("req-*.json"))
        assert len(files) == 2
        assert files[0].name == "req-001.json"
        assert files[1].name == "req-002.json"
        assert json.loads(files[0].read_text())["seq"] == 1
        assert json.loads(files[1].read_text())["seq"] == 2

    def test_inactive_without_e2e_testing_env(self, client, monkeypatch, tmp_path):
        monkeypatch.delenv("E2E_TESTING", raising=False)
        monkeypatch.setenv("E2E_TRACES_DIR", str(tmp_path))
        client.get("/health", headers={"X-E2E-Scenario-ID": "test-no-e2e"})
        assert not any(tmp_path.iterdir())
```

Note: The `monkeypatch` fixture + `tmp_path` are pytest builtins, no import needed.

## Frontend Implementation Details

### `frontend/src/services/api.ts`

In the existing request interceptor (lines 114-119), extend to add the correlation header:

```typescript
this.client.interceptors.request.use((config) => {
  if (this.token) {
    config.headers.Authorization = `Bearer ${this.token}`;
  }
  // Propagate E2E scenario correlation ID if present (injected by scenario test fixture)
  const cid = (window as Window & { __CORRELATION_ID?: string }).__CORRELATION_ID;
  if (cid) {
    config.headers['X-E2E-Scenario-ID'] = cid;
  }
  return config;
});
```

No separate type declaration file needed — the cast is inline and self-documenting.

## Dev Dashboard Implementation Details

### `E2eTracesAspect.tsx` structure

```
E2eTracesAspect
  ├── loadE2eTraces()
  │    ├── GET /artifacts/e2e-traces/         → lists correlation_id dirs
  │    └── for each dir: GET .../req-001.json, req-002.json, ...
  ├── E2eTracesBody({ data: E2eTracesData })
  │    ├── left: scenario list (correlation_id buttons)
  │    └── right: selected scenario
  │         ├── request list (seq, method, path, status badge, duration)
  │         └── call event tree for selected request
  │              └── div.call-events-tree
  │                   └── for each event: indented row with depth * 16px padding
  │                        file:function (line N)
```

### `aspects.config.mjs` addition

```javascript
{
  id: 'e2e-traces',
  title: 'E2E Traces',
  sourceRoots: ['frontend/e2e/scenarios'],
  artifacts: [
    {
      url: '/artifacts/e2e-traces/',
      label: 'e2e-traces/',
      repoPath: 'backend/e2e-traces/',
      fsPath: 'backend/e2e-traces',
    },
  ],
  refreshCommand: 'npm --prefix frontend run e2e:scenarios',
  refreshCwd: '<repo-root>',
  refreshDescription:
    're-runs E2E scenario tests; backend E2E tracing middleware writes per-request call traces under backend/e2e-traces/.',
},
```

### `vite.config.ts` addition

In `mounts`:
```typescript
'/e2e-traces': path.resolve(repoRoot, 'backend/e2e-traces'),
```

In `server.fs.allow`:
```typescript
path.resolve(repoRoot, 'backend/e2e-traces'),
```

### Test fixtures

`tests/fixtures/e2e-traces/test-scenario-123/req-001.json`:
```json
{
  "seq": 1,
  "method": "GET",
  "path": "/health",
  "status_code": 200,
  "duration_ms": 5,
  "timestamp_ms": 1734567890000,
  "call_events": [
    {"event": "call",   "file": "routers/health.py", "function": "health_check", "line": 10, "depth": 0, "timestamp_ns": 0},
    {"event": "return", "file": "routers/health.py", "function": "health_check", "line": 10, "depth": 0, "timestamp_ns": 500}
  ]
}
```

`tests/fixtures/e2e-traces/test-scenario-123/req-002.json`:
```json
{
  "seq": 2,
  "method": "POST",
  "path": "/auth/login",
  "status_code": 200,
  "duration_ms": 12,
  "timestamp_ms": 1734567890100,
  "call_events": [
    {"event": "call",   "file": "routers/auth_api.py", "function": "login", "line": 45, "depth": 0, "timestamp_ns": 0},
    {"event": "call",   "file": "capabilities/__init__.py", "function": "AuthCapability.authenticate", "line": 88, "depth": 1, "timestamp_ns": 100},
    {"event": "return", "file": "capabilities/__init__.py", "function": "AuthCapability.authenticate", "line": 88, "depth": 1, "timestamp_ns": 900},
    {"event": "return", "file": "routers/auth_api.py", "function": "login", "line": 45, "depth": 0, "timestamp_ns": 1100}
  ]
}
```

### Unit tests (`e2eTraces.test.ts`)

```typescript
describe('E2E Traces aspect', () => {
  it('parses request file correctly', ...)
  it('handles directory with multiple requests', ...)
  it('sorts requests by seq number', ...)
  it('renders request method and path', ...)
  it('renders call event depth indentation', ...)
})
```

### Smoke test additions

Add `e2eTraces: boolean` to `Layout` type in `fixtures.ts`.
In `withArtifacts()`, if `layout.e2eTraces`, copy `FIXTURES/e2e-traces` → `TMP_REPO/backend/e2e-traces`.
Add source root stub for `e2e-traces` staleness.

In `dashboard.smoke.spec.ts`:
- `test_e2e_traces_missing` — no artifacts → shows refresh hint
- `test_e2e_traces_with_data` — artifacts present → tab visible, scenario list shows, requests show

## Notes on agent_tracer

No changes needed to the `agent_tracer` library. We implement our own `sys.monitoring` wrapper (`_on_py_start`, `_on_py_return`) using `contextvars` for async safety. The call event JSON schema matches agent_tracer's `call_traces.json` format (same fields: event, file, function, line, depth, timestamp_ns) but organized per-HTTP-request rather than per-pytest-test.

Future work: the trace_analyzer Rust CLI could be extended to index E2E call traces (without requiring `.coverage` data) to enable `trace query --file routers/auth_api.py` to return BOTH pytest scenarios AND E2E scenarios that covered that file.

## Gitignore

Add to root `.gitignore`:
```
# E2E tracing artifacts (generated by backend E2E tracing middleware)
backend/e2e-traces/
```

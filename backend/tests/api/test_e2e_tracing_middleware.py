"""Tests for E2eTracingMiddleware — per-request call trace recording during E2E runs."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.conftest import client  # noqa: F401


class TestE2eTracingMiddleware:
    def test_no_trace_without_header(self, client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """No trace file is written when X-E2E-Scenario-ID header is absent."""
        monkeypatch.setenv("E2E_TESTING", "true")
        monkeypatch.setenv("E2E_TRACES_DIR", str(tmp_path))
        response = client.get("/health")
        assert response.status_code == 200
        assert not any(tmp_path.iterdir())

    def test_trace_file_written_with_header(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A trace file is written under the correlation ID directory when header is present."""
        monkeypatch.setenv("E2E_TESTING", "true")
        monkeypatch.setenv("E2E_TRACES_DIR", str(tmp_path))
        response = client.get(
            "/health",
            headers={"X-E2E-Scenario-ID": "test-scenario-123"},
        )
        assert response.status_code == 200
        trace_dir = tmp_path / "test-scenario-123"
        assert trace_dir.exists()
        files = sorted(trace_dir.glob("req-*.json"))
        assert len(files) == 1

    def test_trace_file_format(self, client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Trace file contains all required fields with correct types."""
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

    def test_call_events_present(self, client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Trace file contains at least one call event with required fields."""
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

    def test_call_events_filtered_to_project_files(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Call events reference only project source files, not site-packages or framework internals."""
        monkeypatch.setenv("E2E_TESTING", "true")
        monkeypatch.setenv("E2E_TRACES_DIR", str(tmp_path))
        client.get("/health", headers={"X-E2E-Scenario-ID": "test-scenario-filter"})
        trace_file = next((tmp_path / "test-scenario-filter").glob("req-*.json"))
        data = json.loads(trace_file.read_text())
        for evt in data["call_events"]:
            assert "site-packages" not in evt["file"]
            assert "starlette/" not in evt["file"]
            assert "fastapi/" not in evt["file"]

    def test_multiple_requests_get_sequential_files(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Multiple requests with the same correlation ID produce sequentially numbered files."""
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

    def test_inactive_without_e2e_testing_env(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Middleware does not write any trace files when E2E_TESTING env var is not set."""
        monkeypatch.delenv("E2E_TESTING", raising=False)
        monkeypatch.setenv("E2E_TRACES_DIR", str(tmp_path))
        client.get("/health", headers={"X-E2E-Scenario-ID": "test-no-e2e"})
        assert not any(tmp_path.iterdir())

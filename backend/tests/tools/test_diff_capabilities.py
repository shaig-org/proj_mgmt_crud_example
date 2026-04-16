"""Tests for the git-based capability diff tool."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List
from unittest.mock import patch

from project_management_crud_example.tools.analyze_capabilities import RouteEntry
from project_management_crud_example.tools.diff_capabilities import (
    WORKING_TREE_REF,
    build_git_diff_doc,
    load_routes_at_ref,
    resolve_commit,
    write_git_diff,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _entry(method: str, path: str, *caps: str) -> RouteEntry:
    return RouteEntry(method=method, path=path, handler="mod.fn", capabilities=tuple(sorted(caps)))


# ---------------------------------------------------------------------------
# resolve_commit
# ---------------------------------------------------------------------------


def test_resolve_commit_returns_sha_on_success(tmp_path: Path) -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "abc1234567890\n"
        result = resolve_commit("main", tmp_path)
    assert result == "abc1234567890"
    mock_run.assert_called_once()


def test_resolve_commit_returns_none_on_failure(tmp_path: Path) -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = ""
        result = resolve_commit("nonexistent-branch", tmp_path)
    assert result is None
    mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# load_routes_at_ref
# ---------------------------------------------------------------------------


def test_load_routes_at_ref_parses_valid_json(tmp_path: Path) -> None:
    payload = json.dumps(
        {
            "routes": [
                {"method": "GET", "path": "/api/x", "handler": "mod.fn", "capabilities": ["XReadCapability"]},
            ]
        }
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = payload
        routes = load_routes_at_ref("HEAD", tmp_path)
    assert routes is not None
    assert len(routes) == 1
    assert routes[0].path == "/api/x"
    assert routes[0].capabilities == ("XReadCapability",)


def test_load_routes_at_ref_returns_none_when_git_fails(tmp_path: Path) -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 128
        mock_run.return_value.stdout = ""
        routes = load_routes_at_ref("missing-ref", tmp_path)
    assert routes is None


def test_load_routes_at_ref_returns_none_on_malformed_json(tmp_path: Path) -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "not json {"
        routes = load_routes_at_ref("HEAD", tmp_path)
    assert routes is None


def test_load_routes_at_ref_handles_empty_routes_array(tmp_path: Path) -> None:
    payload = json.dumps({"routes": []})
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = payload
        routes = load_routes_at_ref("HEAD", tmp_path)
    assert routes == []


def test_load_routes_at_ref_working_tree_reads_from_disk(tmp_path: Path) -> None:
    # Create a fake repo structure with baseline.json on disk.
    baseline_path = tmp_path / "backend" / "evidence" / "capabilities" / "baseline.json"
    baseline_path.parent.mkdir(parents=True)
    baseline_path.write_text(
        json.dumps(
            {"routes": [{"method": "GET", "path": "/api/y", "handler": "mod.fn", "capabilities": ["YReadCapability"]}]}
        )
    )
    # No subprocess call should happen for WORKING.
    with patch("subprocess.run") as mock_run:
        routes = load_routes_at_ref(WORKING_TREE_REF, tmp_path)
    mock_run.assert_not_called()
    assert routes is not None
    assert len(routes) == 1
    assert routes[0].path == "/api/y"


def test_load_routes_at_ref_working_tree_returns_none_when_missing(tmp_path: Path) -> None:
    routes = load_routes_at_ref(WORKING_TREE_REF, tmp_path)
    assert routes is None


def test_resolve_commit_working_tree_returns_sentinel_string(tmp_path: Path) -> None:
    result = resolve_commit(WORKING_TREE_REF, tmp_path)
    assert result == "working-tree"


# ---------------------------------------------------------------------------
# build_git_diff_doc
# ---------------------------------------------------------------------------


def test_build_git_diff_doc_unchanged_routes() -> None:
    routes = [_entry("GET", "/api/x", "XReadCapability")]
    doc = build_git_diff_doc("main", "HEAD", "abc1234", "def5678", routes, routes)
    assert doc["summary"]["unchanged"] == 1
    assert doc["summary"]["expanded"] == 0
    entry = doc["routes"][0]
    assert entry["status"] == "unchanged"
    assert entry["from_capabilities"] == ["XReadCapability"]
    assert entry["to_capabilities"] == ["XReadCapability"]
    assert entry["added"] == []
    assert entry["removed"] == []


def test_build_git_diff_doc_expanded_route() -> None:
    from_routes = [_entry("GET", "/api/x", "XReadCapability")]
    to_routes = [_entry("GET", "/api/x", "XReadCapability", "YReadCapability")]
    doc = build_git_diff_doc("main", "HEAD", "aaa", "bbb", from_routes, to_routes)
    assert doc["summary"]["expanded"] == 1
    entry = doc["routes"][0]
    assert entry["status"] == "expanded"
    assert "YReadCapability" in entry["added"]
    assert entry["removed"] == []


def test_build_git_diff_doc_new_route() -> None:
    from_routes: List[RouteEntry] = []
    to_routes = [_entry("POST", "/api/new", "WriteCapability")]
    doc = build_git_diff_doc("main", "HEAD", "aaa", "bbb", from_routes, to_routes)
    assert doc["summary"]["new"] == 1
    entry = doc["routes"][0]
    assert entry["status"] == "new"
    assert entry["from_capabilities"] is None
    assert entry["to_capabilities"] == ["WriteCapability"]
    assert entry["added"] == ["WriteCapability"]


def test_build_git_diff_doc_removed_route() -> None:
    from_routes = [_entry("DELETE", "/api/old", "WriteCapability")]
    to_routes: List[RouteEntry] = []
    doc = build_git_diff_doc("main", "HEAD", "aaa", "bbb", from_routes, to_routes)
    assert doc["summary"]["removed"] == 1
    entry = doc["routes"][0]
    assert entry["status"] == "removed"
    assert entry["from_capabilities"] == ["WriteCapability"]
    assert entry["to_capabilities"] is None
    assert entry["removed"] == ["WriteCapability"]


def test_build_git_diff_doc_reduced_route() -> None:
    from_routes = [_entry("GET", "/api/x", "XReadCapability", "YReadCapability")]
    to_routes = [_entry("GET", "/api/x", "XReadCapability")]
    doc = build_git_diff_doc("main", "HEAD", "aaa", "bbb", from_routes, to_routes)
    assert doc["summary"]["reduced"] == 1
    entry = doc["routes"][0]
    assert entry["status"] == "reduced"
    assert entry["removed"] == ["YReadCapability"]
    assert entry["added"] == []


def test_build_git_diff_doc_metadata_fields() -> None:
    doc = build_git_diff_doc("v1.0", "feature", "aaa1234", "bbb5678", [], [])
    assert doc["from_ref"] == "v1.0"
    assert doc["to_ref"] == "feature"
    assert doc["from_commit"] == "aaa1234"
    assert doc["to_commit"] == "bbb5678"
    assert "generated_at" in doc
    assert "T" in doc["generated_at"]  # ISO format


def test_build_git_diff_doc_routes_sorted_by_path_then_method() -> None:
    from_routes = [
        _entry("POST", "/api/b", "W"),
        _entry("GET", "/api/a", "R"),
    ]
    to_routes = from_routes[:]
    doc = build_git_diff_doc("main", "HEAD", "a", "b", from_routes, to_routes)
    paths = [r["path"] for r in doc["routes"]]
    assert paths == ["/api/a", "/api/b"]


# ---------------------------------------------------------------------------
# write_git_diff
# ---------------------------------------------------------------------------


def test_write_git_diff_creates_file_and_is_valid_json(tmp_path: Path) -> None:
    from_routes = [_entry("GET", "/api/x", "XReadCapability")]
    doc = build_git_diff_doc("main", "HEAD", "abc", "def", from_routes, from_routes)
    out = tmp_path / "git-diff.json"
    write_git_diff(out, doc)
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["from_ref"] == "main"
    assert data["to_ref"] == "HEAD"
    assert isinstance(data["routes"], list)


def test_write_git_diff_creates_parent_directories(tmp_path: Path) -> None:
    doc = build_git_diff_doc("a", "b", "x", "y", [], [])
    nested = tmp_path / "deep" / "nested" / "git-diff.json"
    write_git_diff(nested, doc)
    assert nested.exists()


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


def test_run_cli_writes_artifact_and_returns_zero(tmp_path: Path) -> None:
    from unittest.mock import MagicMock

    from project_management_crud_example.tools.diff_capabilities import run_cli

    baseline_content = json.dumps(
        {
            "routes": [
                {"method": "GET", "path": "/api/x", "handler": "mod.fn", "capabilities": ["XReadCapability"]},
            ]
        }
    )

    def _fake(cmd: list[str], **_kw: object) -> MagicMock:
        r = MagicMock()
        r.returncode = 0
        r.stdout = "abc123def456\n" if "rev-parse" in cmd else baseline_content
        return r

    out = tmp_path / "git-diff.json"
    with patch("subprocess.run", side_effect=_fake):
        rc = run_cli(["--from", "main", "--to", "HEAD", "--out", str(out)])

    assert rc == 0
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["from_ref"] == "main"
    assert data["to_ref"] == "HEAD"


def test_run_cli_returns_1_on_invalid_from_ref(tmp_path: Path) -> None:
    from unittest.mock import MagicMock

    from project_management_crud_example.tools.diff_capabilities import run_cli

    def _fake(*_args: object, **_kw: object) -> MagicMock:
        r = MagicMock()
        r.returncode = 1
        r.stdout = ""
        return r

    out = tmp_path / "git-diff.json"
    with patch("subprocess.run", side_effect=_fake):
        rc = run_cli(["--from", "no-such-ref", "--to", "HEAD", "--out", str(out)])

    assert rc == 1
    assert not out.exists()

"""Tests for the capability surface analyzer.

Covers extraction (introspecting a synthetic FastAPI app), diff classification,
HTML rendering, and CLI exit behavior.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

import pytest
from fastapi import Depends, FastAPI

from project_management_crud_example.tools.analyze_capabilities import (
    DiffResult,
    RouteEntry,
    collect_route_entries,
    diff_entries,
    extract_capabilities_from_route,
    is_excluded_path,
    render_index_html,
    run_cli,
)

# ---------------------------------------------------------------------------
# Synthetic capability classes + dependency providers
# ---------------------------------------------------------------------------


class AlphaCapability:
    pass


class BetaCapability:
    pass


class GammaCapability:
    pass


class NotACapabilityThing:
    pass


def _provide_alpha() -> AlphaCapability:
    return AlphaCapability()


def _provide_beta() -> BetaCapability:
    return BetaCapability()


def _provide_gamma() -> GammaCapability:
    return GammaCapability()


def _provide_non_cap() -> NotACapabilityThing:
    return NotACapabilityThing()


_DEP_ALPHA = Depends(_provide_alpha)
_DEP_BETA = Depends(_provide_beta)
_DEP_NON_CAP = Depends(_provide_non_cap)


def _build_app_with_routes() -> FastAPI:
    app = FastAPI()

    @app.get("/api/one")
    def one(cap: AlphaCapability = _DEP_ALPHA) -> dict:
        return {}

    @app.get("/api/multi")
    def multi(
        a: AlphaCapability = _DEP_ALPHA,
        b: BetaCapability = _DEP_BETA,
    ) -> dict:
        return {}

    @app.get("/api/noisy")
    def noisy(
        a: AlphaCapability = _DEP_ALPHA,
        _n: NotACapabilityThing = _DEP_NON_CAP,
    ) -> dict:
        return {}

    # Excluded paths
    @app.post("/auth/login")
    def login() -> dict:
        return {}

    @app.get("/health")
    def health() -> dict:
        return {}

    @app.post("/e2e/reset")
    def reset() -> dict:
        return {}

    return app


def _route_by_path(app: FastAPI, path: str) -> object:
    from fastapi.routing import APIRoute

    for r in app.routes:
        if isinstance(r, APIRoute) and r.path == path:
            return r
    raise AssertionError(f"route {path} not found")


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def test_extract_capabilities_from_route_finds_single_capability() -> None:
    app = _build_app_with_routes()
    route = _route_by_path(app, "/api/one")
    assert extract_capabilities_from_route(route) == ("AlphaCapability",)


def test_extract_capabilities_from_route_finds_multiple() -> None:
    app = _build_app_with_routes()
    route = _route_by_path(app, "/api/multi")
    assert extract_capabilities_from_route(route) == ("AlphaCapability", "BetaCapability")


def test_extract_capabilities_from_route_ignores_non_capability_deps() -> None:
    app = _build_app_with_routes()
    route = _route_by_path(app, "/api/noisy")
    assert extract_capabilities_from_route(route) == ("AlphaCapability",)


def test_extract_capabilities_skips_exception_routes() -> None:
    app = _build_app_with_routes()
    entries = collect_route_entries(app)
    paths = {e.path for e in entries}
    assert "/auth/login" not in paths
    assert "/health" not in paths
    assert "/e2e/reset" not in paths
    assert "/api/one" in paths


def test_is_excluded_path_covers_documented_prefixes() -> None:
    assert is_excluded_path("/auth/login")
    assert is_excluded_path("/health")
    assert is_excluded_path("/e2e/reset")
    assert is_excluded_path("/stub_entities")
    assert not is_excluded_path("/api/projects")


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------


def _entry(path: str, caps: List[str], method: str = "GET", handler: str = "h") -> RouteEntry:
    return RouteEntry(method=method, path=path, handler=handler, capabilities=tuple(caps))


def test_diff_classifies_unchanged_route() -> None:
    a = [_entry("/x", ["AlphaCapability"])]
    b = [_entry("/x", ["AlphaCapability"])]
    diff = diff_entries(a, b)
    assert len(diff.unchanged) == 1
    assert not diff.expanded and not diff.reduced and not diff.new and not diff.removed


def test_diff_classifies_expanded_route() -> None:
    a = [_entry("/x", ["AlphaCapability"])]
    b = [_entry("/x", ["AlphaCapability", "BetaCapability"])]
    diff = diff_entries(a, b)
    assert len(diff.expanded) == 1
    assert diff.has_expansion()


def test_diff_classifies_reduced_route() -> None:
    a = [_entry("/x", ["AlphaCapability", "BetaCapability"])]
    b = [_entry("/x", ["AlphaCapability"])]
    diff = diff_entries(a, b)
    assert len(diff.reduced) == 1
    assert not diff.has_expansion()


def test_diff_classifies_new_route() -> None:
    a: List[RouteEntry] = []
    b = [_entry("/x", ["AlphaCapability"])]
    diff = diff_entries(a, b)
    assert len(diff.new) == 1
    assert diff.has_expansion()


def test_diff_classifies_removed_route() -> None:
    a = [_entry("/x", ["AlphaCapability"])]
    b: List[RouteEntry] = []
    diff = diff_entries(a, b)
    assert len(diff.removed) == 1
    assert not diff.has_expansion()


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------


def test_render_index_html_contains_all_routes() -> None:
    diff = DiffResult(
        unchanged=[_entry("/u", ["AlphaCapability"])],
        expanded=[(_entry("/e", ["AlphaCapability"]), _entry("/e", ["AlphaCapability", "BetaCapability"]))],
        reduced=[(_entry("/r", ["AlphaCapability", "BetaCapability"]), _entry("/r", ["AlphaCapability"]))],
        new=[_entry("/n", ["GammaCapability"])],
        removed=[_entry("/x", ["AlphaCapability"])],
    )
    html = render_index_html(diff)
    for path in ("/u", "/e", "/r", "/n", "/x"):
        assert path in html


def test_render_index_html_tints_expanded_rows_red() -> None:
    diff = DiffResult(
        expanded=[(_entry("/e", ["AlphaCapability"]), _entry("/e", ["AlphaCapability", "BetaCapability"]))]
    )
    html = render_index_html(diff)
    assert 'class="expanded"' in html
    assert "#fde8e8" in html  # expanded row background color from the template


def test_render_index_html_banner_counts_match_summary() -> None:
    diff = DiffResult(
        unchanged=[_entry("/a", ["AlphaCapability"]), _entry("/b", ["BetaCapability"])],
        expanded=[(_entry("/e", ["AlphaCapability"]), _entry("/e", ["AlphaCapability", "BetaCapability"]))],
        new=[_entry("/n", ["GammaCapability"])],
    )
    html = render_index_html(diff)
    assert "<strong>Total:</strong> 4" in html
    assert "<strong>Unchanged:</strong> 2" in html
    assert "<strong>Expanded:</strong> 1" in html
    assert "<strong>New:</strong> 1" in html


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _write_baseline(out_dir: Path, entries: List[RouteEntry]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "baseline.json").write_text(
        json.dumps({"routes": [e.to_dict() for e in entries]}, indent=2, sort_keys=True)
    )


def test_cli_exit_zero_when_no_expansion(tmp_path: Path) -> None:
    app = _build_app_with_routes()
    # Baseline that matches current snapshot exactly
    entries = collect_route_entries(app)
    _write_baseline(tmp_path, entries)
    assert run_cli([], app=app, out_dir=tmp_path) == 0


def test_cli_exit_one_when_any_route_expanded(tmp_path: Path) -> None:
    app = _build_app_with_routes()
    current = collect_route_entries(app)
    # Forge a baseline where /api/multi had fewer capabilities (current adds one)
    baseline: List[RouteEntry] = []
    for e in current:
        if e.path == "/api/multi":
            baseline.append(RouteEntry(e.method, e.path, e.handler, ("AlphaCapability",)))
        else:
            baseline.append(e)
    _write_baseline(tmp_path, baseline)
    assert run_cli([], app=app, out_dir=tmp_path) == 1


def test_cli_exit_one_when_new_route_without_update_flag(tmp_path: Path) -> None:
    app = _build_app_with_routes()
    # Baseline that is missing /api/one -> it becomes a new route
    current = collect_route_entries(app)
    baseline = [e for e in current if e.path != "/api/one"]
    _write_baseline(tmp_path, baseline)
    assert run_cli([], app=app, out_dir=tmp_path) == 1


def test_cli_update_baseline_overwrites_file(tmp_path: Path) -> None:
    app = _build_app_with_routes()
    # Write a bogus baseline that will be overwritten
    (tmp_path / "baseline.json").write_text(json.dumps({"routes": []}))
    assert run_cli(["--update-baseline"], app=app, out_dir=tmp_path) == 0
    data = json.loads((tmp_path / "baseline.json").read_text())
    paths = {r["path"] for r in data["routes"]}
    assert "/api/one" in paths
    assert "/api/multi" in paths
    # Follow-up check against new baseline: no expansion
    assert run_cli([], app=app, out_dir=tmp_path) == 0


def test_cli_update_baseline_returns_zero_even_on_unexpected_state(tmp_path: Path) -> None:
    app = _build_app_with_routes()
    # No baseline file at all
    assert run_cli(["--update-baseline"], app=app, out_dir=tmp_path) == 0
    assert (tmp_path / "baseline.json").exists()


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])

"""Capability surface analyzer.

Enumerates every FastAPI route, extracts which Capability dependency classes
it depends on (directly or transitively), and emits:

- evidence/capabilities/report.json   — structured snapshot + diff summary
- evidence/capabilities/index.html    — self-contained HTML viewer
- evidence/capabilities/baseline.json — committed snapshot to diff against

Usage (from backend/):
    python -m project_management_crud_example.tools.analyze_capabilities
    python -m project_management_crud_example.tools.analyze_capabilities --update-baseline

Exit codes:
    0  — no route expanded, no new route (and --update-baseline always returns 0)
    1  — a route's capability set expanded OR a route was added without --update-baseline
"""

from __future__ import annotations

import argparse
import inspect
import json
import sys
import typing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

# Exception list: routes that intentionally do NOT use a capability. The
# analyzer skips these (they do not appear in report.json at all).
EXCLUDED_PATHS: Tuple[str, ...] = (
    "/auth/login",
    "/health",
)
EXCLUDED_PATH_PREFIXES: Tuple[str, ...] = (
    "/e2e/",
    "/stub_entities",  # stub entity template endpoints (legacy path, intentionally excluded)
)


@dataclass(frozen=True)
class RouteEntry:
    """A single route's analyzer record."""

    method: str
    path: str
    handler: str
    capabilities: Tuple[str, ...]

    def key(self) -> str:
        return f"{self.method} {self.path}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "path": self.path,
            "handler": self.handler,
            "capabilities": list(self.capabilities),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RouteEntry":
        return cls(
            method=data["method"],
            path=data["path"],
            handler=data.get("handler", ""),
            capabilities=tuple(data.get("capabilities", [])),
        )


@dataclass
class DiffResult:
    """Per-route diff classification vs baseline."""

    unchanged: List[RouteEntry] = field(default_factory=list)
    expanded: List[Tuple[RouteEntry, RouteEntry]] = field(default_factory=list)  # (old, new)
    reduced: List[Tuple[RouteEntry, RouteEntry]] = field(default_factory=list)
    new: List[RouteEntry] = field(default_factory=list)
    removed: List[RouteEntry] = field(default_factory=list)

    def summary(self) -> Dict[str, int]:
        return {
            "total": len(self.unchanged) + len(self.expanded) + len(self.reduced) + len(self.new) + len(self.removed),
            "unchanged": len(self.unchanged),
            "expanded": len(self.expanded),
            "reduced": len(self.reduced),
            "new": len(self.new),
            "removed": len(self.removed),
        }

    def has_expansion(self) -> bool:
        return bool(self.expanded) or bool(self.new)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def _return_type_name(call: object) -> Optional[str]:
    """Return the unqualified class name of a callable's return annotation, or None."""
    if call is None or not callable(call):
        return None
    try:
        hints = typing.get_type_hints(call)
    except Exception:
        try:
            sig = inspect.signature(call)  # type: ignore[arg-type]
            ann = sig.return_annotation
            if ann is inspect.Signature.empty:
                return None
            return getattr(ann, "__name__", None)
        except (TypeError, ValueError):
            return None
    ret = hints.get("return")
    if ret is None:
        return None
    return getattr(ret, "__name__", None)


def _walk_dependant(dependant: object, seen: Set[int]) -> Iterable[Any]:
    """Yield every `call` in the dependant tree (depth-first)."""
    if id(dependant) in seen:
        return
    seen.add(id(dependant))
    call = getattr(dependant, "call", None)
    if call is not None:
        yield call
    for sub in getattr(dependant, "dependencies", []) or []:
        yield from _walk_dependant(sub, seen)


def extract_capabilities_from_route(route: object) -> Tuple[str, ...]:
    """Return a sorted tuple of Capability class names this route depends on.

    A dependency counts if the callable's return type annotation class name
    ends with `Capability`. Handler itself is skipped.
    """
    dependant = getattr(route, "dependant", None)
    if dependant is None:
        return ()
    handler = getattr(route, "endpoint", None)
    found: Set[str] = set()
    for call in _walk_dependant(dependant, set()):
        if call is handler:
            continue
        name = _return_type_name(call)
        if name and name.endswith("Capability"):
            found.add(name)
    return tuple(sorted(found))


def is_excluded_path(path: str) -> bool:
    """Return True if the path is on the analyzer exception list."""
    if path in EXCLUDED_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in EXCLUDED_PATH_PREFIXES)


def collect_route_entries(app: object) -> List[RouteEntry]:
    """Walk the FastAPI app and produce one entry per (method, path), sorted."""
    # Local import so the analyzer module stays importable even if FastAPI is
    # not available in some tooling contexts.
    from fastapi.routing import APIRoute

    entries: List[RouteEntry] = []
    routes = getattr(app, "routes", [])
    for route in routes:
        if not isinstance(route, APIRoute):
            continue
        if is_excluded_path(route.path):
            continue
        handler = route.endpoint
        handler_name = f"{handler.__module__.rsplit('.', 1)[-1]}.{handler.__name__}"
        caps = extract_capabilities_from_route(route)
        for method in sorted(route.methods or []):
            if method == "HEAD":
                continue
            entries.append(
                RouteEntry(
                    method=method,
                    path=route.path,
                    handler=handler_name,
                    capabilities=caps,
                )
            )
    entries.sort(key=lambda e: (e.path, e.method))
    return entries


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------


def diff_entries(
    baseline: List[RouteEntry],
    current: List[RouteEntry],
) -> DiffResult:
    """Classify each route vs the baseline."""
    by_key_baseline = {e.key(): e for e in baseline}
    by_key_current = {e.key(): e for e in current}
    result = DiffResult()

    for key, new_entry in by_key_current.items():
        old_entry = by_key_baseline.get(key)
        if old_entry is None:
            result.new.append(new_entry)
            continue
        old_set = set(old_entry.capabilities)
        new_set = set(new_entry.capabilities)
        if old_set == new_set:
            result.unchanged.append(new_entry)
        elif new_set > old_set:
            result.expanded.append((old_entry, new_entry))
        elif new_set < old_set:
            result.reduced.append((old_entry, new_entry))
        else:
            # disjoint change — treat as expansion (strictly safer)
            result.expanded.append((old_entry, new_entry))

    for key, old_entry in by_key_baseline.items():
        if key not in by_key_current:
            result.removed.append(old_entry)

    return result


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Capability Surface</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          margin: 24px; color: #222; }}
  h1 {{ font-size: 20px; margin-bottom: 4px; }}
  .banner {{ padding: 10px 14px; border-radius: 6px; background: #f4f4f4;
             margin-bottom: 16px; display: flex; gap: 18px; flex-wrap: wrap;
             font-size: 14px; }}
  .banner span {{ white-space: nowrap; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
  th, td {{ text-align: left; padding: 6px 10px; border-bottom: 1px solid #eee;
            vertical-align: top; }}
  th {{ background: #fafafa; position: sticky; top: 0; }}
  tr.unchanged {{ background: #ffffff; }}
  tr.expanded {{ background: #fde8e8; }}
  tr.new {{ background: #fff3cd; }}
  tr.reduced {{ background: #e8f5e9; }}
  tr.removed {{ background: #eeeeee; color: #888; }}
  code {{ font-family: "SF Mono", Menlo, monospace; font-size: 12px; }}
  .caps {{ font-family: "SF Mono", Menlo, monospace; font-size: 12px; }}
  .diff {{ font-size: 12px; color: #555; }}
</style>
</head>
<body>
<h1>Capability Surface</h1>
<div class="banner">
  <span><strong>Total:</strong> {total}</span>
  <span><strong>Unchanged:</strong> {unchanged}</span>
  <span style="color:#c0392b"><strong>Expanded:</strong> {expanded}</span>
  <span style="color:#b7950b"><strong>New:</strong> {new}</span>
  <span style="color:#2e7d32"><strong>Reduced:</strong> {reduced}</span>
  <span style="color:#666"><strong>Removed:</strong> {removed}</span>
</div>
<table>
<thead>
<tr><th>Method</th><th>Path</th><th>Handler</th><th>Capabilities</th><th>Diff</th></tr>
</thead>
<tbody>
{rows}
</tbody>
</table>
</body>
</html>
"""


def _row(cls: str, method: str, path: str, handler: str, caps: Iterable[str], diff: str) -> str:
    caps_str = ", ".join(caps) if caps else "<em>(none)</em>"
    return (
        f'<tr class="{cls}">'
        f"<td><code>{method}</code></td>"
        f"<td><code>{path}</code></td>"
        f"<td><code>{handler}</code></td>"
        f'<td class="caps">{caps_str}</td>'
        f'<td class="diff">{diff}</td>'
        "</tr>"
    )


def render_index_html(diff: DiffResult) -> str:
    """Render a self-contained HTML page showing every route's capability set."""
    rows: List[str] = []
    all_rows: List[Tuple[str, RouteEntry, str]] = []
    for e in diff.expanded:
        old, new = e
        added = sorted(set(new.capabilities) - set(old.capabilities))
        diff_text = f"+ {', '.join(added)}" if added else "(rearranged)"
        all_rows.append(("expanded", new, diff_text))
    for e in diff.new:
        all_rows.append(("new", e, "new route"))
    for old, new in diff.reduced:
        removed = sorted(set(old.capabilities) - set(new.capabilities))
        all_rows.append(("reduced", new, f"- {', '.join(removed)}"))
    for e in diff.unchanged:
        all_rows.append(("unchanged", e, ""))
    for e in diff.removed:
        all_rows.append(("removed", e, "removed from current"))

    all_rows.sort(key=lambda t: (t[1].path, t[1].method))
    for cls, entry, diff_text in all_rows:
        rows.append(_row(cls, entry.method, entry.path, entry.handler, entry.capabilities, diff_text))

    summary = diff.summary()
    return _HTML_TEMPLATE.format(
        rows="\n".join(rows),
        total=summary["total"],
        unchanged=summary["unchanged"],
        expanded=summary["expanded"],
        new=summary["new"],
        reduced=summary["reduced"],
        removed=summary["removed"],
    )


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------


def _repo_root() -> Path:
    # backend/project_management_crud_example/tools/analyze_capabilities.py
    # -> backend/
    return Path(__file__).resolve().parents[2]


def evidence_dir() -> Path:
    return _repo_root() / "evidence" / "capabilities"


def load_baseline(path: Path) -> List[RouteEntry]:
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    return [RouteEntry.from_dict(r) for r in data.get("routes", [])]


def write_report(path: Path, entries: List[RouteEntry], diff: DiffResult) -> None:
    report = {
        "routes": [e.to_dict() for e in entries],
        "summary": diff.summary(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


def write_baseline(path: Path, entries: List[RouteEntry]) -> None:
    data = {"routes": [e.to_dict() for e in entries]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def write_html(path: Path, diff: DiffResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_index_html(diff))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_app() -> object:
    from project_management_crud_example.app import app

    return app


def run_cli(argv: Optional[List[str]] = None, *, app: object = None, out_dir: Optional[Path] = None) -> int:
    parser = argparse.ArgumentParser(prog="analyze_capabilities")
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Overwrite evidence/capabilities/baseline.json with the current snapshot.",
    )
    args = parser.parse_args(argv)

    if app is None:
        app = _build_app()
    base_dir = out_dir if out_dir is not None else evidence_dir()
    baseline_path = base_dir / "baseline.json"
    report_path = base_dir / "report.json"
    html_path = base_dir / "index.html"

    entries = collect_route_entries(app)

    if args.update_baseline:
        write_baseline(baseline_path, entries)
        # Also write report/html so CI artifacts stay fresh.
        diff = diff_entries(entries, entries)
        write_report(report_path, entries, diff)
        write_html(html_path, diff)
        print(f"Baseline updated: {baseline_path} ({len(entries)} routes)")
        return 0

    baseline = load_baseline(baseline_path)
    diff = diff_entries(baseline, entries)
    write_report(report_path, entries, diff)
    write_html(html_path, diff)

    summary = diff.summary()
    print(
        f"Capability surface: total={summary['total']} "
        f"unchanged={summary['unchanged']} expanded={summary['expanded']} "
        f"new={summary['new']} reduced={summary['reduced']} removed={summary['removed']}"
    )

    if diff.has_expansion():
        for old, new in diff.expanded:
            added = sorted(set(new.capabilities) - set(old.capabilities))
            print(f"  EXPANDED {new.method} {new.path}: + {added}", file=sys.stderr)
        for entry in diff.new:
            print(f"  NEW {entry.method} {entry.path}: {list(entry.capabilities)}", file=sys.stderr)
        return 1
    return 0


def main() -> int:  # pragma: no cover - thin wrapper
    return run_cli()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

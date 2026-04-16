"""Git-based capability diff tool.

Compares backend/evidence/capabilities/baseline.json at two git revisions and
writes a structured diff to backend/evidence/capabilities/git-diff.json.

The artifact is consumed by the dev dashboard Capabilities panel (Git Diff
section). It records which routes gained/lost capabilities between any two
git refs — useful for PR review, release notes, or auditing permission drift.

Usage (from repo root):
    uv --project backend run python -m project_management_crud_example.tools.diff_capabilities
    uv --project backend run python -m project_management_crud_example.tools.diff_capabilities --from v1.0.0 --to HEAD
    uv --project backend run python -m project_management_crud_example.tools.diff_capabilities --from main --to feature-branch

Args:
    --from  Git ref for the "before" state (default: main)
    --to    Git ref for the "after" state (default: HEAD)
    --out   Override output path (default: backend/evidence/capabilities/git-diff.json)

Exit codes:
    0  — success (artifact written)
    1  — git error, unresolvable ref, or missing baseline at the given ref
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from project_management_crud_example.tools.analyze_capabilities import (
    RouteEntry,
    diff_entries,
    evidence_dir,
)

# Repo-relative path of the baseline — used for `git show`.
BASELINE_REPO_PATH = "backend/evidence/capabilities/baseline.json"

# Sentinel ref meaning "read baseline.json from the working tree (on-disk)".
# Useful for seeing uncommitted edits to baseline.json.
WORKING_TREE_REF = "WORKING"


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _repo_root() -> Path:
    # backend/project_management_crud_example/tools/diff_capabilities.py
    # parents[0] = tools/, parents[1] = project_management_crud_example/,
    # parents[2] = backend/, parents[3] = repo root
    return Path(__file__).resolve().parents[3]


def resolve_commit(ref: str, repo_root: Path) -> Optional[str]:
    """Return a display identifier for *ref*.

    For WORKING_TREE_REF returns the literal string "working-tree".
    For git refs returns the full SHA, or None if the ref is invalid.
    """
    if ref == WORKING_TREE_REF:
        return "working-tree"
    result = subprocess.run(
        ["git", "rev-parse", "--verify", ref],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def git_show_baseline(ref: str, repo_root: Path) -> Optional[str]:
    """Read BASELINE_REPO_PATH at *ref* via `git show`. Returns None on error."""
    result = subprocess.run(
        ["git", "show", f"{ref}:{BASELINE_REPO_PATH}"],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def load_routes_at_ref(ref: str, repo_root: Path) -> Optional[List[RouteEntry]]:
    """Parse baseline.json at *ref*.

    If ref is WORKING_TREE_REF, reads from the on-disk file (picks up
    uncommitted edits). Otherwise uses `git show`. Returns None on error.
    """
    if ref == WORKING_TREE_REF:
        disk_path = repo_root / BASELINE_REPO_PATH
        if not disk_path.exists():
            return None
        content = disk_path.read_text()
    else:
        content = git_show_baseline(ref, repo_root)
        if content is None:
            return None
    try:
        data = json.loads(content)
        return [RouteEntry.from_dict(r) for r in data.get("routes", [])]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"Error parsing baseline at {ref!r}: {exc}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Artifact construction
# ---------------------------------------------------------------------------


def _route_diff_entry(
    status: str,
    method: str,
    path: str,
    handler: str,
    from_caps: Optional[List[str]],
    to_caps: Optional[List[str]],
    added: List[str],
    removed: List[str],
) -> Dict:
    return {
        "method": method,
        "path": path,
        "handler": handler,
        "from_capabilities": from_caps,
        "to_capabilities": to_caps,
        "status": status,
        "added": added,
        "removed": removed,
    }


def build_git_diff_doc(
    from_ref: str,
    to_ref: str,
    from_commit: str,
    to_commit: str,
    from_routes: List[RouteEntry],
    to_routes: List[RouteEntry],
) -> Dict:
    """Compute diff and return the git-diff.json document (as a dict)."""
    result = diff_entries(from_routes, to_routes)

    route_entries: List[Dict] = []

    for old, new in result.expanded:
        added = sorted(set(new.capabilities) - set(old.capabilities))
        removed = sorted(set(old.capabilities) - set(new.capabilities))
        route_entries.append(
            _route_diff_entry(
                "expanded",
                new.method,
                new.path,
                new.handler,
                list(old.capabilities),
                list(new.capabilities),
                added,
                removed,
            )
        )

    for entry in result.new:
        route_entries.append(
            _route_diff_entry(
                "new",
                entry.method,
                entry.path,
                entry.handler,
                None,
                list(entry.capabilities),
                list(entry.capabilities),
                [],
            )
        )

    for old, new in result.reduced:
        added = sorted(set(new.capabilities) - set(old.capabilities))
        removed = sorted(set(old.capabilities) - set(new.capabilities))
        route_entries.append(
            _route_diff_entry(
                "reduced",
                new.method,
                new.path,
                new.handler,
                list(old.capabilities),
                list(new.capabilities),
                added,
                removed,
            )
        )

    for entry in result.unchanged:
        route_entries.append(
            _route_diff_entry(
                "unchanged",
                entry.method,
                entry.path,
                entry.handler,
                list(entry.capabilities),
                list(entry.capabilities),
                [],
                [],
            )
        )

    for entry in result.removed:
        route_entries.append(
            _route_diff_entry(
                "removed",
                entry.method,
                entry.path,
                entry.handler,
                list(entry.capabilities),
                None,
                [],
                list(entry.capabilities),
            )
        )

    route_entries.sort(key=lambda r: (r["path"], r["method"]))

    return {
        "from_ref": from_ref,
        "to_ref": to_ref,
        "from_commit": from_commit,
        "to_commit": to_commit,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "routes": route_entries,
        "summary": result.summary(),
    }


def write_git_diff(path: Path, doc: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def run_cli(
    argv: Optional[List[str]] = None,
    *,
    repo_root: Optional[Path] = None,
    out_path: Optional[Path] = None,
) -> int:
    parser = argparse.ArgumentParser(
        prog="diff_capabilities",
        description="Compare capability surfaces at two git revisions.",
    )
    parser.add_argument(
        "--from",
        dest="from_ref",
        default="main",
        metavar="REF",
        help=f"Git ref for the before state (default: main). Use '{WORKING_TREE_REF}' for on-disk file.",
    )
    parser.add_argument(
        "--to",
        dest="to_ref",
        default="HEAD",
        metavar="REF",
        help=f"Git ref for the after state (default: HEAD). Use '{WORKING_TREE_REF}' for on-disk file.",
    )
    parser.add_argument(
        "--out",
        dest="out_path_arg",
        default=None,
        metavar="PATH",
        help="Override output path (default: backend/evidence/capabilities/git-diff.json)",
    )
    args = parser.parse_args(argv)

    root = repo_root if repo_root is not None else _repo_root()

    from_commit = resolve_commit(args.from_ref, root)
    if from_commit is None:
        print(f"Error: cannot resolve git ref '{args.from_ref}'", file=sys.stderr)
        return 1

    to_commit = resolve_commit(args.to_ref, root)
    if to_commit is None:
        print(f"Error: cannot resolve git ref '{args.to_ref}'", file=sys.stderr)
        return 1

    from_routes = load_routes_at_ref(args.from_ref, root)
    if from_routes is None:
        hint = "Ensure the ref exists and baseline.json is committed there." if args.from_ref != WORKING_TREE_REF else "On-disk baseline.json not found."
        print(f"Error: cannot read {BASELINE_REPO_PATH!r} at ref '{args.from_ref}'.\n{hint}", file=sys.stderr)
        return 1

    to_routes = load_routes_at_ref(args.to_ref, root)
    if to_routes is None:
        hint = "Ensure the ref exists and baseline.json is committed there." if args.to_ref != WORKING_TREE_REF else "On-disk baseline.json not found."
        print(f"Error: cannot read {BASELINE_REPO_PATH!r} at ref '{args.to_ref}'.\n{hint}", file=sys.stderr)
        return 1

    doc = build_git_diff_doc(
        args.from_ref,
        args.to_ref,
        from_commit,
        to_commit,
        from_routes,
        to_routes,
    )

    dest = (
        out_path
        if out_path is not None
        else (Path(args.out_path_arg) if args.out_path_arg else evidence_dir() / "git-diff.json")
    )
    write_git_diff(dest, doc)

    summary = doc["summary"]
    short_from = from_commit[:8]
    short_to = to_commit[:8]
    print(
        f"Git diff: {args.from_ref} ({short_from}) → {args.to_ref} ({short_to})\n"
        f"  total={summary['total']} unchanged={summary['unchanged']} "
        f"expanded={summary['expanded']} new={summary['new']} "
        f"reduced={summary['reduced']} removed={summary['removed']}\n"
        f"Artifact: {dest}"
    )
    return 0


def main() -> int:  # pragma: no cover - thin wrapper
    return run_cli()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

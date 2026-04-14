# Capability surface — analyzer, baseline, and viewer

This directory is the evidence surface for the backend's capability-based DI.
Every route handler depends on a narrow `Capability` object rather than the full
`Repository`; the analyzer tool takes a census of which capabilities each
endpoint receives and diffs it against the committed baseline.

## Files

| File | Tracked? | What it is |
|---|---|---|
| `baseline.json` | ✅ committed | The approved capability surface. Diffs are checked against this. Source of truth. |
| `report.json` | ❌ gitignored | Regenerated on every analyzer run. Machine-readable current state. |
| `index.html` | ❌ gitignored | Optional self-contained static viewer. Only written when `--emit-html` is passed; the dev dashboard (`tools/dev-dashboard/`) is the primary viewer and reads `report.json` directly. |

## Running the analyzer

From the `backend/` directory:

```bash
# Check current state vs baseline. Writes report.json.
./devtools/run_with_env.sh uv run python -m project_management_crud_example.tools.analyze_capabilities
#   exit 0  → unchanged or reduced (narrower surface)
#   exit 1  → expanded (wider surface than baseline — review required)

# After an intentional capability change, accept the new state:
./devtools/run_with_env.sh uv run python -m project_management_crud_example.tools.analyze_capabilities --update-baseline
#   Rewrites baseline.json. Commit the diff as part of your PR.

# Opt-in: also write the standalone HTML viewer (index.html). The dev dashboard
# is the preferred viewer; this flag exists for standalone inspection.
./devtools/run_with_env.sh uv run python -m project_management_crud_example.tools.analyze_capabilities --emit-html
```

## Reading the viewer

The primary viewer is the dev dashboard under `tools/dev-dashboard/`, which
reads `report.json` directly. If you need a standalone static file, run the
analyzer with `--emit-html` and open the resulting `index.html`. Columns:

- **Method / Path / Handler** — the endpoint.
- **Capabilities** — the Capability classes that route receives via `Depends(...)`.
- **Diff** — against `baseline.json`.
  - Red row = capabilities were **added** (surface expanded — review).
  - Green row = capabilities were **removed** (surface reduced — good, but still review).
  - Neutral = unchanged.

A top banner summarizes counts (total / unchanged / expanded / reduced / new / removed).

## Workflow for agents & humans

1. Make your code change (new route, reshaped capability, permission tweak).
2. Run the analyzer (no flag). If it exits 0 and you expected zero capability change, you're done — nothing to commit here.
3. If it exits 1 or shows a diff you expected, open the dev dashboard (or re-run with `--emit-html` and open `index.html`) to confirm the diff matches intent.
4. Run with `--update-baseline`. Stage and commit the `baseline.json` change in the same PR as the code change. The PR diff of `baseline.json` is the permission-surface change that reviewers inspect.

## Excluded routes

The analyzer intentionally skips a small allowlist (see `EXCLUDED_PATHS` /
`EXCLUDED_PATH_PREFIXES` in `project_management_crud_example/tools/analyze_capabilities.py`):

- `POST /auth/login` — no authenticated user exists at login time.
- `GET /health` — no authorization.
- `/e2e/**` — test-only reset endpoints, never exposed in production.
- `/stub_entities` — legacy scaffolding.

Adding to this list is a plan-level decision, not a code-level one. See
`docs/architecture/principles.md` §Capability layer.

## When a diff appears in review

A capability-set **expansion** is a review signal, not a validation failure.
The analyzer does not run as part of `run_all_agent_validations.sh` — it is a
review-time tool. When a reviewer sees `baseline.json` change in a PR, they
should:

1. Confirm the PR description explains why the surface grew.
2. Use the dev dashboard (or `git diff baseline.json`, or re-run with `--emit-html`) to see the
   specific route(s) and capabilities added.
3. Verify the new capability methods have allow/deny tests in
   `backend/tests/capabilities/`.

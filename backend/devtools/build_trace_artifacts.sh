#!/usr/bin/env bash
# Build the pytest-tracer index AND a sample set of human-viewable flame-graph
# artifacts for every scenario. Run from anywhere; resolves paths relative to
# the script location.
#
# Outputs (all under backend/, all gitignored):
#   .coverage              per-test SQLite coverage DB        (pytest-cov)
#   scenarios.json         scenario metadata                  (pytest-tracer collect)
#   call_traces.json       per-test sys.monitoring events     (pytest-tracer trace)
#   .trace-index/          queryable index                    (trace build)
#   .trace-artifacts/      one subdir per scenario, each with:
#       summary.json         small frame list (anchored)
#       folded-compact.txt   collapsed call stacks
#       mermaid.md           sequence diagram, ready to view on GitHub
#       flame.png            static flame graph (3600px wide)
#       flame.html           interactive flame graph (open in any browser)
#
# Output contract: concise on pass (one banner per step), dumps the failing
# step's captured stdout+stderr on any error. Mirrors the pattern in
# run_all_agent_validations.sh so agent context isn't flooded with pytest /
# pytest-tracer / trace CLI progress.
#
# Usage:
#   backend/devtools/build_trace_artifacts.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TRACE_BIN="/Users/shai/proj/shaig/learn/agent_tracer/projects/trace_analyzer/target/release/trace"
ART_DIR="${BACKEND_DIR}/.trace-artifacts"

cd "${BACKEND_DIR}"

TEMP_OUTPUT=$(mktemp)
trap 'rm -f "$TEMP_OUTPUT"' EXIT

run_or_dump() {
    # Run "$@", capture stdout+stderr. On success: silent. On failure: dump + exit 1.
    local label="$1"
    shift
    if ! "$@" > "$TEMP_OUTPUT" 2>&1; then
        echo "❌ ${label} failed:"
        cat "$TEMP_OUTPUT"
        exit 1
    fi
}

echo "==> 1/4  pytest with per-test coverage"
run_or_dump "pytest" \
    uv run pytest --cov=project_management_crud_example --cov-context=test

echo "==> 2/4  collect scenario metadata + call traces"
run_or_dump "pytest-tracer collect" uv run pytest-tracer collect . -o scenarios.json
run_or_dump "pytest-tracer trace"   uv run pytest-tracer trace   . -o call_traces.json

echo "==> 3/4  build trace index"
run_or_dump "trace build" \
    "${TRACE_BIN}" build \
        --coverage .coverage \
        --scenarios scenarios.json \
        --call-traces call_traces.json \
        --output .trace-index

echo "==> 4/4  generate per-scenario artifacts under ${ART_DIR}"
rm -rf "${ART_DIR}"
mkdir -p "${ART_DIR}"

# Iterate over every scenario id in the index. Redirect the whole loop to the
# tempfile — one "- <id>" progress line per scenario would flood agent context.
{
    "${TRACE_BIN}" list --index .trace-index \
        | python3 -c 'import json,sys; print("\n".join(s["id"] for s in json.load(sys.stdin)))' \
        | while IFS= read -r ID; do
            # Sanitize: replace / and :: with _
            SAFE="${ID//\//_}"
            SAFE="${SAFE//::/__}"
            OUT="${ART_DIR}/${SAFE}"
            mkdir -p "${OUT}"
            echo "    - ${ID}"
            "${TRACE_BIN}" flamegraph "${ID}" --format summary        --index .trace-index > "${OUT}/summary.json"
            "${TRACE_BIN}" flamegraph "${ID}" --format folded-compact --index .trace-index > "${OUT}/folded-compact.txt"
            {
                echo '# '"${ID}"
                echo
                echo '```mermaid'
                "${TRACE_BIN}" flamegraph "${ID}" --format mermaid --index .trace-index
                echo '```'
            } > "${OUT}/mermaid.md"
            "${TRACE_BIN}" flamegraph "${ID}" --format png  --index .trace-index > "${OUT}/flame.png"
            "${TRACE_BIN}" flamegraph "${ID}" --format html --index .trace-index > "${OUT}/flame.html"
        done
} > "$TEMP_OUTPUT" 2>&1 || {
    echo "❌ per-scenario artifact generation failed:"
    cat "$TEMP_OUTPUT"
    exit 1
}

echo "Done. Open ${ART_DIR} to browse per-scenario artifacts."

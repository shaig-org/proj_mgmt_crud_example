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
# Usage:
#   backend/devtools/build_trace_artifacts.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TRACE_BIN="/Users/shai/proj/shaig/learn/agent_tracer/projects/trace_analyzer/target/release/trace"
ART_DIR="${BACKEND_DIR}/.trace-artifacts"

cd "${BACKEND_DIR}"

echo "==> 1/4  pytest with per-test coverage"
uv run pytest --cov=project_management_crud_example --cov-context=test -q

echo "==> 2/4  collect scenario metadata + call traces"
uv run pytest-tracer collect . -o scenarios.json
uv run pytest-tracer trace   . -o call_traces.json

echo "==> 3/4  build trace index"
"${TRACE_BIN}" build \
    --coverage .coverage \
    --scenarios scenarios.json \
    --call-traces call_traces.json \
    --output .trace-index

echo "==> 4/4  generate per-scenario artifacts under ${ART_DIR}"
rm -rf "${ART_DIR}"
mkdir -p "${ART_DIR}"

# Iterate over every scenario id in the index.
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

echo
echo "Done. Open ${ART_DIR} to browse per-scenario artifacts."

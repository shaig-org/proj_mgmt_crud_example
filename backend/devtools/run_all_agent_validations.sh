#!/usr/bin/env zsh

# Run all validation steps and only print output on failure.
# Concise on success, verbose on failure. Keeps agent context tight.
#
# Steps (4, was 6):
#   1. ruff check --fix        — auto-fix lint errors; exits non-zero if unfixable violations remain
#   2. ruff format             — format code in-place (always idempotent)
#   3. ty check                — type check
#   4. pytest                  — runs under xdist (-n auto) per pytest.ini
#
# Removed redundant steps:
#   - A second `ruff check` after `--fix` only detects the same unfixable violations.
#   - A `ruff format --diff` after `ruff format` always reports zero changes.

set -e  # Exit on first error

TEMP_OUTPUT=$(mktemp)
trap "rm -f $TEMP_OUTPUT" EXIT

SECONDS_START=$SECONDS

# Function to run a command and capture output
run_step() {
    local step_name="$1"
    shift

    if "$@" > "$TEMP_OUTPUT" 2>&1; then
        return 0
    else
        return 1
    fi
}

run_step "ruff-fix" uv run ruff check --fix . || {
    echo "❌ Ruff lint (with auto-fix) failed:"
    cat "$TEMP_OUTPUT"
    exit 1
}

run_step "ruff-format" uv run ruff format . || {
    echo "❌ Ruff formatting failed:"
    cat "$TEMP_OUTPUT"
    exit 1
}

run_step "type-check" uv run ty check || {
    echo "❌ Type checking failed:"
    cat "$TEMP_OUTPUT"
    exit 1
}

run_step "pytest" uv run pytest -n auto --dist loadfile || {
    echo "❌ Tests failed:"
    cat "$TEMP_OUTPUT"
    exit 1
}

# All validations passed
ELAPSED=$(( SECONDS - SECONDS_START ))
echo "✅ All validations passed in ${ELAPSED}s (lint+fix, format, type check, tests)"

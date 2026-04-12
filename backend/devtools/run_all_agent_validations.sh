#!/usr/bin/env zsh

# Run all validation steps and only print output on failure
# On success, prints a single summary line

set -e  # Exit on first error

TEMP_OUTPUT=$(mktemp)
trap "rm -f $TEMP_OUTPUT" EXIT

SUCCESS=true
FAILED_STEP=""

# Function to run a command and capture output
run_step() {
    local step_name="$1"
    shift

    if "$@" > "$TEMP_OUTPUT" 2>&1; then
        return 0
    else
        SUCCESS=false
        FAILED_STEP="$step_name"
        return 1
    fi
}

# Run each validation step
run_step "ruff-fix" uv run ruff check --fix . || {
    echo "❌ Ruff auto-fix failed:"
    cat "$TEMP_OUTPUT"
    exit 1
}

run_step "ruff-format" uv run ruff format . || {
    echo "❌ Ruff formatting failed:"
    cat "$TEMP_OUTPUT"
    exit 1
}

run_step "ruff-check" uv run ruff check . || {
    echo "❌ Ruff linting failed:"
    cat "$TEMP_OUTPUT"
    exit 1
}

run_step "ruff-format-check" uv run ruff format --diff . || {
    echo "❌ Code formatting check failed:"
    cat "$TEMP_OUTPUT"
    exit 1
}

run_step "type-check" uv run ty check || {
    echo "❌ Type checking failed:"
    cat "$TEMP_OUTPUT"
    exit 1
}

run_step "pytest" uv run pytest || {
    echo "❌ Tests failed:"
    cat "$TEMP_OUTPUT"
    exit 1
}

# All validations passed
echo "✅ All validations passed (lint, format, type check, tests)"

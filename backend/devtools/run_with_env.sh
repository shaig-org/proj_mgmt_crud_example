#!/usr/bin/env bash
# Wrapper: sets test env vars and runs the given command. Used so agents can
# invoke python/pytest/uv with required env vars via a pre-approved path.
set -euo pipefail
export JWT_SECRET_KEY="${JWT_SECRET_KEY:-test_secret_key_minimum_32_characters_long_xxxxx}"
export BCRYPT_ROUNDS="${BCRYPT_ROUNDS:-4}"
exec "$@"

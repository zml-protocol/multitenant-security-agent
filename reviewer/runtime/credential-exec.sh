#!/bin/sh
set -eu

secret_file="${REVIEWER_CREDENTIAL_FILE:-/run/secrets/anthropic_api_key}"

[ -r "$secret_file" ] || {
  echo "reviewer credential file is not readable" >&2
  exit 64
}

IFS= read -r ANTHROPIC_API_KEY < "$secret_file"
[ -n "$ANTHROPIC_API_KEY" ] || {
  echo "reviewer credential file is empty" >&2
  exit 64
}

export ANTHROPIC_API_KEY
unset ANTHROPIC_AUTH_TOKEN CLAUDE_CODE_OAUTH_TOKEN
exec "$@"

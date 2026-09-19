#!/bin/sh
set -eu

[ -n "${ANTHROPIC_API_KEY:-}" ] || {
  echo "credential probe did not receive the parent credential" >&2
  exit 1
}

child_present="$(env -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN -u CLAUDE_CODE_OAUTH_TOKEN sh -c '
  for name in ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN CLAUDE_CODE_OAUTH_TOKEN; do
    if printenv "$name" >/dev/null 2>&1; then printf true; exit; fi
  done
  printf false
')"

node -e 'const fs=require("fs"); const p="/etc/claude-code/managed-settings.json"; const s=JSON.parse(fs.readFileSync(p,"utf8")); if(s.availableModels?.[0]!=="claude-sonnet-5" || s.env?.CLAUDE_CODE_SUBPROCESS_ENV_SCRUB!=="1" || s.env?.CLAUDE_CODE_SKIP_PROMPT_HISTORY!=="1") process.exit(1)'

printf '{"credential_present_in_wrapper":true,"sensitive_environment_present_in_probe_child":%s,"managed_settings_valid":true}\n' "$child_present"

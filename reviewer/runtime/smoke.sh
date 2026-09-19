#!/bin/sh
set -eu

fail() {
  echo "runtime smoke failed: $1" >&2
  exit 1
}

version_output="$(claude --version)"
case "$version_output" in
  "$CLAUDE_CODE_EXPECTED_VERSION (Claude Code)") ;;
  *) fail "unexpected Claude Code version" ;;
esac

[ "$(id -u)" = "10001" ] || fail "container is not running as reviewer uid 10001"
[ -r /review/input/smoke-input.txt ] || fail "review input is not readable"
[ -r /etc/claude-code/managed-settings.json ] || fail "managed settings are not readable"

if touch /review/input/.write-probe 2>/dev/null; then
  rm -f /review/input/.write-probe
  fail "review input is writable"
fi

if touch /.root-write-probe 2>/dev/null; then
  rm -f /.root-write-probe
  fail "container root filesystem is writable"
fi

touch /review/output/.write-probe || fail "review output is not writable"
rm -f /review/output/.write-probe
touch "$CLAUDE_CONFIG_DIR/.write-probe" || fail "isolated Claude config directory is not writable"
rm -f "$CLAUDE_CONFIG_DIR/.write-probe"
touch "$TMPDIR/.write-probe" || fail "temporary directory is not writable"
rm -f "$TMPDIR/.write-probe"

for name in ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN CLAUDE_CODE_OAUTH_TOKEN; do
  if printenv "$name" >/dev/null 2>&1; then
    fail "credential environment variable is present: $name"
  fi
done

if awk 'NR > 1 && $2 == "00000000" { found = 1 } END { exit found ? 0 : 1 }' /proc/net/route; then
  fail "container has a default network route"
fi

node -e 'JSON.parse(require("fs").readFileSync("/etc/claude-code/managed-settings.json", "utf8"))'

printf '{"claude_code_version":"%s","container_uid":10001,"input_read_only":true,"output_writable":true,"root_read_only":true,"isolated_config_writable":true,"default_network_route":false,"credential_environment_present":false}\n' "$CLAUDE_CODE_EXPECTED_VERSION"

# Controlled Claude Reviewer Execution

English | [中文](reviewer-execution.md)

Status: `implemented_validated_not_formally_authorized`

The execution controller combines the pinned Claude Code runtime, read-only reviewer bundle, independent egress proxy, secret-file injection, fixed model and budget, and two phase-specific output schemas into a fail-closed path. Only cost-free validation has run; the formal start gate remains closed.

## Fixed command

`reviewer/execution/controller.py` generates fixed arguments for each phase:

- `--print` selects non-interactive execution;
- `--restricted --bare` confines access to controlled working directories and managed settings while skipping user and project customizations;
- `--model claude-sonnet-5` pins the model;
- `--max-budget-usd 1.00` provides Claude Code's native spending stop;
- `--max-turns 12` provides a hard agentic-turn limit;
- `--json-schema` requires phase output to match a fixed schema;
- `--no-session-persistence` prevents session persistence;
- `--permission-prompts none` prevents unattended permission grants; and
- `--tools Read,Glob,Grep` permits only reads from the isolated bundle, with no Bash, editing, Web, MCP, or browser tool.
- `--disallowedTools mcp__*`, `--disable-slash-commands`, and `--no-chrome` explicitly close extension surfaces that `--tools` does not govern.

Claude Code's `--max-turns` is not the same as a count of underlying API requests. `maximum_model_api_calls=12` and aggregate 100k/20k token values remain approval and post-run reconciliation boundaries. The current local hard stops are `$1.00`, 12 turns, 900 seconds, 1 MiB of captured output, and container resource limits.

## Credential and network path

A future real key may exist only in an ephemeral read-only secret file created immediately before the run. The Docker command contains only its path. `reviewer-credential-exec` reads the key inside the container, sets `ANTHROPIC_API_KEY`, and directly executes Claude. The key does not enter Docker environment metadata, command arguments, the bundle, or the image.

The reviewer joins only an ephemeral `--internal` network and uses `HTTPS_PROXY=http://egress-proxy:3128`. The separate proxy is the only internet-connected component and permits only CONNECT to `api.anthropic.com:443`. The supervisor forcibly removes the reviewer container on a timeout or output-limit violation and scans reviewer and proxy output for the key before persisting results.

## Cost-free combined verification

Run:

```text
python -m scripts.reviewer_combined_smoke
```

The latest verification on 2026-09-19 established:

- reviewer image: `sha256:d49654657cc6a7977adb7c50a03f613afa62b7fa71f70a1d78d83de8807b642a`;
- egress image: `sha256:dc4b0704ba84407d472ae93dd04dc01f80bbf2fb4f16d2adf12c93d1518ae235`;
- the synthetic key was absent from `docker inspect`, the probe child, output, proxy logs, and persisted evidence;
- credential-free, network-free `claude doctor` reported no installation issues and confirmed that managed environment policy disabled updates;
- allowlisted TLS CONNECT succeeded, a non-allowlisted target returned 403, and direct reviewer egress failed; and
- no `claude -p` command, model request, or cost occurred.

The first doctor check found that the image lacked `bubblewrap`. The image now installs the Anthropic-documented `bubblewrap` and `socat` requirements; doctor and the combined smoke passed after rebuilding. This shows why the actual CLI startup path must be checked in addition to validating a JSON file.

## Formal candidate

`assessment/appsec/v1/formal-candidate-attestation.json` binds the frozen commit, fixture, scenario, bundle-manifest hash, three profile hashes, approved budget-subject hash, fixed Claude-command hash, and local image IDs. Its status is `validated_waiting_formal_start_approval`; the embedded bundle remains `draft_not_for_claude`.

Formal execution still requires:

- the Security Engineer's immutability commitment for the assessment window;
- final approver and UTC time;
- a dedicated project API key and workspace spend limit;
- one atomic binding of the start gate and runtime, egress, execution, and auth execution switches to the approved attestation; and
- registry digests instead of local image IDs before cloud deployment.

## Official sources

- [Claude Code CLI reference](https://code.claude.com/docs/en/cli-reference)
- [Claude Code programmatic usage](https://code.claude.com/docs/en/headless)
- [Claude Code environment variables](https://code.claude.com/docs/en/env-vars)
- [Claude Code settings precedence](https://code.claude.com/docs/en/settings)

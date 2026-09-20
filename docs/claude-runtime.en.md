# Claude Reviewer Runtime Readiness Audit

English | [中文](claude-runtime.md)

Status: `runtime_foundation_implemented_not_authorized`

This document records the Claude Code runtime boundary required for the formal AppSec assessment. The initial audit checked only local capabilities and official requirements. The later implementation installed Claude Code only inside an isolated Docker image and ran an offline version check. It did not install Claude on the host, authenticate, invoke a model, read credential contents, or change `approval_status`. Formal execution still requires separate Security Engineer approval.

## Local audit results

| Item | Observation | Formal-assessment impact |
| --- | --- | --- |
| Claude Code | The host has no `claude` command; the isolated image pins version `2.1.278` | The reviewer must run through the controlled container |
| Node.js / npm | Node.js `v22.17.0`, npm `10.9.2`; `npm.cmd` works | The host can support an install flow, but no install occurred |
| Windows | Native Windows with Git for Windows installed | Claude can run on native Windows, but the official Bash sandbox does not support native Windows |
| WSL | Only Docker Desktop's internal distribution was found; no user Linux distribution | There is no current WSL2 workspace for an interactive sandboxed Claude session |
| Docker | Client and server `29.8.0`; `alpine:3.22` is present | The verified project runner can provide filesystem isolation |
| Claude environment variables | No variable names beginning with `ANTHROPIC` or `CLAUDE` were found | No environment credential was found for reviewer use |
| Claude user directory | `%USERPROFILE%\.claude` exists; its contents were not read | The host user directory must not be mounted into the reviewer container or treated as an approved credential source |

The inspection did not read environment-variable values or files under `%USERPROFILE%\.claude`.

## Official runtime requirements

Anthropic documents Windows 10 1809 or later, at least 4 GB RAM, and an internet connection as requirements. Native installation is the recommended method and updates automatically by default. Native Windows does not support the Claude Code Bash sandbox. The sandbox supports Linux and WSL2, where it also requires `bubblewrap` and `socat`.

The first interactive login normally opens a browser. Credential sources also include `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN`, and `apiKeyHelper`. Windows login credentials are stored by default in `%USERPROFILE%\.claude\.credentials.json`. This project will neither inspect nor reuse that host file.

Claude Code's sandbox constrains Bash-style subprocesses; built-in Read/Edit/Write tools remain governed by the permission system. Sandboxed subprocesses inherit the parent environment by default. Anthropic provides `sandbox.credentials` and `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB` to restrict subprocess credential access, but those settings do not replace container mounts, egress control, or approval gates.

## Runtime model selected for this project

The formal reviewer should run in a version-pinned Linux container image rather than a native Windows host session. The container must enforce these boundaries:

- mount only runner-validated phase input read-only at `/review/input`;
- make only `/review/output` writable and keep the source repository, parent directory, `.git`, database, token files, `.env`, historical reports, and operator truth mapping inaccessible;
- use an isolated `CLAUDE_CONFIG_DIR` and never mount the host `%USERPROFILE%\.claude`;
- pin and record the Claude Code version, with automatic updates and plugin installation disabled during the formal run;
- disable Claude.ai MCP connectors, Artifacts, nonessential traffic, and telemetry to reduce reachable hosts and data flows;
- inject the Claude credential at runtime, never into the bundle, command line, logs, reports, or image layers; subprocesses must use environment scrubbing or explicit credential deny/mask rules;
- keep the container root filesystem read-only and use separate controlled writable mounts for temporary data and reviewer output;
- retain the existing `prepare`, phase 1 seal, human authorization, and phase 2 release state machine.

The container is the primary isolation boundary. Claude Code's own sandbox may add defense in depth, but it cannot be the only control because it does not cover every built-in file tool.

## Implemented offline container foundation

`reviewer/runtime/` now contains:

- `node:22.17.0-bookworm-slim` pinned by digest;
- Claude Code `2.1.278` with a `package-lock.json` that contains platform-package integrity values;
- `/etc/claude-code/managed-settings.json`, which disables bypass permission mode, Claude.ai connectors, Artifacts, skill/plugin synchronization, automatic updates, telemetry, error reporting, and nonessential traffic, and enables subprocess environment scrubbing;
- non-root UID/GID `10001:10001`;
- `bubblewrap` and `socat`, required for Claude Code subprocess isolation;
- an in-container launcher that reads credentials only from `/run/secrets/anthropic_api_key`;
- runner-generated arguments for read-only input, writable output, a read-only root filesystem, restricted tmpfs mounts, dropped capabilities, `no-new-privileges`, and `--network none`.

`python -m scripts.reviewer_runtime_smoke` passed on Docker Desktop and verified the version, UID, filesystem boundaries, temporary configuration, absence of a default route, and absence of credential environment variables. The script runs the smoke test against the image ID from that build and records the ID in the local result. A formal run must still use and record an immutable registry digest.

The foundation smoke executes only `claude --version` and local boundary probes. The later combined smoke also ran credential-free, network-free `claude doctor`, confirming that the CLI accepts the managed environment with no installation issue. The canary must still provide final settings evidence from a real model session.

## Network egress boundary

The legacy runner's `--network none` mode is suitable for offline validation but cannot make a real Claude API request. [Restricted egress](reviewer-egress.en.md) has passed both independent and combined smoke tests. The new [isolated handoff](reviewer-execution.en.md) generates the internal-plus-proxy Compose topology, which the Security Engineer creates manually after approval. Docker networking blocks direct reviewer connections while the separate proxy enforces the host allowlist.

The minimum host set depends on the authentication method:

| Host | Purpose | Project policy |
| --- | --- | --- |
| `api.anthropic.com` | Anthropic API requests | Required for the formal reviewer |
| `platform.claude.com` | Console/OAuth token exchange, refresh, and revocation | Allow only when required by the selected authentication flow |
| `claude.ai`, `claude.com` | Interactive claude.ai login | Prefer to avoid in the formal noninteractive container |
| `mcp-proxy.anthropic.com` | Claude.ai MCP connectors | Deny and disable connectors |
| `downloads.claude.ai`, `registry.npmjs.org` | Installation, updates, or plugin dependencies | Handle during image build; deny at formal runtime |
| Datadog intake, `raw.githubusercontent.com`, `code.claude.com`, and other optional hosts | Telemetry, error reports, release notes, or documentation lookup | Deny at formal runtime and disable nonessential traffic |

The egress proxy must also reject arbitrary IP addresses, redirects to hosts outside the allowlist, and reviewer attempts to add domains. Proxy logs may retain connection metadata only and must not record authorization headers, request bodies, or model content.

## Credential lifecycle

Before a formal run, select a dedicated, revocable, least-privilege reviewer credential. Prefer an external secret source or `apiKeyHelper` that supplies a short-lived credential at startup, with the secret source mounted outside the bundle. Do not expose a developer's personal Claude configuration directory to the container.

The run may record the credential source type and a non-secret identifier, never the secret. Afterward, revoke or expire the credential, remove the temporary configuration directory, and verify that outputs contain no token. Before any real authentication, model call, or cost, separately approve the model, budget, credential mechanism, and network allowlist.

## Readiness state

| Control | State | Work before formal assessment |
| --- | --- | --- |
| Frozen bundle and hash verification | Implemented | Use the recorded formal candidate and verify it again |
| Read-only input, writable output, no source-repository mount | Passed a real Docker smoke test | Repeat on the final Claude image |
| Two-phase seal/release gate | Implemented | Retain human authorization |
| Claude Code installation and version pin | Offline image foundation implemented | Record an immutable registry digest before formal execution |
| Linux runtime foundation | Verified | Binary, non-root identity, Docker filesystem boundaries, and a clean `claude doctor` result passed |
| Restricted network egress | Combined smoke passed | Enable only the verified internal-plus-proxy topology after formal start approval |
| Dedicated credential injection and subprocess scrubbing | The dedicated workspace API-key design is approved, and the secret-file wrapper passed the combined synthetic-sentinel check | The Security Engineer supplies an external key file at manual launch; the project does not read its value |
| Nonessential connections, plugins, and connectors disabled | Managed settings frozen | Verify that Claude loads them and observe actual connections before enabling egress |
| Model and cost budget | Fixed model and per-run budget approved; interactive CLI has no cost/turn hard stop | Use the 900-second timeout and Workspace spend limit, then reconcile usage after the manual run |
| Formal Claude execution | v2 is approved for Security Engineer manual launch | The first attempt produced no assessment result; Codex does not launch the model |

The repaired pinned reviewer container, combined restricted egress, all three secret-file formats, and mount boundaries passed model-free validation. Security Engineer manual-launch approval for v2 is recorded.

## Official sources

- [Claude Code setup](https://code.claude.com/docs/en/setup)
- [Claude Code authentication](https://code.claude.com/docs/en/authentication)
- [Claude Code network configuration](https://code.claude.com/docs/en/network-config)
- [Claude Code settings](https://code.claude.com/docs/en/settings)
- [Claude Code sandboxing](https://code.claude.com/docs/en/sandboxing)

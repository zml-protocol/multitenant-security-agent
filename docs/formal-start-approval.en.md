# Claude Reviewer Manual-Launch Approval Package

English | [中文](formal-start-approval.md)

Status: `approved_for_security_engineer_manual_launch`

This package binds the validated vulnerable candidate and generated isolated reviewer workspace. Codex completed preparation and container validation. With explicit project-owner authorization, it ran one isolated model preflight that could see only a fixed probe file; it did not mount or read the reviewer bundle and did not expose the API-key value. The formal assessment has not started.

## Bound objects

| Object | Value |
| --- | --- |
| Candidate-attestation SHA-256 | `c2cd87005bf1333be573df341e86837eca0f9c755fb6938fd0b6a2b1b01e76e7` |
| Start-approval-package SHA-256 | `258148e4c18dd68b8f241d07291469c0b3a81529362ea444089aedef55798193` |
| Handoff-manifest SHA-256 | `9dc4e0e2dc2f9b6cf9b93ba8994762df5e260062ba44c9dfd05820a828c7d5ad` |
| Vulnerable-code commit | `14a7b48ae30b833962752e4d65b7e03ade5664a1` |
| Fixture / scenario / bundle | `fixture-256eb13b57860e22` / `scenario-7f3a` / `bundle-6a1a247aca19153c0d22` |
| Workspace | `.local/reviewer-handoffs/appsec-v1-phase1-ready-v4/` |
| Separate results directory | `.local/reviewer-results/appsec-v1-phase1-ready-v4/` |
| Model | `claude-sonnet-5` |
| Claude tools | `Read`, `Glob`, `Grep`, and `Write` restricted to `/review/output` |
| Prohibited tools | `Bash`, `Edit`, `WebFetch`, `WebSearch`, MCP, and browsers |
| Egress | no direct reviewer egress; the proxy permits only `api.anthropic.com:443` |

The machine-readable object is `assessment/appsec/v1/formal-start-approval-package.json`. It contains responsibilities, hashes, budgets, and non-secret state only; it contains no API-key value.

## v4 preparation and preflight

The approved v2 manual run failed because `Read` tool results were not returned to the model. Claude read no code, created no output, and produced no finding. v2 remains frozen as infrastructure-failure evidence.

v3 removes the unsupported `--restricted` flag and uses the container boundary for isolation. A separate preflight service mounted only `read-probe.txt`; Claude returned the exact expected value `REVIEWER_READ_CHANNEL_OK_8D2F4A61`. The same run exposed the current Claude Code file-permission syntax, so the managed rule was corrected to `Edit(/review/output/**)` while the actual exposed output tool remains `Write`.

The v4 assessment-window immutability commitment and Security Engineer manual launch were approved by `project_owner` at `2026-09-20T03:02:30.589534Z`. `codex_may_launch_claude` remains `false`.

## One-command launch after approval

Store the Anthropic API key as a single-line text file outside the repository, for example `C:\secure\anthropic-api-key.txt`. Then run this command from any directory in Windows Terminal:

```text
D:\multitenant-security-agent\.local\reviewer-handoffs\appsec-v1-phase1-ready-v4\START-CLAUDE.cmd "C:\secure\anthropic-api-key.txt"
```

The command builds the containers, opens interactive Claude Code, and runs `docker compose down -v` after exit. The launcher checks human approval before the in-container credential wrapper reads the Compose secret. Neither project Python code nor Codex reads the key value.

Claude can only review `/review/input` statically. The run does not start the application, provide application tokens, issue HTTP requests, or perform dynamic tests. Results persist in the separate `/review/output` host directory, including bilingual findings, remediation advice, limitations, and the JSON log.

## Runtime limits

The container enforces a 900-second timeout, a read-only root filesystem, read-only input, and a process-level 1 MiB limit for each output file. Interactive Claude Code currently has no verified native hard-stop flags for aggregate tokens, turns, or dollar cost, so 12 turns and `$1.00` are approved planning boundaries. The formal run also depends on an Anthropic Workspace spend limit and post-run usage reconciliation. The Security Engineer should exit the session when the planning boundary is reached.

## Interview explanation

This design separates assessment preparation, run authorization, and security judgment. Codex generates a reviewable environment. The Security Engineer binds and personally launches the exact candidate. Claude performs only static code review and drafts findings and remediation advice. The Security Engineer decides reachability, whether dynamic evidence is needed, finding validity, impact, and severity.

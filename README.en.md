# Multi-Tenant Security Agent Lab

English | [中文](README.md)

This is a dual-workflow security lab for a security engineering interview. See the [project vision and roadmap](docs/project-vision.en.md), the [requirements baseline](spec.en.md), the [current phase implementation notes](docs/phase1.en.md), the [reviewer isolation design](docs/reviewer-bundle.en.md), the [staged reviewer runner](docs/reviewer-runner.en.md), the [Claude runtime readiness audit](docs/claude-runtime.en.md), the [restricted egress design](docs/reviewer-egress.en.md), the [credential and budget gate](docs/reviewer-auth-budget.en.md), the [controlled execution design](docs/reviewer-execution.en.md), and the [final start approval package](docs/formal-start-approval.en.md).

The final goal includes a human-in-the-loop, white-box AppSec AI Agent Flow and an Alibaba Cloud DDoS / Network Security Incident Response Flow. Phase 1 is complete: FastAPI + SQLite, two tenants and six test users, three GET endpoints, four modes, an independent authorization matrix, redacted JSON/Markdown reports, structured application logs, and remediation regression testing. No model, Alibaba Cloud resource, SLS integration, or response executor is connected yet.

The human-authored assessment inputs for workflow 1 are under [`assessment/appsec/v1/`](assessment/appsec/v1/). Before a formal Claude review begins, the Security Engineer must review the brief, security requirements, and reviewer input manifest, then record approval against a frozen Git commit.

## Windows PowerShell Quick Start

Run these commands from the project root. You do not need to activate the virtual environment or change the PowerShell execution policy.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.seed
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m scripts.demo
```

If `.venv` or `.local` already exists, reuse it and skip the corresponding initialization step. The initializer refuses to overwrite an existing database or token file so that a remediation retest cannot accidentally replace the data. The default seed is 42; test data is reproducible, while tokens are generated independently each time. Email addresses use `example.com`, and phone values use explicit `TEST-PHONE-...` synthetic placeholders.

Demo output is written to `reports/local/demo/`: each of the four modes and three secure retests has a `report.json` plus Chinese and English Markdown reports; `comparison.json` contains the summary. This demo uses an in-process TestClient and does not start a network service.

## Real HTTP Verification

The following command temporarily starts secure mode, runs at no more than two requests per second, verifies all 54 checks and their log correlation, and stops the service automatically. Port 8000 must be available.

```powershell
.\.venv\Scripts\python.exe -m scripts.smoke
```

Reports are written under `reports/local/http-secure/`; the server log is `.local/smoke-access.log`.

For manual operation, start the application in terminal 1:

```powershell
$env:LAB_MODE = 'secure'
.\.venv\Scripts\python.exe -m app.serve
```

Run the fixed matrix in terminal 2:

```powershell
.\.venv\Scripts\python.exe -m scanner.run --output reports/local/manual-secure
```

The target is fixed to `http://127.0.0.1:8000`; the CLI accepts no other target. It generates GET requests only for known users, does not follow redirects, and ignores environment proxies. The 54 requests take approximately 27 seconds, with a ten-second timeout per request. Exit codes are: 0 for all checks passing, 1 for one or more confirmed violations, and 2 for one or more inconclusive results. If violations and inconclusive results coexist, the exit code is 1.

## Vulnerability Modes and Retesting

Stop the application in terminal 1 with Ctrl+C, select one mode, and restart it:

```powershell
$env:LAB_MODE = 'same_tenant_bypass'
.\.venv\Scripts\python.exe -m app.serve
```

Run the executor again in terminal 2 and use a separate output directory:

```powershell
.\.venv\Scripts\python.exe -m scanner.run --output reports/local/manual-same-tenant
```

| LAB_MODE | Expected confirmed violations | Missing/invalid credential checks |
| --- | ---: | --- |
| secure | 0 | All 6 pass |
| same_tenant_bypass | 8 | All 6 pass |
| cross_tenant_bypass | 18 | All 6 pass |
| list_role_bypass | 4 | All 6 pass |

For remediation validation, stop the application, set `LAB_MODE` back to `secure`, restart it, and rerun the same matrix. Do not reinitialize `.local`. The mode is read only at startup and there is no HTTP mode-switch endpoint. Secure mode is the default; an unknown mode causes startup to fail.

## Code Guide

- `app/seed.py`: data snapshots, independently generated tokens, and SQLite initialization.
- `app/main.py`: authentication, three business routes, policy calls, and structured auditing, with no scenario answer.
- `app/policy.py`: the default secure authorization implementation.
- `evaluation/`: operator-only neutral scenarios and truth mapping, excluded from reviewer bundles.
- `reviewer/bundle.py`: builds a single-scenario, redacted reviewer bundle with integrity hashes.
- `reviewer/runner.py`: prepares isolated phase inputs, seals phase 1 output, and enforces the human-approved phase 2 release gate.
- `reviewer/runtime/`: defines the Linux reviewer image with a pinned Claude Code version, base-image digest, npm integrity lock, and enforced managed settings.
- `reviewer/egress/`: defines the inactive, default-deny, proxy-only egress foundation with a fixed `api.anthropic.com:443` allowlist.
- `reviewer/auth_budget/`: defines the approved but execution-disabled dedicated API-key source, fixed model, budget fields, and synthetic-sentinel leakage checks.
- `reviewer/execution/`: generates the interactive static-only Claude command, read-only input/separate output, isolated Compose handoff, and one-command Windows Terminal entry point; neither the project nor Codex launches Claude.
- `fixtures/permissions.v1.json`: independent, explicit authorization expectations.
- `fixtures/request-template.v1.json`: a normal request template with no credentials.
- `scanner/`: the fixed matrix, response evidence assessment, and reporting.
- `tests/`: full matrix tests, mode isolation, remediation retests, error/timeout fixtures, log correlation, and redaction.
- `scripts/demo.py`: in-process complete demo; `scripts/smoke.py`: real HTTP verification; `scripts/reviewer_runtime_smoke.py`: credential-free, offline reviewer-container isolation verification; `scripts/reviewer_egress_smoke.py`: proxy allowlist and direct-egress blocking verification; `scripts/reviewer_auth_budget_smoke.py`: network-free, cost-free synthetic credential boundary verification; `scripts/reviewer_combined_smoke.py`: combined container-boundary verification; `scripts/reviewer_execute.py`: prepares or approves a manual handoff and never launches Claude.

`.local/`, databases, tokens, runtime logs, and local reports are ignored by Git. Raw responses are not persisted; reports retain only user/tenant test IDs, matched field names, and evidence references. The current authentication scheme is for a local lab and is not a production identity platform.

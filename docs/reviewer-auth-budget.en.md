# Reviewer Credential and Budget Gate

English | [中文](reviewer-auth-budget.md)

Status: `approved_not_formally_authorized`

This stage freezes and approves the credential source, model, and budget fields for the Claude reviewer and validates the secret boundary with a local synthetic sentinel. It configures no real API key, invokes no model, and incurs no cost. The formal start gate now permits only the Security Engineer to launch the bound workspace manually; project and Codex model-invocation capabilities remain disabled.

## Credential design

The formal assessment should use a revocable workspace API key created in the Anthropic Console only for this project. It must not reuse the Windows host's personal Claude login, `%USERPROFILE%\.claude`, or another personal configuration. The real key may enter the reviewer process through `ANTHROPIC_API_KEY` only when an approved run starts. It must never enter:

- Git, the reviewer bundle, an image layer, or persistent configuration;
- command-line arguments, a run manifest, a Docker plan, logs, or reviewer output;
- subprocesses launched by Claude;
- assessment reports or evidence files.

The run record may contain only the credential type and a later non-secret key identifier. Each formal run must revoke the key afterward and remove the temporary Claude configuration directory.

## Fixed model and approved budget

`reviewer/auth_budget/profile.json` is the Security Engineer-approved machine-readable design. Its execution switches remain disabled because the credential is supplied only when the Security Engineer manually launches the container:

| Control | Proposed value |
| --- | ---: |
| Model | `claude-sonnet-5` |
| Aggregate input-token maximum per run | 100,000 |
| Aggregate output-token maximum per run | 20,000 |
| Model API-call maximum | 12 |
| Agentic-turn planning boundary | 12 |
| Supplemental tool-call maximum | 30 |
| Maximum duration | 900 seconds |
| Standard planning price | $2 / MTok input, $10 / MTok output |
| Standard cost at token ceilings | $0.40 |
| Per-run approval ceiling | $1.00 |

The model and prices are based on Anthropic's official documentation as of 2026-09-19. The approver, UTC time, and approval-subject SHA-256 are recorded in the profile and approval record. Model availability and pricing must still be rechecked before a formal run.

The $0.40 figure is a planning estimate based on standard uncached input and output prices. Claude Code may make several API requests and may incur cache or retry charges, so local preflight cannot replace provider billing controls. In the pinned CLI, `--max-budget-usd` and `--max-turns` apply only to non-interactive `--print`. The interactive assessment therefore uses an outer 900-second timeout, a dedicated Anthropic Workspace spend limit, and post-run usage reconciliation. API-call and aggregate-token values remain approval and reconciliation boundaries rather than local hard stops.

## Synthetic sentinel verification

Run:

```text
python -m scripts.reviewer_auth_budget_smoke
```

The script places a random invalid synthetic key only in an environment copy held by the parent Python process. It then:

1. verifies the approved profile hash while model invocation remains disabled;
2. creates an offline execution envelope with no key value;
3. removes `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, and `CLAUDE_CODE_OAUTH_TOKEN` from the child environment;
4. checks that the sentinel is absent from the child command line, child environment, existing frozen reviewer bundle, and persisted output; and
5. writes only Boolean results under the Git-ignored `.local/reviewer-auth-budget/`.

The check opens no network connection and does not run Claude. It shows that the current project configuration and local validation path do not copy the fake credential into those locations. The Security Engineer keeps the real key outside the project and supplies it only as a secret file during manual Docker Compose launch.

## Project-side gates that remain closed

- `formal_execution_authorized` is `false`;
- `model_invocation_enabled` is `false`;
- `approval.approved` is `true`, while `model_invocation_enabled` remains `false`;
- `assessment/appsec/v1/start-gate.json` is `approved_for_security_engineer_manual_launch` for v2, while `codex_may_launch_claude` remains `false`;
- the runtime, egress, and execution profiles all keep `formal_execution_authorized` set to `false`.

## Official sources

- [Anthropic model overview](https://platform.claude.com/docs/en/models/overview)
- [Anthropic API pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- [Claude Code authentication](https://code.claude.com/docs/en/authentication)
- [Anthropic API rate limits and spend limits](https://platform.claude.com/docs/en/api/rate-limits)

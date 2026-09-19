# Reviewer Credential and Budget Gate

English | [中文](reviewer-auth-budget.md)

Status: `proposed_tested_not_approved`

This stage freezes the proposed credential source, model, and budget approval fields for a future Claude reviewer and validates the secret boundary with a local synthetic sentinel. It configures no real API key, invokes no model, incurs no cost, and does not activate the current runner or restricted egress proxy. The formal assessment start gate remains closed.

## Credential design

The formal assessment should use a revocable workspace API key created in the Anthropic Console only for this project. It must not reuse the Windows host's personal Claude login, `%USERPROFILE%\.claude`, or another personal configuration. The real key may enter the reviewer process through `ANTHROPIC_API_KEY` only when an approved run starts. It must never enter:

- Git, the reviewer bundle, an image layer, or persistent configuration;
- command-line arguments, a run manifest, a Docker plan, logs, or reviewer output;
- subprocesses launched by Claude;
- assessment reports or evidence files.

The run record may contain only the credential type and a later non-secret key identifier. Each formal run must revoke the key afterward and remove the temporary Claude configuration directory.

## Fixed model and proposed budget

`reviewer/auth_budget/profile.json` is a machine-readable proposal awaiting Security Engineer approval:

| Control | Proposed value |
| --- | ---: |
| Model | `claude-sonnet-5` |
| Aggregate input-token maximum per run | 100,000 |
| Aggregate output-token maximum per run | 20,000 |
| Model API-call maximum | 12 |
| Supplemental tool-call maximum | 30 |
| Maximum duration | 900 seconds |
| Standard planning price | $2 / MTok input, $10 / MTok output |
| Standard cost at token ceilings | $0.40 |
| Per-run approval ceiling | $1.00 |

The model and prices are based on Anthropic's official documentation as of 2026-09-19. Before a formal run, recheck model availability and pricing, then record the final profile SHA-256, approver, and UTC time.

The $0.40 figure is a planning estimate based on standard uncached input and output prices. Claude Code may make several API requests and may incur cache or retry charges, so local preflight cannot replace provider billing controls. A formal run also requires a dedicated Anthropic workspace spend limit, external observation, a fail-closed supervisor, and post-run usage reconciliation. The current API-call and aggregate-token values are approval boundaries; the project does not yet claim that Claude Code exposes a verified native hard stop for them.

## Synthetic sentinel verification

Run:

```text
python -m scripts.reviewer_auth_budget_smoke
```

The script places a random invalid synthetic key only in an environment copy held by the parent Python process. It then:

1. verifies that the profile remains unapproved and model invocation remains disabled;
2. creates an offline execution envelope with no key value;
3. removes `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, and `CLAUDE_CODE_OAUTH_TOKEN` from the child environment;
4. checks that the sentinel is absent from the child command line, child environment, existing frozen reviewer bundle, and persisted output; and
5. writes only Boolean results under the Git-ignored `.local/reviewer-auth-budget/`.

The check opens no network connection and does not run Claude. It shows that the current project configuration and local validation path do not copy the fake credential into those locations. The check must be repeated against the final container, proxy, and supervisor combination before a real run.

## Gates that remain closed

- `formal_execution_authorized` is `false`;
- `model_invocation_enabled` is `false`;
- `approval.approved` is `false`, with no approver, time, or profile hash;
- the reviewer runtime still uses `--network none` and `credential_injection: disabled`;
- the egress proxy is still disconnected from the runner.

## Official sources

- [Anthropic model overview](https://platform.claude.com/docs/en/models/overview)
- [Anthropic API pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- [Claude Code authentication](https://code.claude.com/docs/en/authentication)
- [Anthropic API rate limits and spend limits](https://platform.claude.com/docs/en/api/rate-limits)


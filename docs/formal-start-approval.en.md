# Claude Reviewer Final Start Approval Package

English | [中文](formal-start-approval.md)

Status: `prepared_not_approved`

This package separates approval of the run design from authorization to perform this specific formal Claude assessment. The candidate, budget, containers, and egress controls have been validated, but the Security Engineer has not accepted the assessment-window immutability commitment or supplied the final approver and time. Every execution switch therefore remains closed. No real API key has been created or read, no model was called, and no cost was incurred.

## Bound objects

The machine-readable package is `assessment/appsec/v1/formal-start-approval-package.json`:

| Object | Bound value |
| --- | --- |
| Candidate-attestation SHA-256 | `8a2d419e75754557c8ef61e03dd52b8acd8882d92d9bd53bde764b73e86272bb` |
| Approval-package SHA-256 | `fe0b63ffdd00aa5c3b7d44f95615e2aef7cc7570092fe7eefe4add17c8f0059b` |
| Vulnerable-code commit | `14a7b48ae30b833962752e4d65b7e03ade5664a1` |
| Fixture | `fixture-256eb13b57860e22` |
| Scenario | `scenario-7f3a` |
| Bundle | `bundle-6a1a247aca19153c0d22` |
| Model | `claude-sonnet-5` |
| Per-run limits | `$1.00`, 12 turns, 900 seconds, 1 MiB captured output |
| Tools | `Read`, `Glob`, `Grep` |
| Egress | `api.anthropic.com:443` only |

The package itself remains `prepared_not_approved` as the immutable approval subject. Final authorization is recorded in `start-gate.json`, which references SHA-256 values for this file and the candidate attestation. Rewriting the package cannot introduce new content into an already approved run.

## Two remaining human decisions

1. The Security Engineer accepts that vulnerable code, requirements, fixture, reviewer manifest, bundle, and bound control files will not change from final approval through completion of this assessment. A needed change terminates the run and requires new attestation and approval.
2. The Security Engineer supplies the final approver and UTC time and explicitly changes the state from `requirements_approved` to `ready_for_claude_review`.

These are the two unchecked items in Section 8 of the approval record. Preparing this package does not make either decision for the approver.

## Anthropic Console prerequisites

You must perform these actions in Anthropic Console. They may require purchasing non-refundable prepaid credits. This preparation step performs no paid action.

1. Create a dedicated project Workspace under **Settings → Workspaces**, such as `appsec-v1-reviewer`. Anthropic states that only an Organization Admin can create a Workspace.
2. Open that Workspace's **Limits** tab and set its spend limit. Current project policy requires a recorded positive value no greater than `$1.00`. If Console does not permit that value, stop and amend and reapprove the project budget before launch; do not silently substitute a higher limit.
3. Confirm that auto-reload is disabled on the organization **Billing** page. The organization's prepaid-credit balance does not replace the project's `$1.00` per-run CLI stop.
4. Create a dedicated key in the Workspace's **API Keys** tab with a descriptive, non-sensitive label such as `appsec-v1-reviewer-20260919`.
5. Store the key value only in an ephemeral file outside the repository. Never place it in JSON, Markdown, command arguments, chat, Docker environment arguments, or an image. Approval evidence records only the Workspace name and key label.
6. Disable or delete the key after the run and reconcile actual usage in Anthropic's Usage/Cost reports by Workspace and API key.

Anthropic's official guidance says that a Workspace key is bound to its Workspace; the Workspace Limits page supports spend limits and notifications; the Billing page controls prepaid credits and auto-reload; and Usage/Cost reports can be filtered by Workspace and API key.

## Atomic changes after approval

The package's `activation_changes` records 14 fixed JSON Pointer transitions. They must be applied together with `start-gate.json`, the two approval-record checkboxes, and final approval metadata. They must not leave a partially enabled state. The changes cover:

- auth/budget status, formal execution, and model invocation;
- authorization for the controlled execution controller;
- runtime `internal_proxy_only` mode and read-only secret-file injection;
- activation of the egress proxy for the formal runner;
- reviewer-manifest status `ready_for_claude_review`; and
- start-gate approver, UTC time, immutability commitment, non-secret Workspace/key identifiers, spend-limit period, and both SHA-256 values.

Before creating a Docker network or reading a secret file, the controller revalidates these values. Execution fails if any value is absent, the package changed, the spend limit exceeds `$1.00`, auto-reload is not explicitly disabled, or a current value differs from its approved target.

## Interview explanation

This step demonstrates the human authorization boundary. Codex can prepare the candidate, controls, cost boundary, and credential path as verifiable objects, but it cannot accept the freeze commitment or authorize model execution for the Security Engineer. File hashes bind approval to exact inputs and controls. The secret value does not enter approval evidence. Provider limits, the CLI stop, and the supervisor provide separate layers of cost control.

## Official sources

- [Creating and managing Workspaces](https://support.anthropic.com/en/articles/9796807-creating-and-managing-workspaces)
- [How do I pay for API usage?](https://support.anthropic.com/en/articles/8977456-how-do-i-pay-for-my-api-usage)
- [Cost and Usage Reporting in Console](https://support.anthropic.com/en/articles/9534590-cost-and-usage-reporting-in-console)
- [API Console Roles and Permissions](https://support.anthropic.com/en/articles/10186004-api-console-roles-and-permissions)

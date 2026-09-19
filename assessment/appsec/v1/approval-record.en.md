# AppSec Assessment v1 Approval Record

English | [中文](approval-record.md)

This is the single formal sign-off location for workflow 1. Read the linked sources first and edit any inaccurate requirement in its source file; do not record exceptions only here. Claude may begin a formal assessment only after every decision is approved, the code and fixture are frozen, and all version fields are complete.

## Linked Sources

- [Assessment Brief](assessment-brief.en.md): business context, actors, assets, trust boundaries, scope, test constraints, and evidence standard.
- [Security Requirements](security-requirements.json): machine-readable requirements used by Claude and deterministic tools.
- [Reviewer Input Manifest](reviewer-input-manifest.json): what Claude may read, what is forbidden, and required outputs.
- [Authorization Matrix](../../../fixtures/permissions.v1.json): expected object and list access for all six identities.
- [Normal Request Template](../../../fixtures/request-template.v1.json): the assessment starting request.

## 1. Approval Metadata

| Field | Value |
| --- | --- |
| approval_status | `requirements_approved` |
| approver | `project_owner` |
| approved_at_utc | `2026-09-19T18:42:29Z` |
| requirement_version | `appsec-v1.0` |
| git_commit | `14a7b48ae30b833962752e4d65b7e03ade5664a1` |
| fixture_id | `fixture-256eb13b57860e22` |
| assessment_scenario_id | `scenario-7f3a` |
| candidate_bundle_id | `bundle-6a1a247aca19153c0d22` |
| candidate_generated_at_utc | `2026-09-19T20:44:40.966113Z` |
| candidate_validated_at_utc | `2026-09-19T22:54:07.417730Z` |
| candidate_status | `validated_waiting_formal_start_approval` |
| candidate_attestation | `formal-candidate-attestation.json` |
| candidate_attestation_sha256 | `8a2d419e75754557c8ef61e03dd52b8acd8882d92d9bd53bde764b73e86272bb` |
| formal_start_approval_package | `formal-start-approval-package.json` |
| formal_start_approval_package_sha256 | `fe0b63ffdd00aa5c3b7d44f95615e2aef7cc7570092fe7eefe4add17c8f0059b` |
| bundle_manifest_sha256 | `69049b3e03d58c6742bcd475bdc090465aef3b510c2f6ae4134efad3507fc7be` |
| approved_auth_budget_subject_sha256 | `a764deb46e1b106be04a34548f6b179a22e0c2dfcefa34f2650606b28f5df3b4` |

### Frozen Git References

| Reference | Target commit | Mutation policy |
| --- | --- | --- |
| `assessment/v1-vulnerable` | `14a7b48ae30b833962752e4d65b7e03ade5664a1` | Frozen; no commits, deletion, force-push, or ref movement |
| `appsec-v1-vulnerable` | `14a7b48ae30b833962752e4d65b7e03ade5664a1` after annotated-tag dereference | Immutable vulnerable application marker |
| `remediation/v1` | Initially `14a7b48ae30b833962752e4d65b7e03ade5664a1` | Writable only after the Security Engineer confirms a finding |
| `appsec-v1-fixed` | Not created | Create only after remediation regression and human acceptance |

GitHub reported HTTP 403 for both repository rulesets and classic branch protection because this is a private repository on the current free plan. The repository was not made public and no paid plan was created. Until platform-enforced protection becomes available, the annotated tag, the no-mutation process rule, and explicit remote SHA verification are the freeze controls.

This workstation also has a local `.git/hooks/pre-push` guard that rejects deletion or movement of `assessment/v1-vulnerable` and `appsec-v1-vulnerable`. Tests confirmed that an unchanged frozen reference is allowed while branch and tag deletion attempts are blocked. This hook is a local defense-in-depth control; it is not versioned, does not protect pushes from another clone, and does not replace server-side protection.

Before review or deployment, verify the remote references without checking out the frozen branch:

```text
git ls-remote origin refs/heads/assessment/v1-vulnerable refs/tags/appsec-v1-vulnerable "refs/tags/appsec-v1-vulnerable^{}"
```

The branch value and dereferenced tag value must both equal `14a7b48ae30b833962752e4d65b7e03ade5664a1`. A mismatch stops the assessment or deployment and requires Security Engineer review.

Status moves only in this order:

`pending` → `requirements_approved` → `ready_for_claude_review`

- `requirements_approved`: Sections 2–7 are approved, although code, fixture, or scenario may not yet be frozen.
- `ready_for_claude_review`: Section 8 is also complete and the Git commit, fixture ID, scenario ID, and UTC time are recorded.

## 2. Business, Actors, and Data

- [x] The business is a multi-tenant profile read service in a shared application instance.
- [x] There are two fixed tenants, each with two ordinary users and one tenant administrator.
- [x] An ordinary user may read only themselves; a tenant administrator may read their own tenant but is not a global administrator.
- [x] `name`, `email`, and `phone` are protected synthetic data; unauthorized access is treated as a real finding even though the data is not personal data.
- [x] A bearer token is a Secret and does not enter source code, model context, logs, or reports; the server stores only a digest.
- [x] Redacted `user_id`, `tenant_id`, and `role` may appear in assessment evidence.
- [x] Authorization decisions must use server-authoritative identity, tenant, and role information. Client-supplied claims must not override these values.

If changes are needed, edit Sections 1, 3, and 4 of `assessment-brief.en.md` and `security-requirements.json`, then review this section again.

## 3. Security Requirements and Expected Behavior

| Requirement | Decision to confirm | Decision |
| --- | --- | --- |
| AUTHN-01 | All three business endpoints require a server-mapped opaque bearer token; missing, malformed, or invalid credentials return 401 without protected data | `approved` |
| AUTHN-02 | Client tenant, role, and user claims cannot change identity or increase access | `approved` |
| AUTHZ-ME-01 | `/api/me` returns only the authenticated user's allowed public profile fields | `approved` |
| AUTHZ-OBJ-01 | An ordinary user reads only themselves; other same-tenant and all cross-tenant targets are denied | `approved` |
| AUTHZ-OBJ-02 | A tenant administrator reads their own tenant; every cross-tenant target is denied | `approved` |
| AUTHZ-LIST-01 | `/api/users` is available only to a tenant administrator | `approved` |
| AUTHZ-LIST-02 | An administrator list contains all users in the current tenant and no user from another tenant | `approved` |
| DATA-01 | Success responses contain only explicitly approved public fields and never expose authentication tokens, credential digests, internal authorization fields, or other sensitive internal data | `approved` |
| ERROR-01 | 401, 403, 404, 5xx, and other errors contain no credential or protected profile data | `approved` |
| AUDIT-01 | Every test is correlated by run/request ID and logs/reports persist no secret or complete profile | `approved` |
| TOOL-01 | Reviewer tools enforce the approved target, allowed HTTP methods, in-scope routes, approved test identities, known test object IDs, redirect restrictions, and request budget | `approved` |

Change each decision from `pending` to `approved` or `change_requested`. For `change_requested`, update `security-requirements.json` and the relevant brief section first, then synchronize this table with the final text.

## 4. Endpoint Scope and Explicit Exclusions

- [x] Only `GET /api/me`, `GET /api/users/{user_id}`, and `GET /api/users` are in scope.
- [x] `user_id` comes only from the approved six-user fixture; unknown ID enumeration is not allowed.
- [x] Business writes, token guessing, password attacks, social engineering, persistence, and destructive behavior are out of scope.
- [x] Host, Docker, Alibaba Cloud, and network infrastructure testing are out of scope.
- [x] Results do not support performance, DDoS, capacity, or whole-application security conclusions.

## 5. Claude Reviewer Access and Separation of Duties

- [x] In phase 1, Claude may read only the `readable_files` in the frozen generated bundle; the bundle is its only accessible workspace.
- [x] The source repository and its parent directories are inaccessible to Claude, and the manifest allowlist is enforced by the execution environment rather than by prompt instructions alone.
- [x] Claude cannot read raw tokens, the SQLite database, `.env`, historical local reports, or operator scenario answers.
- [x] Existing test code and vulnerability truth labels are withheld in the first pass so Claude cannot treat an existing answer as independent review work.
- [x] The fixed authorization matrix and redacted deterministic results are released only after phase 1 outputs are sealed and the Security Engineer explicitly authorizes phase 2; phase 1 outputs cannot then be rewritten.
- [x] Claude may trace code paths, propose and execute bounded negative tests, collect evidence, and draft findings.
- [x] Claude cannot modify security requirements, application code, final finding status, or severity.
- [x] Codex implements and remediates but cannot use the application authorization function as an independent oracle or approve its own fix.
- [x] The Security Engineer makes the final decision on finding validity, impact, severity, and remediation acceptance.

## 6. Execution and Evidence Boundaries

- [x] The target is fixed to `http://127.0.0.1:8000`; environment proxies and cross-target redirects are disabled.
- [x] The base matrix runs at no more than two requests per second, concurrency two, and a ten-second timeout.
- [x] The tool layer injects credentials by alias and never exposes them to Claude context.
- [x] Raw responses are not written to reports; reports retain only redacted summaries and evidence IDs.
- [x] A 429, timeout, 5xx, redirect, fixture mismatch, or missing evidence is `inconclusive`.
- [x] HTTP 200 alone is not vulnerability evidence; protected data in an error response can still confirm a violation.

## 7. Finding, Remediation, and Regression Rules

- [x] A confirmed finding cites a real run ID, case ID, request ID, evidence ID, and requirement ID.
- [x] Claude submits only a draft finding and evidence-based impact analysis; it cannot decide final severity or invent an exact CVSS score.
- [x] The Security Engineer selects `confirmed`, `rejected`, or `needs_more_evidence` for each finding.
- [x] Only a `confirmed` finding proceeds to Codex remediation.
- [x] Remediation retesting reuses the same fixture, identity map, authorization version, and cases.
- [x] Closing a finding requires evidence that the violation disappeared and previously valid access still succeeds.

After Sections 2–7 are complete, change `approval_status` to `requirements_approved`. This confirms the requirements but does not yet permit a formal Claude assessment.

## 8. Formal Assessment Start Gate

The final start approval package is prepared; see its [guide](../../../docs/formal-start-approval.en.md) and `formal-start-approval-package.json`. The package remains `prepared_not_approved`, and the Security Engineer must explicitly decide the two remaining items below.

- [x] The requirement version no longer contains `-draft`, and the JSON matches this record.
- [x] Assessment code is frozen and the full Git commit SHA is recorded.
- [x] The assessment fixture is frozen and its fixture ID is recorded.
- [x] Obvious `*_bypass` answer labels have been removed from the vulnerability scenario and a neutral scenario ID is recorded.
- [ ] Code, requirements, fixture, and reviewer manifest will not change during assessment.
- [ ] Approver and `approved_at_utc` are complete.
- [x] Claude is again confirmed to have no raw credentials or ground-truth label.

When every item is complete, change `approval_status` to `ready_for_claude_review`. Only this state authorizes formal Claude decision-path review and independent test-matrix generation.

## 9. Change Record

| UTC time | Changed by | Change | Reapproval required? |
| --- | --- | --- | --- |
| `2026-09-19T18:42:29Z` | `project_owner` | Approved AppSec requirements v1.0 (Sections 2–7) | No (initial approval) |
| `2026-09-19T19:41:06Z` | `project_owner` | Approved bundle-only two-phase reviewer access model v2.0 | No (approved in this record) |
| `2026-09-19T19:56:57Z` | `project_owner` | Authorized implementation of the isolated runner plan, phase 1 seal, and phase 2 release gate; Claude execution remains unauthorized | No (implementation of the approved model) |
| `2026-09-19T20:44:40.966113Z` | `codex` | Generated the formal freeze candidate from the recorded clean commit, new fixture, and randomly selected neutral scenario; start-gate decisions remain unchecked | No (candidate generation only) |
| `2026-09-19T21:09:33Z` | `codex` | Recorded vulnerable/remediation Git references and the GitHub Free private-repository protection limitation; no ref was moved and the start gate remains open | No (freeze-control record only) |
| `2026-09-19T21:12:15Z` | `codex` | Installed and tested a local pre-push guard for the frozen branch and vulnerable tag; server-side protection remains unavailable | No (local defense-in-depth control) |
| `2026-09-19T21:22:29Z` | `codex` | Completed the Claude reviewer runtime readiness audit; Claude was neither installed nor executed, credential contents were not read, and the formal start gate remains open | No (runtime-readiness record only) |
| `2026-09-19T21:41:52Z` | `codex` | Implemented and passed the credential-free, offline isolation smoke test for the pinned Claude Code 2.1.278 Linux reviewer image; no authentication or model call occurred, and the formal start gate remains open | No (implementation of the approved runtime foundation) |
| `2026-09-19T21:53:33Z` | `codex` | Implemented and passed the inactive proxy-only egress smoke test; only a TLS handshake to `api.anthropic.com:443` was allowed, with no API request, credential injection, or model call, and the formal runner remains offline | No (implementation of the approved egress foundation) |
| `2026-09-19T22:03:20Z` | `codex` | Froze an unapproved dedicated Anthropic workspace API-key source, `claude-sonnet-5`, and per-run budget proposal, then passed a local synthetic-sentinel leakage check; no real credential, network, or model was used | No (implementation of the approved credential and budget gate design) |
| `2026-09-19T22:22:24Z` | `project_owner` | Approved a dedicated revocable Anthropic workspace API key, `claude-sonnet-5`, 100k/20k token planning boundaries, a 12 model-API-call approval boundary, 12 agentic turns, 30 tool calls, 900 seconds, and a `$1.00` per-run ceiling; model execution was not approved | No (run design approved; formal start gate remains open) |
| `2026-09-19T22:27:14Z` | `codex` | Implemented the fixed Claude command and fail-closed supervisor, then passed a combined synthetic-secret, managed-settings-file, proxy-allowlist, non-allowlist denial, and direct-egress blocking smoke test; no model or cost was involved | No (execution control and cost-free validation) |
| `2026-09-19T22:27:21Z` | `codex` | Validated and attested the formal candidate, binding the frozen commit, fixture, scenario, bundle, profile hashes, and local image IDs; five of seven start-gate items now have evidence and formal execution remains unauthorized | No (candidate validation) |
| `2026-09-19T22:29:53Z` | `codex` | `claude doctor` exposed and drove the fix for missing `bubblewrap`/`socat` in the reviewer image; doctor and the combined smoke passed after rebuilding, with no real credential or model | No (runtime repair and revalidation) |
| `2026-09-19T22:33:53Z` | `codex` | Regenerated the formal candidate attestation against repaired reviewer image `sha256:d496…642a`; the previous attestation was replaced and formal-start status did not change | No (candidate rebinding) |
| `2026-09-19T22:37:07Z` | `codex` | Explicitly disabled MCP, slash commands, and Chrome in the fixed command, then rebound the final command hash; formal execution remains unauthorized | No (execution-surface reduction and candidate rebinding) |
| `2026-09-19T22:38:01Z` | `codex` | Added per-file SHA-256 values for the controller, runtime wrapper/settings, and egress proxy to the attestation, binding the exact control-plane implementation in the uncommitted workspace | No (candidate-integrity strengthening) |
| `2026-09-19T22:55:58Z` | `codex` | Prepared the final start approval package, binding the candidate attestation, fixed budget, and 14 atomic switch changes; added approval-state consistency validation, cross-platform LF hash stability, and official Workspace/key instructions while leaving every switch closed | No (approval subject preparation only; no model authorization or execution) |

After formal approval, any change affecting actors, assets, trust boundaries, scope, expected behavior, tool access, or the finding standard requires a new entry and reapproval. A spelling-only correction that does not change meaning may be recorded as not requiring reapproval.

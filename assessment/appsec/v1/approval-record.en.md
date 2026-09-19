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
| git_commit | Full commit SHA after code freeze |
| fixture_id | To be completed after the assessment data is frozen |
| assessment_scenario_id | To be completed after scenario delabeling |

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

- [x] Claude may read the `readable_inputs` in `reviewer-input-manifest.json`.
- [x] Claude cannot read raw tokens, the SQLite database, `.env`, historical local reports, or operator scenario answers.
- [x] Existing test code and vulnerability truth labels are withheld in the first pass so Claude cannot treat an existing answer as independent review work.
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

- [ ] The requirement version no longer contains `-draft`, and the JSON matches this record.
- [ ] Assessment code is frozen and the full Git commit SHA is recorded.
- [ ] The assessment fixture is frozen and its fixture ID is recorded.
- [ ] Obvious `*_bypass` answer labels have been removed from the vulnerability scenario and a neutral scenario ID is recorded.
- [ ] Code, requirements, fixture, and reviewer manifest will not change during assessment.
- [ ] Approver and `approved_at_utc` are complete.
- [ ] Claude is again confirmed to have no raw credentials or ground-truth label.

When every item is complete, change `approval_status` to `ready_for_claude_review`. Only this state authorizes formal Claude decision-path review and independent test-matrix generation.

## 9. Change Record

| UTC time | Changed by | Change | Reapproval required? |
| --- | --- | --- | --- |
| `2026-09-19T18:42:29Z` | `project_owner` | Approved AppSec requirements v1.0 (Sections 2–7) | No (initial approval) |

After formal approval, any change affecting actors, assets, trust boundaries, scope, expected behavior, tool access, or the finding standard requires a new entry and reapproval. A spelling-only correction that does not change meaning may be recorded as not requiring reapproval.

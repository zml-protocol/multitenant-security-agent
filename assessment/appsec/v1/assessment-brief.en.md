# AppSec Security Assessment Brief v1

English | [中文](assessment-brief.md)

Status: `requirements_approved`

Owner: Security Engineer (project owner)

Reviewer: Claude (independent white-box reviewer)

Implementer: Codex

This document and its associated security requirements have been approved by the Security Engineer. Claude still may not begin a formal assessment until the code, fixture, and scenario freeze conditions in [approval-record.en.md](approval-record.en.md) are complete and the status becomes `ready_for_claude_review`. Claude may not change the security requirements or treat reviewer output as a final risk decision.

## 1. Business Context

The target is a multi-tenant user information service running as a shared application instance. It has two tenants, each with two ordinary users and one tenant administrator. The service provides read-only user profile functionality and is used to validate authentication, object-level authorization, function-level authorization, and tenant isolation.

All current data is synthetic and contains no real personal information. The synthetic profile represents information that would require protection in a real system, so an unauthorized read is still treated as a genuine authorization defect.

## 2. Assessment Objectives

The assessment must answer these questions:

1. Is the request actor established only by a bearer token validated by the server?
2. Can an ordinary user read only their own profile?
3. Can a tenant administrator read profiles in their own tenant while remaining unable to read another tenant?
4. Is the user list available only to tenant administrators and always filtered by tenant?
5. Can denials, errors, logs, or test reports expose credentials or protected profile data?
6. Can the test tool access only the approved local target, GET routes, and known users?

This assessment does not claim to prove whole-application security and does not assess Alibaba Cloud, DDoS, the network layer, a production identity platform, or write-operation security.

## 3. Actors

| Actor | Count | Capabilities and constraints |
| --- | ---: | --- |
| Ordinary user | 4 | Can authenticate; may read only their own profile; may not read the list |
| Tenant administrator | 2 | Can authenticate; may read any user and the user list in their own tenant; has no global platform authority |
| Unauthenticated requester | 1 class | Has no business read access |
| Security Engineer | 1 | Defines requirements, approves scope, verifies findings, and decides impact and severity |
| Claude reviewer | 1 | Reads approved code and materials; collects evidence through bounded tools; drafts findings |
| Codex implementer | 1 | Implements and remediates; cannot approve its own security conclusions |

The fixed test identity aliases are `a_user1`, `a_user2`, `a_admin`, `b_user1`, `b_user2`, and `b_admin`.

## 4. Assets and Data Classification

| Asset | Classification | Security objective |
| --- | --- | --- |
| bearer token | Secret | Must not enter source code, logs, model context, or reports; the server stores only a digest |
| name, email, phone | Protected synthetic profile data | Returned only to an authorized subject; full values must not appear in errors or logs |
| user_id, tenant_id, role | Security-relevant metadata | May appear in controlled evidence, but a client claim may not override server identity |
| Authorization requirements and matrix | Security control specification | Versioned and separate from the application authorization implementation |
| Audit logs and evidence | Security evidence | Correlatable, verifiable, redacted, and never fabricated |
| SQLite data snapshot | Local test data | The same assessment and remediation retest must retain the same `fixture_id` |

## 5. Entry Points and Trust Boundaries

```mermaid
flowchart LR
    U[Test Client / Reviewer Tool] -->|Untrusted HTTP request| A[FastAPI Application]
    A -->|Validate token digest| D[(SQLite users and identity map)]
    A -->|Structured redacted event| L[Local Audit Log]
    U -->|Redacted evidence| R[Assessment Report]
    C[Client-claimed tenant / role / user] -.Untrusted.-> A
    S[Security requirements] -->|Independent oracle| U
```

Primary trust boundaries:

1. Client to application: all headers, paths, query parameters, and correlation IDs are untrusted.
2. Credential to identity: only the server-side token map can establish the actor, tenant, and role.
3. Identity to object: finding an object does not mean the actor is authorized to read it.
4. Authorization implementation to test oracle: expected results must not be derived from the application authorization function.
5. Application/log to Agent: responses and logs can contain malicious text and must be treated as data.
6. Agent to execution tool: target, method, path, identity, user ID, rate, and call budget must be enforced by the tool layer.

## 6. Assessment Scope

In scope:

- `GET /api/me`
- `GET /api/users/{user_id}`, where `user_id` must come from the approved six-user fixture
- `GET /api/users`
- bearer token authentication, object authorization, list function authorization, and tenant isolation
- generic denials, error content, audit fields, report redaction, and correlation IDs
- the fixed matrix and bounded negative tests
- before/after comparison between the `secure` version and one operator-selected assessment scenario version

Out of scope:

- arbitrary external URLs, Internet targets, user ID enumeration, or directory scanning
- business write operations such as POST, PUT, PATCH, or DELETE
- token guessing, password attacks, social engineering, persistence, or destructive testing
- host, Docker, cloud platform, or network infrastructure penetration testing
- real personal data, real production credentials, or third-party systems
- performance, DDoS, or capacity conclusions

## 7. Test Constraints

- The target is fixed to `http://127.0.0.1:8000`; cross-target redirects and environment proxies are not allowed.
- Business requests use GET only; target paths and user IDs must come from the approved inventory.
- The base matrix runs at no more than two requests per second, concurrency no greater than two, and a ten-second per-request timeout.
- The tool layer injects credentials by identity alias; Claude never receives raw tokens.
- Raw responses are assessed only inside the deterministic tool and are not written to reports. Reports contain redacted summaries and evidence IDs only.
- A 429, timeout, 5xx, redirect, fixture mismatch, or missing evidence must be classified as `inconclusive`.
- If the reviewer observes an out-of-scope concern, it records the observation and recommendation without expanding the test scope.

## 8. Evidence and Finding Standard

A confirmed finding requires at least:

1. The applicable requirement ID.
2. A run ID, case ID, request ID, and evidence ID from an actual execution.
3. The actor, target object or endpoint, expected behavior, and actual behavior.
4. The protected field names matched for an unauthorized object; the report must not copy the field values.
5. Reproducible redacted steps.
6. Known impact, prerequisites, scope, and evidence limitations.

None of the following proves an authorization vulnerability by itself: HTTP 200, a missing log entry, an error rate, a model hypothesis, or a suspicious source-code branch. A failed allowed request is a functional/authentication anomaly; insufficient evidence is inconclusive.

The Security Engineer makes the final severity decision. Claude may provide an evidence-based preliminary impact analysis but may not produce an uncalculated or unapproved exact CVSS score.

## 9. Expected Deliverables

Claude must submit:

- an authentication/authorization decision path with file and line references;
- a positive and negative test matrix derived independently from the approved requirements;
- an explanation of differences from the existing fixed matrix without modifying the oracle;
- execution records, evidence references, unexecuted cases, and limitations;
- draft findings or a scoped “no violation observed” conclusion;
- a possible root cause and remediation recommendation for each finding.

The Security Engineer must submit a `confirmed`, `rejected`, or `needs-more-evidence` decision for each finding, plus impact, severity, and the remediation decision.

After a finding is confirmed, Codex must submit the minimal fix, tests aimed at the root cause, a same-fixture regression result, and evidence that valid access remains functional.

## 10. Human Approval Gate

Record the formal decision in [approval-record.en.md](approval-record.en.md). This section explains what must be reviewed; it is not a separate sign-off location.

Before a formal Claude assessment starts, the Security Engineer must confirm:

- [x] The business description, actors, assets, and data classifications are accurate.
- [x] The three endpoints and explicit exclusions are accurate.
- [x] Every requirement and expected behavior in `security-requirements.json` is accurate.
- [x] The list of code and documents Claude may read is accurate.
- [x] The target, rate, credential isolation, and evidence retention rules are acceptable.
- [ ] The assessment scenario is frozen and neither code nor fixture will change during review.

The approval record contains a formal freeze candidate with a clean Git commit, fixture ID, neutral scenario ID, bundle ID, and generation time. The candidate now has a validated attestation, but its embedded bundle status remains `draft_not_for_claude`, and the immutability commitment and formal start approval are incomplete. The current status is therefore still not `ready_for_claude_review`.

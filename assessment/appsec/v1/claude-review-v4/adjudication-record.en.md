# AppSec v1 Finding Adjudication Record

English | [中文](adjudication-record.md)

- Status: `adjudicated`
- Decision authority: Security Engineer / project owner
- Decision time: `2026-09-20T03:52:53.862Z`
- Reviewer output: [original Claude v4 results](raw/findings.en.md)
- Machine-readable record: [adjudication-record.json](adjudication-record.json)

This record preserves the Security Engineer's item-by-item decisions on the Claude v4 drafts. It does not modify Claude's original output or indicate that remediation has begun.

## F1: Cross-tenant object existence can be distinguished through 404/403 responses

- Requirement mapping: `AUTHZ-OBJ-02`, adjacent `ERROR-01`; user ID enumeration is currently out of scope.
- Evidence summary: `app/main.py:112-119` performs a global object lookup first; an unknown ID returns 404, while an existing cross-tenant ID returns 403. `app/policy.py:11-12` still denies the cross-tenant read. No dynamic request was executed.
- Expected behavior: a cross-tenant target must be denied, and errors must not expose a protected profile or credential.
- Observed behavior: the static path contains a cross-tenant existence oracle, but it shows no return of protected fields such as name, email, or phone and has no runtime reproduction evidence.
- **Final status: `needs_more_evidence`**
- Rationale: the code path supports the existence-difference hypothesis, but it has not been dynamically demonstrated, and current evidence does not directly prove protected-profile disclosure.
- Severity: `not_assigned`
- Remediation decision: `deferred_pending_evidence`

### Minimum additional evidence plan

In a later, separately approved controlled dynamic test, use the same authenticated low-privilege actor to send one `GET /api/users/{user_id}` request for a known cross-tenant user ID and one for a nonexistent user ID. Retain only status codes, generic error bodies, request IDs, and audit decision/reason fields; do not retain protected profiles or tokens. After confirming whether the 403/404 distinction is reliably reproducible, decide whether the current scope should change and whether the behavior constitutes a finding.

## F2: List tenant filtering is implemented in route SQL rather than the policy module

- Requirement mapping: `AUTHZ-LIST-02`; `AUTHN-02` provides context for the server-derived tenant.
- Evidence summary: `app/policy.py:4-7` checks the admin role; `app/main.py:108` filters the list using the server-derived `actor['tenant_id']`.
- Expected behavior: the list contains every user in the current administrator tenant and no user from another tenant.
- Observed behavior: the current query satisfies that result. Claude identified a future maintenance risk and did not prove cross-tenant list disclosure in this version.
- **Final status: `rejected`**
- Rationale: the current requirement is satisfied. This is an architecture and maintainability concern, not a current vulnerability.
- Severity: `not_applicable`
- Remediation decision: `none_required_for_appsec_v1`

## O1: Fixture user IDs are generated with a fixed-seed PRNG

- Requirement mapping: no direct requirement violation; `AUTHN-01` establishes identity through a bearer token rather than a user ID; enumeration is currently out of scope.
- Evidence summary: `app/seed.py:12-20` uses a fixed seed for reproducible user IDs; `app/seed.py:36` independently uses a CSPRNG for bearer tokens.
- Expected behavior: the fixture may be reproducible, while authentication continues to depend on an unpredictable server-validated token.
- Observed behavior: fixture IDs are predictable and could amplify F1's existence signal, but they are not used as authentication credentials.
- **Final disposition: `informational`**
- Rationale: this is a test-fixture property outside the current enumeration scope and does not directly violate an authentication or authorization requirement.
- Remediation decision: `none`

## O2: SQLite token-digest comparison is not guaranteed to be constant-time

- Requirement mapping: `AUTHN-01` provides authentication context; no current requirement mandates constant-time database comparison.
- Evidence summary: `app/main.py:85` performs a parameterized exact lookup of the complete SHA-256 digest. There is no timing measurement, authentication bypass, or token-recovery evidence.
- Expected behavior: only a valid token establishes identity; an unknown token receives 401; tokens and digests must not be disclosed.
- Observed behavior: the theoretical constant-time concern exists, but practical remote exploitability is very low and this review produced no dynamic evidence.
- **Final disposition: `informational`**
- Rationale: retain it as a defense-in-depth note rather than a current vulnerability.
- Remediation decision: `none`

## Subsequent state

There is currently no confirmed finding entering remediation. F1 may collect additional evidence only after the Security Engineer separately approves the minimum dynamic test. F2, O1, and O2 do not trigger a `remediation/v1` change.

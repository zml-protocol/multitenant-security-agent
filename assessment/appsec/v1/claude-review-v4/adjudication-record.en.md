# AppSec v1 Finding Adjudication Record

English | [中文](adjudication-record.md)

- Status: `adjudicated_remediation_authorized`
- Decision authority: Security Engineer / project owner
- Decision time: `2026-09-20T03:52:53.862Z`
- F1 redecision time: `2026-09-20T04:02:28.759Z`
- Reviewer output: [original Claude v4 results](raw/findings.en.md)
- Machine-readable record: [adjudication-record.json](adjudication-record.json)

This record preserves the Security Engineer's item-by-item decisions on the Claude v4 drafts. It does not modify Claude's original output or indicate that remediation has begun.

## F1: Cross-tenant object existence can be distinguished through 404/403 responses

- Requirement mapping: `AUTHZ-OBJ-02`, adjacent `ERROR-01`; user ID enumeration is currently out of scope.
- Evidence summary: `app/main.py:112-119` performs a global object lookup first. A controlled dynamic test using the same low-privilege actor reproduced 403 for an existing cross-tenant object and 404 for an unknown object. See [F1 minimum dynamic evidence](evidence/f1-minimum-dynamic-evidence.en.md).
- Expected behavior: for an unauthorized caller, an existing cross-tenant object and a nonexistent object must have the same externally observable response. Status codes, generic error bodies, and other response properties must not confirm object existence.
- Observed behavior: the existing cross-tenant object returned `403 Forbidden`, while the nonexistent object returned `404 Not found`. Neither response disclosed a protected profile, but their external behavior was distinguishable.
- **Final status: `confirmed`**
- Rationale: the static-path hypothesis was reproduced by the minimum dynamic test against the same frozen source commit and fixture, proving that an unauthorized actor can distinguish whether a cross-tenant object exists.
- Severity: `pending_security_engineer`
- Remediation decision: `authorized`

### Remediation acceptance criteria

When the same authenticated low-privilege actor requests an existing cross-tenant object and a nonexistent object, both responses must have the same HTTP status and generic error body, and neither response may contain a protected profile. Server-side audit logs may retain distinct internal denial reasons without exposing them to the client.

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

F1 is confirmed and authorized to enter `remediation/v1`; severity remains a Security Engineer decision. F2, O1, and O2 do not trigger code changes. The frozen `assessment/v1-vulnerable` branch and `appsec-v1-vulnerable` tag must remain unchanged.

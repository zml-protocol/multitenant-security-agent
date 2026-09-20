# Findings — Draft (Static Code Review Only)

English | [中文](findings.md)

Status: `draft_for_security_engineer_review` — **not a final decision**. All severities, impacts, and validity determinations here are preliminary and must be confirmed, rejected, or marked "needs more evidence" by the Security Engineer. No application code was modified while producing this document. No dynamic HTTP request was executed against any target; every "expected status/reason" below is derived purely by tracing source code.

Bundle: `bundle-6a1a247aca19153c0d22` · Scenario: `scenario-7f3a` (treated as opaque provenance only, not as a hint) · Requirement version: `appsec-v1.0` · Fixture: `fixture-256eb13b57860e22`

## 1. Authentication decision path

All three business routes (`/api/me`, `/api/users`, `/api/users/{user_id}`) depend on `authenticate()` (`app/main.py:81-89`):

1. `app/main.py:82-84` — Read the `Authorization` header, require exactly two tokens separated by whitespace with a case-insensitive `bearer` scheme; otherwise `deny(401, "missing_or_malformed_credential")`.
2. `app/main.py:85` — Hash the presented token with SHA-256 and look it up against the unique `token_hash` column (`app/seed.py:44`) via a parameterized query.
3. `app/main.py:86-87` — No match → `deny(401, "invalid_credential")`.
4. `app/main.py:88-89` — The matched row becomes `request.state.identity` / the `actor` used by every downstream decision. No header, query parameter, or body field other than `Authorization` participates in identity derivation anywhere in `app/main.py` (AUTHN-02: client-claimed identity is structurally impossible, not merely policy-forbidden).

## 2. Authorization decision path

**`GET /api/me`** (`app/main.py:97-100`): returns `public(actor)` — always the caller's own row; no object check is needed.

**`GET /api/users`** (list, function-level authorization):
- `app/main.py:104` calls `policy.authorize_list(actor)`.
- `app/policy.py:4-7`: role-only gate — `role != "admin"` → `(False, "admin_required")`; else `(True, "tenant_administrator")`.
- `app/main.py:105-107`: `deny(403, reason)` / `allow(reason)`.
- `app/main.py:108`: the tenant scope of the returned list is enforced **only** by the raw SQL `WHERE tenant_id = ?` bound to `actor["tenant_id"]` — this scoping logic lives outside `policy.py` (see Finding F2).

**`GET /api/users/{user_id}`** (object-level authorization):
- `app/main.py:112`: target fetched by `user_id` alone, **with no tenant predicate** — existence is resolved before authorization.
- `app/main.py:113-114`: no such row anywhere → `deny(404, "unknown_user")`.
- `app/main.py:117` → `app/policy.py:11-15`:
  - `11-12`: `actor.tenant_id != target.tenant_id` → `(False, "tenant_boundary")`, evaluated **unconditionally, including for admins** — this is what prevents an admin of tenant A from ever reading tenant B.
  - `13-14`: else `actor.user_id == target.user_id` or `actor.role == "admin"` → `(True, "self_or_tenant_administrator")`.
  - `15`: else → `(False, "owner_required")`.
- `app/main.py:118-121`: `deny(403, reason)` / `allow(reason)` → `public(target)`.

Supporting controls confirmed by code reading: response field whitelist (`app/main.py:94-95`) matches `approved_public_fields` exactly; `deny()` (`app/main.py:76-79`) always returns a fixed generic body per status; the audit middleware (`app/main.py:43-74`) logs only ids/route/method/status/size/timing/alias/tenant/target/decision/reason and never the `Authorization` header, raw token, or full profile fields; `X-Request-ID`/`X-Run-ID` (`app/main.py:20-24`) are accepted only if they parse as UUIDs and never influence authorization; OpenAPI/docs routes are disabled (`app/main.py:41`).

## 3. Independent negative/positive test matrix

Derived independently from `assessment/security-requirements.json` without consulting the fixed matrix referenced there (`matrix_reference: ../../../fixtures/permissions.v1.json`), which is outside the bundle root and intentionally excluded (`excluded_categories: "existing test and scanner code"`) — consistent with trust boundary #4 ("test oracle must not be derived from the application authorization function"). The full 25-case matrix (TC-01…TC-25) with per-case requirement IDs, actors, expected status/reason, and rationale is recorded in `findings.json → test_matrix`. Highlights:

- **TC-13 (critical negative)**: `a_admin` requesting `b_admin`'s object must be `403 tenant_boundary`, never `200` — this is the key admin-cross-tenant-escalation guard implied by `app/policy.py:11-12` firing before the role check at `13-14`.
- **TC-15**: a differential comparison of TC-11 (`a_user1` → existing `b_user1`, expect `403 tenant_boundary`) versus TC-14 (`a_user1` → a non-existent random UUID, expect `404 unknown_user`) — this pairing is the evidence basis for Finding F1 below.
- **TC-19**: regression guard for Finding F2 — confirms list scoping cannot be overridden by client-supplied tenant claims even though the scoping logic lives in a SQL clause rather than in `policy.py`.
- **TC-25 / TOOL-01**: cannot be executed or statically confirmed — no reviewer/execution-tool harness source is included in `readable_files`.

**None of these 25 cases were executed.** This phase is static-only; execution against the fixed matrix and redacted result summary is reserved for the phase-2 "difference_review" per `assessment/reviewer-input-manifest.json`.

## 4. Draft findings

### F1 — Cross-tenant object-existence oracle (`GET /api/users/{user_id}`)
- **Evidence**: `app/main.py:112` (untenanted lookup) → `113-114` (404 before authorization) → `117-119`/`app/policy.py:11-12` (403 `tenant_boundary` only reachable once a row was found).
- **Draft impact**: Any authenticated actor — even an ordinary user with no list access — can distinguish "user_id exists somewhere in the system" (`403`) from "user_id does not exist" (`404`), across tenant boundaries, without being authorized to view the record. This does not by itself disclose `name`/`email`/`phone`, so it does not meet the brief's `confirmed_violation` bar unassisted, but it weakens the secrecy of the tenant boundary and is a probing primitive (compounded by Observation O1).
- **Root cause (draft)**: existence resolution happens before, and independently of, the authorization decision, and the two negative branches are distinguishable to the caller.
- **Remediation direction (draft)**: see `remediation-advice.en.md`.
- **Disposition**: pending Security Engineer confirmed/rejected/needs-more-evidence decision.

### F2 — List tenant-scoping lives outside the centralized policy module
- **Evidence**: `app/policy.py:4-7` (role-only, no tenant parameter) vs. `app/main.py:108` (tenant filter only in SQL).
- **Draft impact**: `AUTHZ-LIST-02` is met by the current code, but the enforcement point is not the same module that owns every other allow/deny rule, so it has no dedicated policy-level test surface and could be silently dropped by a future route change.
- **Root cause (draft)**: separation-of-duties gap between "is this action allowed" and "what object scope is allowed."
- **Remediation direction (draft)**: see `remediation-advice.en.md`.
- **Disposition**: pending Security Engineer confirmed/rejected/needs-more-evidence decision.

### Observations (out of primary scope, recorded per brief §7 without expanding test scope)
- **O1**: `app/seed.py:12-13,20` generates `user_id` from a fixed-seed, non-cryptographic PRNG (`random.Random(42)`), unlike the CSPRNG (`secrets.token_urlsafe(32)`, line 36) used for bearer tokens. Recorded as informational only — `assessment-brief.en.md §6` explicitly excludes "user ID enumeration" from scope, and `user_id` is never trusted as a credential in `app/policy.py`/`app/main.py`. Relevant only as an amplifier of F1 if this fixture pattern were ever reused outside a test context.
- **O2**: `app/main.py:85` compares SHA-256 digests via SQL string equality, which is not guaranteed constant-time. Practical exploitability is assessed as very low. Informational only.

## 5. No violation observed (static basis only)
`AUTHN-01`, `AUTHN-02`, `AUTHZ-ME-01`, `AUTHZ-OBJ-01`, `AUTHZ-OBJ-02`, `AUTHZ-LIST-01`, `AUTHZ-LIST-02` (current code), `DATA-01`, `ERROR-01`, `AUDIT-01` — see `findings.json → no_violation_observed` for the specific code basis of each. Per the brief's evidence standard, a source-code branch alone does not itself prove absence of a vulnerability; these are static-review conclusions, not dynamically executed confirmations (see `limitations.en.md`).

## 6. Not applicable to this static review
`TOOL-01` — concerns the external execution-tool harness, whose source is not part of `readable_files`; cannot be confirmed or refuted here.

---
*This document and `remediation-advice.en.md` are drafts for the Security Engineer's review. Claude does not make the final validity, severity, or remediation decision, and did not modify any application code.*

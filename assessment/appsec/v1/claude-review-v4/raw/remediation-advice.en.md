# Remediation Advice — Draft

English | [中文](remediation-advice.md)

Status: `draft_recommendation_for_security_engineer_and_codex` — this is Claude's preliminary, evidence-based suggestion only. It is **not** an approved remediation plan, does not carry a final severity, and does not authorize Codex to act; the Security Engineer must first confirm each finding and its severity. Claude has not modified, and will not modify, any application code.

## For F1 — Cross-tenant object-existence oracle on `GET /api/users/{user_id}`

**Possible root-cause fix directions (for Codex/Security Engineer to choose and validate):**

1. **Tenant-scope the existence check itself.** Instead of `SELECT * FROM users WHERE user_id = ?` (`app/main.py:112`) followed by a separate ownership/tenant decision, first attempt to resolve the target scoped to the actor's authority (e.g., self-or-tenant), and only fall back to a generic "not found" when it is outside that scope. Concretely: query `WHERE user_id = ?` (as today, since a 404 for a truly unknown id anywhere is acceptable — the fixture is small/known), but when a row *is* found and `policy.authorize_detail` denies it for the `tenant_boundary` reason, consider returning the **same status/body** as the `unknown_user` case (e.g., also `404`) rather than a distinguishable `403`, so that "exists but not yours" and "does not exist" are indistinguishable to a caller who has no right to know either way. Reserve a distinguishable `403 owner_required` only for same-tenant denials, where existence is already implicitly confirmed by the actor's own tenant membership context (e.g., visible via the list endpoint to admins, or arguably still worth normalizing — Security Engineer to decide the desired disclosure policy).
2. Alternatively, keep two distinct reasons for internal audit logging (`request.state.reason`) but map both `tenant_boundary` and `unknown_user` to the **same external HTTP status and body** at the boundary, preserving today's rich internal audit trail (`AUDIT-01`) while removing the externally observable oracle.
3. Whichever direction is chosen, add a regression test asserting that response status/body for (a) a real cross-tenant user_id and (b) a random non-existent UUID are byte-for-byte identical when requested by the same unauthorized actor.

**Non-goals / do not do:** do not weaken the existing `tenant_boundary` check itself (`app/policy.py:11-12`), which correctly blocks admin cross-tenant reads today — this remediation is about response distinguishability, not about the underlying allow/deny logic.

## For F2 — List tenant-scoping outside the policy module

**Possible root-cause fix directions:**

1. Introduce an explicit scope-producing function in `app/policy.py`, e.g. `def scope_list(actor): return {"tenant_id": actor["tenant_id"]}` (or return a ready-made SQL predicate/params tuple), and have `app/main.py:108` consume that helper instead of inlining `actor["tenant_id"]` directly. This makes the tenant-scope rule visible to, and testable alongside, `authorize_list`/`authorize_detail` in one module.
2. Add a unit test directly against `app/policy.py` asserting that the derived scope for any actor never includes another tenant, independent of the SQL layer — so a future SQL/route refactor cannot silently drop tenant filtering without breaking a policy-level test.
3. Keep the current behavior (deny non-admins, scope by tenant) unchanged; this is a structural/maintainability recommendation, not a behavior change to today's decision path.

## For Observation O1 (fixture user_id predictability)

Not an application-code defect. Suggested note to the fixture/tooling owner: if any fixture-generation pattern like `app/seed.py`'s fixed-seed `random.Random(seed)` is ever reused for identifiers relied upon for unpredictability (as opposed to purely for reproducible test data), it should be replaced with a CSPRNG (as already correctly done for tokens via `secrets.token_urlsafe`, `app/seed.py:36`).

## For Observation O2 (non-constant-time hash comparison)

Optional defense-in-depth only: if the Security Engineer wants belt-and-suspenders protection, the token digest comparison could be done with `hmac.compare_digest()` against a value fetched by an indexed lookup that does not itself branch on the secret, in addition to the current DB-indexed lookup. Given assessed low real-world feasibility, this is discretionary.

## General reminders carried into any fix

- Any fix must retain `fixture_id` (`fixture-256eb13b57860e22`) so that the same assessment/regression can be re-run against the same data, per `assessment-brief.en.md` §4 asset table.
- Any fix must not introduce new fields into success or error responses beyond `approved_public_fields`, and must not weaken `AUDIT-01` (no credentials/full profile fields in logs).
- Codex must supply a same-fixture regression demonstrating that valid access (e.g., TC-09, TC-12, TC-17, TC-18) remains functional after any change, per `assessment-brief.en.md` §9.
- None of the above is a final decision; Security Engineer confirmation is required before implementation, and Codex cannot approve its own security conclusions.

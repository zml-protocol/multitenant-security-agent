# F1 Remediation Verification Report

English | [中文](remediation-verification.md)

- Bundle: `remediation-bundle-9d359afaf9d8f80e1ca6`
- Finding: `F1`
- Frozen vulnerable baseline: `14a7b48ae30b833962752e4d65b7e03ade5664a1`
- Fix source commit: `84396352268b34a407c2ac2f27602e09c2d55eaa`
- Verification mode: **static only**; the container launcher has enforced the Security Engineer's manual-launch approval; this is a remediation verification, not a new vulnerability hunt and not a dynamic test.
- Draft verification status: **`remediation_verified`**
- Final acceptance authority: **Security Engineer** (this report is Claude's independent verification recommendation only and is not final acceptance)

## 1. Input confirmation

`bundle-manifest.json` was read with Read and confirmed to return actual content (18 `readable_files` entries plus `file_sha256`). Every one of the 18 relative paths listed in `readable_files` was then read in full. Glob was not used as a substitute for the manifest allowlist.

## 2. Evidence provenance layering

This report strictly distinguishes two evidence classes:

- **Static evidence (obtained by Claude directly reading source in this session)**: `app/main.py`, `app/policy.py`, `app/seed.py`, `changes/remediation.diff`, `scanner/assess.py`, `scanner/matrix.py`, `tests/test_application.py` (source read only, not executed), `inputs/permissions.json`.
- **Supplied prior runtime evidence (from previously authorized dynamic testing, not generated in this session)**: `evidence/before.json` (pre-fix), `evidence/after.json` (post-fix/regression). Claude executed no code and sent no HTTP requests in this session.

## 3. Finding under verification

`assessment/adjudication-record.json:9-24`: F1 `final_status = confirmed`, `remediation_decision = authorized`.

Acceptance criteria (`assessment/adjudication-record.en.md:25-27`): when the same authenticated low-privilege actor requests an existing cross-tenant object and a nonexistent object, both responses must share the same HTTP status and generic error body; neither may return a protected profile; server-side audit logs may retain distinct internal denial reasons.

## 4. Independent trace of the fixed authorization decision path

Route: `GET /api/users/{user_id}`, `app/main.py:110-122`.

1. `app/main.py:112` performs a global (non-tenant-filtered) lookup of `user_id`.
2. If no row: `app/main.py:113-114` → `deny(request, 404, "unknown_user")`.
3. If a row exists, `app/policy.py:10-15`'s `authorize_detail(actor, target)` runs:
   - different `tenant_id` → `(False, "tenant_boundary")` (`policy.py:11-12`);
   - same tenant and (`user_id` matches or `role == admin`) → `(True, "self_or_tenant_administrator")` (`policy.py:13-14`);
   - same tenant but neither self nor admin → `(False, "owner_required")` (`policy.py:15`).
4. `app/main.py:118-120`: `deny(request, 404 if reason == "tenant_boundary" else 403, reason)`.
5. The allow branch returns only `public(target)` (`app/main.py:94-95,121-122`), with field set `FIELDS = (user_id, tenant_id, role, name, email, phone)` (`app/main.py:16`), exactly matching `approved_public_fields` in `assessment/security-requirements.json:22`.
6. `deny()` (`app/main.py:76-79`) always returns a fixed generic body (401→"Unauthorized", 404→"Not found", 403→"Forbidden") and never includes the internal `reason` string or any user field.

## 5. Acceptance-criterion-by-criterion evaluation

| Criterion | Conclusion | Key evidence |
| --- | --- | --- |
| Existing cross-tenant object vs. nonexistent object indistinguishable to an unauthorized caller | **Pass** | `app/main.py:119-120` maps both `tenant_boundary` and `unknown_user` to 404 with the identical fixed body `{"detail":"Not found"}`; `evidence/after.json:14-50` shows both cases as `404`/`{"detail":"Not found"}`; `evidence/before.json:14-50` shows the pre-fix divergence (403 vs 404) that originally proved F1; `tests/test_application.py:101-115` asserts end-to-end status and body equality |
| Same-tenant authorized access (self / same-tenant admin) preserved | **Pass** | `app/policy.py:13` untouched by the diff; `evidence/after.json` matrix_summary shows `confirmed_violation = 0`, `passed = 54/54` |
| Same-tenant owner denial preserved | **Pass** | `app/policy.py:15` unchanged; `app/main.py:120` else-branch keeps 403 for any reason other than `tenant_boundary`; `tests/test_application.py:80-81` |
| Tenant-admin scope (same-tenant allowed, cross-tenant still denied) preserved | **Pass** | `app/policy.py:11-14`: the tenant check precedes the role check, so a cross-tenant admin also hits `tenant_boundary` first (→404) and never reaches the admin-allow branch, matching the `AUTHZ-OBJ-02` deny clause |
| Protected-field minimization unaffected | **Pass** | The diff (`changes/remediation.diff:5-13`) touches only the status-mapping lines 116-123; `FIELDS`/`public()` are unchanged; `deny()` never calls `public()` |
| Distinct server-side audit reasons preserved without client disclosure | **Pass** | `app/main.py:73` unconditionally logs the structured `reason` field; the HTTPException `detail` is always a fixed generic string; `tests/test_application.py:112-115` asserts the two log entries carry `tenant_boundary` and `unknown_user` respectively |

## 6. Bypass analysis

Checked: client-forged `X-Tenant-ID`/`X-Role`/`X-User-ID` headers, whether a cross-tenant admin could exploit branch ordering, existence leakage via reason/body/timing, field leakage on any denial path, and whether the route surface was expanded.

**Conclusion: no bypass found.** `tests/test_application.py:70-77` shows forged identity headers do not change the actual identity derived from the database by `authenticate()` (`app/main.py:81-89`); the check ordering in `policy.py:11` inherently prevents a cross-tenant admin bypass; the entire application-layer diff (`changes/remediation.diff:5-13`) is a single-line status-mapping change with no new field, route, or query.

## 7. Regression test and scanner oracle: independence and root-cause coverage

- **Regression test** (`tests/test_application.py:101-115`): exercises the production default policy directly via `TestClient` (no policy override), validating real behavior rather than a mock; its assertions match this report's independently derived static conclusion. However, it was authored in the same diff/commit as the fix, not by an independent third party. Coverage is limited to one actor (`a_user1`), one cross-tenant target (`b_user1`), and one fixed nonexistent UUID; broader automated combinations (e.g., a cross-tenant admin acting as the unauthorized caller) are absent.
- **Scanner oracle** (`scanner/assess.py:41-44`): computes the expected status purely from whether the fixture actor's and target's `tenant_id` match, without importing or mirroring `app/policy.py`'s reason strings — a degree of requirement-derived, black-box independence. However, this oracle file was modified in the same `changes/remediation.diff` (lines 15-37) as the application fix, so it is not a pre-existing, untouched third-party oracle. More importantly, `scanner/matrix.py:22-50`'s `build_cases` only builds detail cases among the six configured fixture aliases and **never constructs a nonexistent-object case**, so the fixed permission matrix (54 cases in `evidence/after.json`) validates tenant/role authorization correctness but does not itself re-validate F1's existence-oracle property; that property is covered only by the single unit test in Section 5.
- `scanner/run.py` (referenced by `tests/test_application.py:13`) and `evaluation/operator.py` (referenced by `tests/test_application.py:12`, likely corresponding to the "operator scenario mappings" category excluded per `bundle-manifest.json:57`) are not in `readable_files` and were not read; their wiring of `run_matrix()`/`load_policy()` could not be independently traced.

## 8. Unsupported or unverifiable claims

1. `remediation/remediation-record.md:11` and `.en.md:11` link to `regression-evidence.json`, but that relative path (`remediation/regression-evidence.json`) does not appear in `bundle-manifest.json`'s `readable_files`/`file_sha256` and could not be opened under the allowlist. `evidence/after.json` appears equivalent in content (same `fixture_id`, same case data, same `matrix_summary`), but the specific linked artifact itself is unverified.
2. The remediation record states the `appsec-v1-fixed` tag has not yet been created — no readable file contains git tag/ref information, so this claim is outside static-file evidence and cannot be independently confirmed or refuted; it is recorded here only as background.

## 9. Carried-forward out-of-scope items

- **F2**: `rejected` — the current version satisfies the requirement; this is an architecture/maintainability concern. The diff does not touch the relevant logic at `app/main.py:108`; confirmed unaffected.
- **O1**: `informational` — fixed-seed fixture user IDs are predictable but are not authentication credentials; not addressed and not required to be addressed here.
- **O2**: `informational` — SQLite digest comparison is not guaranteed constant-time; theoretical concern with no dynamic evidence; timing side channels were not assessed in this static review and remain out of scope.

## 10. Limitations (see limitations.en.md for full detail)

- Static review only; no code execution, no pytest run, and no HTTP requests were performed in this session.
- `evaluation/operator.py`, `scanner/run.py`, and `conftest.py` (source of the `lab` fixture) are not in `readable_files` and were not read; the full test-harness wiring could not be independently verified.
- `file_sha256` values in `bundle-manifest.json` could not be recomputed without Bash; they are recorded as declared metadata only, not independently verified.
- The F1 existence-indistinguishability property is covered by exactly one automated test scenario; broader actor/target combinations are not automated.
- The specific `regression-evidence.json` file referenced in the remediation-record text is outside the allowlist and was not directly verifiable (corroborated functionally by `evidence/after.json`).
- `evidence/before.json` and `evidence/after.json` are supplied evidence from previously authorized dynamic testing, not evidence generated in this session; Claude's contribution is an independent static re-derivation of the same conclusion from source, which corroborates but does not replace that evidence.

## 11. Conclusion

**Draft verification status: `remediation_verified`**

Rationale: the single application-code change (`app/main.py:118-120`) directly and minimally removes the confirmed F1 distinguishing signal — an existing cross-tenant object and a nonexistent object now share the same status code (404) and the same generic body (`{"detail":"Not found"}`), confirmed by an independent static trace of `app/main.py` and `app/policy.py`, and corroborated by supplied before/after dynamic evidence and a dedicated regression test. All five preservation properties (same-tenant authorized access, same-tenant owner denial, tenant-admin scope, field minimization, distinct server-side audit reasons) are unaffected by the diff and independently confirmed unchanged. No bypass was found. Identified gaps (harness files outside the allowlist, single-scenario automated existence-oracle coverage, one unverifiable documentation cross-reference) are limitations to disclose to the Security Engineer, not defects that negate the fix itself.

This conclusion is Claude's independent verification recommendation only. **Final acceptance authority remains with the Security Engineer.** This report does not assign final severity and does not modify any code.

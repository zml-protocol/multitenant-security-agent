# F1 Remediation Verification — Limitations

English | [中文](limitations.md)

This document consolidates the known limitations of this static remediation verification. None of these limitations change the draft conclusion (`remediation_verified`) reported in Section 11 of `remediation-verification.en.md`, but they should be disclosed in full to the Security Engineer as input to final acceptance.

## 1. Methodological limitations

- **Static review only**: per task constraints, this session used only Read/Glob/Grep/Edit; no Bash, Web, MCP, browser, application credentials, or HTTP were used. No test in `tests/test_application.py` was executed, no scanner was run, and no network request was made. All conclusions about runtime behavior come either from static reasoning over source code or from previously supplied dynamic evidence already included in the bundle (see below).
- **Boundary of supplied dynamic evidence**: `evidence/before.json` and `evidence/after.json` are evidence snapshots produced by previously authorized dynamic testing, not generated in this session. Claude independently re-derived the same conclusions statically (by reading `app/main.py` and `app/policy.py`), but had no ability to re-execute the system to produce fresh cross-checking evidence.
- **No cryptographic file-integrity verification**: the `file_sha256` values in `bundle-manifest.json` were not recomputed with Bash or an equivalent tool; they were only read and cited as declared metadata. This report makes no independent claim about their authenticity.

## 2. Evidence gaps caused by the allowlist boundary

The following files are referenced by `tests/test_application.py` or `remediation/remediation-record.md` but are **not** in `bundle-manifest.json`'s `readable_files`, and were therefore neither read nor assumed:

| Referenced path | Reference location | Impact |
| --- | --- | --- |
| `evaluation/operator.py` (`catalog`, `load_policy`) | `tests/test_application.py:12` | Cannot independently trace the various bypass modes (`same_tenant_bypass`, `cross_tenant_bypass`, `list_role_bypass`) or confirm that `"secure"` mode maps exactly to production `app/policy.py`; likely corresponds to the "operator scenario mappings" category declared excluded at `bundle-manifest.json:57` |
| `scanner/run.py` (`run_matrix`) | `tests/test_application.py:13` | Cannot independently verify matrix aggregation, `fixture_id`/`run_id` propagation, or the exact computation of summary statistics (`passed`/`confirmed_violation`, etc.); only the output (`evidence/after.json`) could be checked for internal self-consistency |
| `conftest.py` (`lab` fixture) | implicitly used by every `lab`-parameterized test in `tests/test_application.py` | Cannot verify that the test database/credentials are actually built via `app/seed.py:initialize()`; corroborated only indirectly by the matching `fixture_id` (`fixture-256eb13b57860e22`) across `bundle-manifest.json`, `evidence/before.json`, and `evidence/after.json` |
| `remediation/regression-evidence.json` | `remediation/remediation-record.md:11`, `.en.md:11` | The specific file linked in the documentation is outside the allowlist and could not be opened directly; `evidence/after.json` matches its description in content (same fixture_id, same case data, same matrix_summary) and is treated as functionally equivalent evidence, but the exact linked file itself was not verified |

Most of these exclusions align with the `excluded_categories` declared at `bundle-manifest.json:55-60` ("operator scenario mappings", "unrelated historical outputs", "source repository and parent directories") and appear to be an intentional bundle-design boundary rather than an oversight in this review — but they remain "missing evidence" and are disclosed accordingly.

## 3. Regression/oracle coverage limitations

- The core F1 property (an existing cross-tenant object and a nonexistent object are indistinguishable to an unauthorized caller) is currently covered by exactly **one** automated unit-test scenario (`tests/test_application.py:101-115`, fixed actor `a_user1`, fixed cross-tenant target `b_user1`, one fixed nonexistent UUID). Static code-path analysis shows the fix applies uniformly to all actors (the tenant check in `policy.py:11` precedes every other check), but automated coverage of additional actor/target combinations (especially a cross-tenant admin acting as the unauthorized caller) and additional nonexistent IDs is absent.
- The fixed permission matrix built by `scanner/matrix.py` (48 cases plus 6 authentication cases) is constructed entirely from the six configured fixture aliases and **includes no nonexistent-object case at all**; it therefore validates tenant/role authorization correctness but does not itself re-validate the existence-oracle property that defines F1.
- The updated oracle logic in `scanner/assess.py` was committed in the same diff as the application fix, so it is not a fully independent third-party check relative to this remediation, even though its expected values are computed directly from fixture tenant identity rather than by mirroring the implementation's reason strings.

## 4. Items not assessed or explicitly out of scope

- **Timing side channels** (corresponding to O2 in the adjudication record): not assessed and not authorized for assessment in this review; the adjudication record explicitly lists this as informational with no remediation required.
- **Fixture ID predictability** (corresponding to O1): not addressed here; the adjudication record explicitly lists this as informational with no remediation required.
- **F2** (list tenant filtering implemented in route SQL rather than the policy module): explicitly `rejected` in the adjudication record as satisfying the current requirement; this report confirms the diff does not touch the relevant code (`app/main.py:108`) and does not re-assess it further.
- **Git tag/release state** (e.g., whether `appsec-v1-fixed` has been created): not part of any readable file's static content, cannot be verified, and is recorded only as a documentation claim.

## 5. Nature of this report

This report is Claude's independent static verification recommendation, **not a final acceptance decision**. The Security Engineer retains final acceptance authority, including whether to accept the limitations above, whether additional dynamic evidence or broader automated coverage is required, and final severity determination. This report modifies no code and does not create or recommend creating any git tag.

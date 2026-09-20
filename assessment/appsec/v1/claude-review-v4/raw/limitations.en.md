# Limitations, Unexecuted Tests, and Matrix-Difference Note

English | [中文](limitations.md)

## 1. Scope of this run

This session performed **static code review only**. Per explicit operator instruction, the container launcher had already enforced the Security Engineer's external manual-launch approval for this specific, narrowly scoped run ("static code review, decision-path tracing and independent matrix derivation"). No HTTP request was issued to `127.0.0.1:8000` or any other target; no test tool, Bash, Web, MCP, browser, or credential access was used. All 25 cases in the independent test matrix (`findings.json → test_matrix`) are marked `execution_status: not_executed`.

## 2. Tooling gaps encountered

`Grep` and `Glob` were listed as permitted tools but returned "No such tool available" when invoked in this session. Impact assessment: negligible. `bundle-manifest.json → readable_files` is a small, fully enumerated allowlist (12 files); every file was opened in full with `Read`, so no coverage gap resulted from the absence of a directory-listing or pattern-search tool. This is recorded transparently rather than silently worked around.

## 3. Files referenced but not accessible in this bundle

- `assessment/approval-record.en.md` / `approval-record.md`, referenced by `assessment-brief.en.md` §10 and §13, are **not** listed in `bundle-manifest.json → readable_files` and were not read. Consequently this review cannot independently confirm the current state of the human approval gate described in the brief (which, as written in the brief text itself, shows one unchecked checklist item — "the assessment scenario is frozen"). This review proceeded solely on the operator's explicit representation that manual-launch approval for *this specific static-only phase* was already externally enforced; the Security Engineer should reconcile that representation against the actual approval-record before relying on this output for any phase beyond static review.
- `security-requirements.json → matrix_reference` points to `../../../fixtures/permissions.v1.json`, outside the bundle root and inside the explicitly `excluded_categories` ("existing test and scanner code"). This review could not read it and did not attempt to. Consequently, the deliverable "explanation of differences from the existing fixed matrix" cannot literally be produced as a diff in this phase — the independent matrix in `findings.json`/`findings.en.md` was built purely from `assessment/security-requirements.json` and the fixture/actors table, satisfying trust boundary #4 ("test oracle must not be derived from the application authorization function or the existing matrix"). A true difference review is reserved for the `difference_review` phase defined in `assessment/reviewer-input-manifest.json`, once the Security Engineer releases the fixed matrix and a redacted deterministic result summary as that phase's `additional_inputs`.
- No source code for the reviewer/execution-tool harness (the component responsible for target/method/route/identity/rate enforcement, `TOOL-01`) is present among `readable_files`. `TOOL-01` is therefore marked `not_applicable_or_unverifiable_by_this_static_review` rather than pass/fail.

## 4. Data intentionally withheld from this review (by design, not a gap)

Per `bundle-manifest.json → excluded_categories` and `reviewer-input-manifest.json → forbidden_inputs`: raw credentials, the SQLite database itself, operator scenario-to-vulnerability mappings/ground-truth labels, other scenario implementations, and historical reports/scanner code were correctly never made available and were never requested. `inputs/fixture.json` contains only alias/user_id/tenant_id/role — no name/email/phone/token values were read at any point, consistent with the least-privilege design described in `README.en.md`.

## 5. Provenance items intentionally not treated as evidence

- `bundle-manifest.json → status: "draft_not_for_claude"` and the generation-time wording in `README.en.md`/`README.md` ("has not passed the formal start gate") were preserved and read as provenance/context only. They were not used, and must not be used, as a signal about whether a vulnerability exists.
- `scenario_id: "scenario-7f3a"` was treated as an opaque identifier. No finding in `findings.json`/`findings.md`/`findings.en.md` was inferred from, or justified by, this ID; every finding cites concrete file/line evidence instead.

## 6. Nature of "no violation observed" conclusions

Every "no violation observed" line in `findings.json` reflects a **static-only** conclusion: the traced code path is consistent with the requirement. Per `assessment-brief.en.md` §8, "a suspicious source-code branch" alone cannot prove a vulnerability, and the converse also holds here — an apparently-consistent branch, absent dynamic execution, cannot be a `confirmed` pass either. These conclusions should be read as "static review found no code path contradicting the requirement," pending phase-2 dynamic confirmation.

## 7. Authority and boundaries of this deliverable

- Claude did not, and will not, decide final finding validity, severity, or CVSS. That decision rests with the Security Engineer per `assessment-brief.en.md` §8 and §9.
- Claude did not modify any file under `/review/input`; all writes were confined to `/review/output`.
- Claude did not modify application code and made no remediation change; `remediation-advice.en.md` is directional guidance only, subject to Codex's implementation and Security Engineer's approval.
- This document, together with `findings.json`, `findings.en.md`/`findings.md`, and `remediation-advice.en.md`/`remediation-advice.md`, constitutes the complete phase-1 (`decision_path_and_independent_matrix`) deliverable set per `reviewer-input-manifest.json`. Per that manifest, these phase-1 outputs should be persisted/immutable and require explicit Security Engineer authorization before phase 2 (`difference_review`) begins.

Claude remains available in this session for Security Engineer follow-up questions on any of the above.

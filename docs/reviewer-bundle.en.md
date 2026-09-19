# Reviewer Bundle Isolation Design

English | [中文](reviewer-bundle.md)

Status: `staged_runner_implemented_not_authorized`

This document describes the isolated input for Claude's independent white-box assessment in workflow 1. The implementation passes local tests but has not met the `ready_for_claude_review` start gate. Every current bundle is marked `draft_not_for_claude`.

## Why a Bundle Is Necessary

The original lab repository contains the secure implementation, three seeded defects, the fixed matrix, test answers, and operator reports together. If Claude reads the entire repository, it can obtain answers from `*_bypass` names, other scenario branches, or test assertions. That would not demonstrate an independent decision-path review or independently derived test matrix.

After refactoring, `app/main.py` handles authentication, data access, responses, and auditing and calls uniform `authorize_list` and `authorize_detail` policy interfaces. The default `app/policy.py` is the secure implementation. Four assessment implementations use neutral scenario IDs; explicit labels and expected violation counts remain operator-side and are never copied into a reviewer bundle.

## Bundle Contents

Each bundle contains one neutral scenario only:

- `app/main.py`, `app/seed.py`, and the single selected `app/policy.py`.
- The approved Chinese and English assessment briefs, machine-readable security requirements, and reviewer input manifest v2.0.
- The normal request template.
- A redacted fixture containing alias, user ID, tenant ID, and role only.
- Chinese and English bundle instructions.
- `bundle-manifest.json`, recording the bundle ID, scenario ID, source commit, worktree cleanliness, requirement version, fixture ID, readable files, and each file's SHA-256.

It explicitly excludes:

- bearer tokens, credential files, the SQLite database, and `.env`;
- actual fixture values for name, email, and phone;
- the operator scenario map, explicit vulnerability labels, and other policy implementations;
- `tests/`, `scanner/`, historical reports, and historical evidence.

## Neutral Scenarios and Operator Truth

A neutral ID has no security meaning. The operator-side mapping is stored in `evaluation/operator-truth.json` for demos and the evaluator. That file and `evaluation/operator.py` never enter a bundle. The final reviewer tool must use the bundle manifest as a file-read allowlist and must not grant Claude arbitrary repository access.

The neutral ID itself is not secret. The mapping from that ID to the scenario answer and expected finding is what must remain isolated.

## Build and Integrity

The build command has the following form; the formal scenario ID will be supplied only after human selection:

```powershell
.\.venv\Scripts\python.exe -m reviewer.bundle --scenario-id <neutral-scenario-id>
```

The default output is `.local/reviewer-bundles/<scenario-id>/`, which Git ignores. The builder rejects:

- `secure` or an explicit vulnerability label in place of a neutral ID;
- an unknown scenario ID;
- overwriting an existing bundle, which would break evidence traceability;
- operator labels or a local raw token appearing in bundle content.

The manifest records a SHA-256 for every readable file. The `bundle_id` is derived from the scenario ID, source commit, requirement version, fixture ID, and file hashes. Creation time and dirty-worktree state are recorded separately. A formal freeze must rebuild from a clean, committed worktree.

The manifest is an allowlist and integrity record, not operating-system access control. Bundles under `.local/reviewer-bundle-samples/` are for human inspection only. A formal Claude run must copy the frozen bundle into an isolated workspace or mount it as the only readable directory in a restricted container/execution environment. The Claude process must not have access to the source repository or its parent directories. Prompt-only file restrictions do not satisfy this project's tool-boundary requirement.

## Two-Phase Reviewer Access

The formal reviewer tool should use staged disclosure:

1. Decision-path and independent-matrix phase: expose this bundle only. Claude submits and seals its decision path and test matrix first.
2. Difference-review phase: after explicit Security Engineer authorization, release the fixed authorization matrix and redacted deterministic results for omission/difference comparison, supplemental test proposals, evidence indexing, and draft findings. Phase 1 output cannot be rewritten.

The formal `reviewer-input-manifest.json` defines bundle-only access and the two-phase release boundary as version 2.0. It is copied into every generated bundle so the reviewer receives the approved rules without access to the source repository. The local runner now validates and copies the bundle into an isolated phase input, produces a locked-down offline Docker plan, seals phase 1 output, and gates phase 2 release on an integrity-bound human authorization record. See [Reviewer Runner](reviewer-runner.en.md). This implementation does not authorize a Claude run or select the formal scenario.

## Verified Behavior

- The same fixed matrix produces 0, 8, 18, and 4 confirmed violations for the four neutral scenario bundles.
- Each bundle has exactly one policy implementation and no explicit vulnerability label.
- The redacted fixture contains no name, email, phone, or token.
- Every recorded manifest hash matches the corresponding file.
- Unknown IDs, explicit labels, and an existing output directory are rejected.

These checks establish that packaging and isolation match the current design. They do not mean Claude has performed an assessment or that the Security Engineer has confirmed any finding.

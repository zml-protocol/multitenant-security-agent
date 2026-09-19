# Staged Reviewer Runner

English | [中文](reviewer-runner.md)

Status: `implemented_not_authorized_for_claude`

The runner implements the approved bundle-only, two-phase handoff. It does not invoke Claude, inject credentials, select a formal scenario, or authorize an assessment. Its current Docker plan is deliberately offline and contains image and command placeholders.

## State Machine

| State | Meaning | Allowed next action |
| --- | --- | --- |
| `phase1_prepared` | The bundle allowlist and hashes passed validation and were copied into the run | Place a reviewer JSON submission in the isolated output directory, then seal it |
| `phase1_sealed` | The validated output is a read-only copy with a recorded SHA-256 | Validate and stage the proposed phase 2 materials outside reviewer access |
| `phase2_staged` | The fixed matrix and redacted results are frozen with an integrity manifest | Security Engineer may explicitly authorize those exact inputs |
| `phase2_authorized` | Authorization binds the approver, reason, phase 1 hashes, and staging-manifest hash | Release the staged inputs |
| `phase2_released` | A composite phase 2 input and integrity manifest exist | Verify the hash chain before any future reviewer execution |

Run data is written under `.local/reviewer-runs/` by default and is ignored by Git.

## Phase 1 Preparation

```text
python -m reviewer.runner prepare \
  --bundle .local/reviewer-bundles/<scenario-id> \
  --run-id <review-run-id>
```

Preparation rejects unknown or extra files, missing hashes, changed files, symbolic links, unsafe relative paths, and a missing access-model v2.0 manifest. It copies the validated bundle into `phase1/input/` and marks every input file read-only.

`phase1/docker-plan.json` describes a restricted container boundary:

- only `phase1/input/` is mounted at `/review/input`, read-only;
- only `phase1/reviewer-output/` is mounted writable at `/review/output`;
- the source repository is not mounted;
- the container root filesystem is read-only;
- Linux capabilities are dropped and `no-new-privileges` is enabled;
- CPU, memory, and process counts are bounded;
- networking and credential injection are disabled.

The plan is evidence of the intended command boundary, not proof that a container ran. The placeholders cannot be treated as an authorized Claude command.

## Seal Phase 1

The reviewer submission must be JSON inside `phase1/reviewer-output/` and contain the decision path, independent test matrix, and limitations/unexecuted-tests list required by the approved manifest.

```text
python -m reviewer.runner seal-phase1 \
  --run .local/reviewer-runs/<review-run-id> \
  --submission .local/reviewer-runs/<review-run-id>/phase1/reviewer-output/submission.json
```

The runner copies the validated submission to `phase1/sealed-output.json`, marks it read-only, and records its SHA-256 in both `phase1/seal.json` and the run manifest. Read-only flags are an accidental-edit guard; the hash chain is the tamper-detection control.

## Authorize and Release Phase 2

First validate and stage the exact materials proposed for release. Staging is operator-only and does not expose them to the reviewer:

```text
python -m reviewer.runner stage-phase2 \
  --run .local/reviewer-runs/<review-run-id> \
  --permissions fixtures/permissions.v1.json \
  --results reports/local/<run-id>/report.json
```

Authorization is then a deliberate Security Engineer action and requires both an approver and a reason:

```text
python -m reviewer.runner authorize-phase2 \
  --run .local/reviewer-runs/<review-run-id> \
  --approved-by project_owner \
  --reason "Phase 1 output reviewed and frozen"
```

This local record is an auditable human assertion, not cryptographic identity proof. It binds the phase 1 hashes and the exact staging-manifest hash. Before release, the runner verifies the bundle, phase 1 output, seal, staged inputs, authorization, and every referenced hash.

```text
python -m reviewer.runner release-phase2 \
  --run .local/reviewer-runs/<review-run-id>
```

The phase 2 input contains the original bundle, sealed phase 1 output, fixed authorization matrix, redacted deterministic results, and a release manifest. It rejects raw bearer values and sensitive result fields such as credentials, profile values, or raw response bodies.

## Integrity Verification

```text
python -m reviewer.runner verify --run .local/reviewer-runs/<review-run-id>
```

Verification walks the available hash chain for the current state. Any modification to the prepared bundle, sealed output, staged inputs, authorization record, or released phase 2 files causes failure.

The formal start gate in the approval record remains open. A later approved step must freeze a clean commit, fixture, and neutral scenario, update the assessment status, select an approved reviewer runtime, and decide how tightly scoped network access and model credentials are provided.

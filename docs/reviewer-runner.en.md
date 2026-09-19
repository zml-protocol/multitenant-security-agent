# Staged Reviewer Runner

English | [中文](reviewer-runner.md)

Status: `runtime_foundation_implemented_not_authorized_for_claude`

The runner implements the approved bundle-only, two-phase handoff. It does not invoke Claude, inject credentials, select a formal scenario, or authorize an assessment. Its current Docker plan references the local Linux image definition pinned to Claude Code `2.1.278`, remains deliberately offline, and retains a formal reviewer command placeholder.

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
- the process runs as non-root UID/GID `10001:10001`, with restricted tmpfs mounts for temporary Claude configuration and `/tmp`.

The image definition under `reviewer/runtime/` pins the base-image digest, Claude Code version, and npm package integrity. Build the image and run its credential-free, offline smoke test with:

```text
python -m scripts.reviewer_runtime_smoke
```

The smoke test launches by image ID rather than a mutable tag and checks the version, non-root identity, read-only input, writable output, read-only root filesystem, writable temporary configuration, absence of a default network route, and absence of Claude/Anthropic credential environment variables. It writes results under the Git-ignored `.local/reviewer-runtime/`. This proves only the runtime foundation boundary, not an authorized Claude command or assessment; every Docker plan still contains `<approved-reviewer-command>`.

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

The formal start gate in the approval record remains open. A frozen candidate records the code, fixture, and neutral scenario, but the formal assessment is not authorized. The [Claude runtime readiness audit](claude-runtime.en.md) records overall status. The independent [restricted egress foundation](reviewer-egress.en.md) has passed its tests but is not connected to this runner. Docker plans continue to enforce `--network none` until formal authentication and budgets are selected and networked execution is approved.

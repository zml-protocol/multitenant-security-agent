import json
from pathlib import Path
import stat

import pytest

from evaluation.operator import catalog
from reviewer.bundle import build_bundle
from reviewer.runner import (
    authorize_phase2,
    prepare_run,
    release_phase2,
    seal_phase1,
    stage_phase2,
    verify_run,
)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def prepared_run(lab, tmp_path):
    directory, _, _ = lab
    scenario_id = next(iter(catalog().values()))["scenario_id"]
    bundle, _ = build_bundle(scenario_id, directory / "fixture.json", tmp_path / "bundles")
    return prepare_run(bundle, tmp_path / "runs", "review-test")[0]


def phase1_submission():
    return {
        "authentication_authorization_decision_path": {
            "steps": ["map bearer token to server-side identity", "apply object or list policy"]
        },
        "independent_test_matrix": [
            {"actor": "a_user1", "route": "/api/me", "expected": "allow"}
        ],
        "limitations_and_unexecuted_tests": []
    }


def test_prepare_creates_bundle_only_offline_docker_plan(lab, tmp_path):
    run = prepared_run(lab, tmp_path)
    manifest = json.loads((run / "run-manifest.json").read_text(encoding="utf-8"))
    plan = json.loads((run / "phase1" / "docker-plan.json").read_text(encoding="utf-8"))

    assert manifest["state"] == "phase1_prepared"
    assert manifest["formal_execution_authorized"] is False
    assert plan["execution_authorized"] is False
    assert plan["network_mode"] == "none"
    assert plan["credential_injection"] == "disabled"
    assert plan["source_repository_mounted"] is False
    arguments = plan["docker_arguments_template"]
    assert "--read-only" in arguments
    assert arguments[arguments.index("--cap-drop") + 1] == "ALL"
    assert arguments[arguments.index("--network") + 1] == "none"
    mounts = [arguments[index + 1] for index, value in enumerate(arguments) if value == "--mount"]
    assert len(mounts) == 2
    assert "dst=/review/input,readonly" in mounts[0]
    assert "dst=/review/output" in mounts[1]
    assert all(str(run) in mount for mount in mounts)
    assert (run / "phase1" / "input" / "bundle-manifest.json").is_file()


def test_phase1_seal_requires_schema_and_detects_tampering(lab, tmp_path):
    run = prepared_run(lab, tmp_path)
    incomplete = run / "phase1" / "reviewer-output" / "incomplete.json"
    write_json(incomplete, {"independent_test_matrix": []})
    with pytest.raises(ValueError, match="missing required outputs"):
        seal_phase1(run, incomplete)

    submission = run / "phase1" / "reviewer-output" / "phase1.json"
    write_json(submission, phase1_submission())
    seal = seal_phase1(run, submission)
    assert seal["integrity_model"] == "read_only_copy_with_sha256_verification"
    assert verify_run(run)["state"] == "phase1_sealed"

    sealed = run / "phase1" / "sealed-output.json"
    sealed.chmod(stat.S_IWRITE | stat.S_IREAD)
    sealed.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="failed integrity verification"):
        verify_run(run)


def test_phase2_requires_human_authorization_and_preserves_hash_chain(lab, tmp_path):
    run = prepared_run(lab, tmp_path)
    submission = run / "phase1" / "reviewer-output" / "phase1.json"
    write_json(submission, phase1_submission())
    seal_phase1(run, submission)
    permissions = Path("fixtures/permissions.v1.json")
    results = tmp_path / "results.json"
    write_json(results, {
        "run_id": "deterministic-run",
        "summary": {"confirmed_violation": 0},
        "results": [{"case_id": "me:a_user1", "request": {"Authorization": "[REDACTED]"}}]
    })

    with pytest.raises(ValueError, match="phase2_authorized"):
        release_phase2(run)

    staging = stage_phase2(run, permissions, results)
    assert staging["files"] == ["authorization-matrix.json", "deterministic-results.json"]
    authorization = authorize_phase2(run, "project_owner", "Release approved comparison inputs")
    assert authorization["decision"] == "approved"
    assert authorization["phase2_staging_manifest_sha256"]
    release = release_phase2(run)
    assert release["approved_by"] == "project_owner"
    assert "bundle/bundle-manifest.json" in release["readable_files"]
    assert "phase1-output.json" in release["readable_files"]
    assert "authorization-matrix.json" in release["readable_files"]
    assert "deterministic-results.json" in release["readable_files"]
    assert verify_run(run)["state"] == "phase2_released"

    plan = json.loads((run / "phase2" / "docker-plan.json").read_text(encoding="utf-8"))
    assert plan["phase"] == "difference_review"
    assert plan["network_mode"] == "none"
    assert plan["execution_authorized"] is False


def test_phase2_rejects_unredacted_authorization(lab, tmp_path):
    run = prepared_run(lab, tmp_path)
    submission = run / "phase1" / "reviewer-output" / "phase1.json"
    write_json(submission, phase1_submission())
    seal_phase1(run, submission)
    results = tmp_path / "results.json"
    write_json(results, {"request": {"Authorization": "Bearer raw-secret-value"}})

    with pytest.raises(ValueError, match="Unredacted Authorization"):
        stage_phase2(run, "fixtures/permissions.v1.json", results)


def test_authorization_binds_exact_staged_inputs(lab, tmp_path):
    run = prepared_run(lab, tmp_path)
    submission = run / "phase1" / "reviewer-output" / "phase1.json"
    write_json(submission, phase1_submission())
    seal_phase1(run, submission)
    results = tmp_path / "results.json"
    write_json(results, {"summary": {"confirmed_violation": 0}})
    stage_phase2(run, "fixtures/permissions.v1.json", results)
    authorize_phase2(run, "project_owner", "Bind exact staged inputs")

    staged_results = run / "phase2" / "staged" / "deterministic-results.json"
    staged_results.chmod(stat.S_IWRITE | stat.S_IREAD)
    write_json(staged_results, {"summary": {"confirmed_violation": 1}})
    with pytest.raises(ValueError, match="Staged deterministic results failed integrity verification"):
        release_phase2(run)


def test_run_manifest_paths_cannot_escape_run_directory(lab, tmp_path):
    run = prepared_run(lab, tmp_path)
    manifest_path = run / "run-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["phase1_input"] = "../outside"
    write_json(manifest_path, manifest)

    with pytest.raises(ValueError, match="Unsafe manifest path|escapes the run directory"):
        verify_run(run)

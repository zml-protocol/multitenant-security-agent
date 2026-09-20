import hashlib
import json
from pathlib import Path

from reviewer.auth_budget.gate import approval_subject_sha256, read_profile
from reviewer.candidate import CONTROL_FILES, EXPECTED


ROOT = Path(__file__).resolve().parents[1]
ATTESTATION = ROOT / "assessment" / "appsec" / "v1" / "formal-candidate-attestation.json"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_formal_candidate_attestation_is_validated_but_not_authorized():
    attestation = json.loads(ATTESTATION.read_text(encoding="utf-8"))

    assert attestation["status"] == "validated_waiting_security_engineer_manual_launch_approval"
    assert attestation["codex_execution_authorized"] is False
    assert attestation["manual_launch_approved"] is False
    assert {key: attestation[key] for key in EXPECTED} == EXPECTED
    assert attestation["bundle_embedded_status"] == "draft_not_for_claude"
    assert all(attestation["checks"].values())
    assert attestation["profiles"]["runtime_sha256"] == file_sha256(ROOT / "reviewer/runtime/profile.json")
    assert attestation["profiles"]["egress_sha256"] == file_sha256(ROOT / "reviewer/egress/profile.json")
    assert attestation["profiles"]["execution_sha256"] == file_sha256(ROOT / "reviewer/execution/profile.json")
    assert attestation["profiles"]["approved_auth_budget_subject_sha256"] == approval_subject_sha256(read_profile())
    assert attestation["control_files_sha256"] == {
        relative: file_sha256(ROOT / relative)
        for relative in CONTROL_FILES
    }
    assert attestation["images"]["runtime_local_image_id"].startswith("sha256:")
    assert attestation["images"]["egress_local_image_id"].startswith("sha256:")


def test_machine_start_gate_allows_only_security_engineer_to_launch_v4():
    gate = json.loads((ROOT / "assessment/appsec/v1/start-gate.json").read_text(encoding="utf-8"))

    assert gate["status"] == "approved_for_security_engineer_manual_launch"
    assert gate["manual_launch_approved"] is True
    assert gate["codex_may_launch_claude"] is False
    assert gate["approved_by"] == "project_owner"
    assert gate["approved_at_utc"]
    assert gate["authorized_attestation_sha256"] == file_sha256(ATTESTATION)
    assert gate["authorized_handoff_manifest_sha256"] == gate["prepared_handoff_manifest_sha256"]
    assert gate["prepared_handoff_manifest_sha256"]
    assert gate["immutability_commitment_accepted"] is True
    assert gate["security_engineer_supplies_credential_at_manual_launch"] is True
    assert gate["previous_attempts"][-1]["outcome"] == "reviewer_infrastructure_failure_cli_prompt_parsed_as_deny_rules"
    assert gate["previous_attempts"][-1]["output_files_created"] == 0

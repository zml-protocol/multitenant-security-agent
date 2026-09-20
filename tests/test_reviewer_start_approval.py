import json
from pathlib import Path

from reviewer.start_approval import (
    ACTIVATION_CHANGES,
    PACKAGE_PATH,
    START_GATE_PATH,
    pointer_value,
    read_json,
    sha256,
    validate_prepared_package,
)


ROOT = Path(__file__).resolve().parents[1]


def test_package_records_manual_human_launch_boundary():
    package = validate_prepared_package()
    assert package["status"] == "prepared_waiting_security_engineer_manual_launch_approval"
    assert package["codex_execution_authorized"] is False
    assert package["responsibility_boundary"]["codex_may_launch_claude"] is False
    assert "run_manual_docker_command" in package["responsibility_boundary"]["security_engineer"]
    assert package["credential_boundary"]["api_key_value_managed_by_project"] is False
    assert package["candidate"]["attestation_sha256"] == sha256(
        ROOT / package["candidate"]["attestation"]
    )
    assert package["prepared_handoff"]["manifest"] == read_json(START_GATE_PATH)["prepared_handoff_manifest"]
    assert package["prepared_handoff"]["manifest_sha256"] == read_json(START_GATE_PATH)["prepared_handoff_manifest_sha256"]


def test_activation_changes_release_only_the_approved_manifest_metadata():
    package = validate_prepared_package()
    assert len(package["activation_changes"]) == len(ACTIVATION_CHANGES) == 2
    assert {change["file"] for change in package["activation_changes"]} == {
        "assessment/appsec/v1/reviewer-input-manifest.json"
    }
    for change in package["activation_changes"]:
        assert pointer_value(read_json(ROOT / change["file"]), change["json_pointer"]) == change["to"]


def test_v4_start_gate_authorizes_security_engineer_and_never_codex():
    gate = read_json(START_GATE_PATH)
    assert gate["status"] == "approved_for_security_engineer_manual_launch"
    assert gate["manual_launch_approved"] is True
    assert gate["codex_may_launch_claude"] is False
    assert gate["authorized_attestation_sha256"] == sha256(ROOT / "assessment/appsec/v1/formal-candidate-attestation.json")
    assert gate["authorized_handoff_manifest_sha256"] == gate["prepared_handoff_manifest_sha256"]
    assert gate["prepared_handoff_manifest_sha256"]
    assert gate["immutability_commitment_accepted"] is True
    assert gate["security_engineer_supplies_credential_at_manual_launch"] is True
    assert gate["previous_attempts"][-1]["outcome"] == "reviewer_infrastructure_failure_cli_prompt_parsed_as_deny_rules"


def test_package_contains_no_credential_value_or_project_key_workflow():
    serialized = PACKAGE_PATH.read_text(encoding="utf-8")
    package = json.loads(serialized)
    assert "sk-ant-" not in serialized
    assert "ANTHROPIC_API_KEY" not in serialized
    assert package["credential_boundary"]["api_key_value_recorded_in_approval"] is False


def test_human_records_publish_the_exact_approval_hashes():
    package = read_json(PACKAGE_PATH)
    package_hash = sha256(PACKAGE_PATH)
    attestation_hash = package["candidate"]["attestation_sha256"]
    for record in (
        ROOT / "docs/formal-start-approval.md",
        ROOT / "docs/formal-start-approval.en.md",
        ROOT / "assessment/appsec/v1/approval-record.md",
        ROOT / "assessment/appsec/v1/approval-record.en.md",
    ):
        text = record.read_text(encoding="utf-8")
        assert package_hash in text
        assert attestation_hash in text

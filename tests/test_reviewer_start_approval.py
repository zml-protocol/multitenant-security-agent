import json
from pathlib import Path

import pytest

from reviewer.start_approval import (
    ACTIVATION_CHANGES,
    PACKAGE_PATH,
    START_GATE_PATH,
    pointer_value,
    read_json,
    sha256,
    validate_authorized_start,
    validate_prepared_package,
)


ROOT = Path(__file__).resolve().parents[1]


def test_prepared_package_binds_candidate_and_keeps_execution_closed():
    package = validate_prepared_package()
    attestation = read_json(ROOT / package["candidate"]["attestation"])

    assert package["status"] == "prepared_not_approved"
    assert package["formal_execution_authorized"] is False
    assert package["candidate"]["attestation_sha256"] == sha256(
        ROOT / package["candidate"]["attestation"]
    )
    assert package["candidate"]["source_commit"] == attestation["source_commit"]
    assert package["remaining_human_decisions"]["formal_start_approval"] == "pending"
    assert package["external_prerequisites"]["dedicated_api_key_created"] is False


def test_activation_plan_matches_every_current_closed_value():
    package = validate_prepared_package()

    assert len(package["activation_changes"]) == len(ACTIVATION_CHANGES)
    for change in package["activation_changes"]:
        assert pointer_value(read_json(ROOT / change["file"]), change["json_pointer"]) == change["from"]


def test_start_gate_and_controller_still_fail_closed():
    gate = read_json(START_GATE_PATH)

    assert gate["formal_execution_authorized"] is False
    assert gate["authorized_approval_package_sha256"] is None
    with pytest.raises(PermissionError):
        validate_authorized_start()


def test_package_contains_no_credential_value_or_secret_field():
    serialized = PACKAGE_PATH.read_text(encoding="utf-8")
    package = json.loads(serialized)

    assert "sk-ant-" not in serialized
    assert "ANTHROPIC_API_KEY" not in serialized
    assert package["credential_handling"]["secret_in_repository_or_approval_records"] is False


def test_human_records_publish_the_exact_approval_hashes():
    package = read_json(PACKAGE_PATH)
    package_hash = sha256(PACKAGE_PATH)
    attestation_hash = package["candidate"]["attestation_sha256"]
    records = (
        ROOT / "docs/formal-start-approval.md",
        ROOT / "docs/formal-start-approval.en.md",
        ROOT / "assessment/appsec/v1/approval-record.md",
        ROOT / "assessment/appsec/v1/approval-record.en.md",
    )

    for record in records:
        text = record.read_text(encoding="utf-8")
        assert package_hash in text
        assert attestation_hash in text

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

    assert attestation["status"] == "validated_waiting_formal_start_approval"
    assert attestation["formal_execution_authorized"] is False
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


def test_machine_start_gate_remains_closed():
    gate = json.loads((ROOT / "assessment/appsec/v1/start-gate.json").read_text(encoding="utf-8"))

    assert gate["status"] == "awaiting_final_approval"
    assert gate["formal_execution_authorized"] is False
    assert gate["approved_by"] is None
    assert gate["approved_at_utc"] is None
    assert gate["authorized_attestation_sha256"] is None

"""Prepare a human manual-launch approval package without authorizing Codex execution."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from reviewer.auth_budget.gate import read_profile as read_auth_profile, validate_profile


ROOT = Path(__file__).resolve().parents[1]
ASSESSMENT = ROOT / "assessment" / "appsec" / "v1"
ATTESTATION_PATH = ASSESSMENT / "formal-candidate-attestation.json"
PACKAGE_PATH = ASSESSMENT / "formal-start-approval-package.json"
START_GATE_PATH = ASSESSMENT / "start-gate.json"
ACTIVATION_CHANGES = (
    ("assessment/appsec/v1/reviewer-input-manifest.json", "/status", "requirements_approved", "ready_for_claude_review"),
    (
        "assessment/appsec/v1/reviewer-input-manifest.json",
        "/tool_access_status",
        "interactive_static_review_prepared_not_authorized",
        "interactive_static_review_manual_launch_approved",
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pointer_value(document: dict[str, Any], pointer: str) -> Any:
    value: Any = document
    for segment in pointer.lstrip("/").split("/"):
        value = value[segment.replace("~1", "/").replace("~0", "~")]
    return value


def activation_changes() -> list[dict[str, Any]]:
    return [
        {"file": file, "json_pointer": pointer, "from": before, "to": after}
        for file, pointer, before, after in ACTIVATION_CHANGES
    ]


def _assert_preparation_only_state() -> None:
    gate = read_json(START_GATE_PATH)
    required = {
        "status": "awaiting_security_engineer_manual_launch_approval",
        "manual_launch_approved": False,
        "codex_may_launch_claude": False,
        "approved_by": None,
        "approved_at_utc": None,
        "authorized_attestation_sha256": None,
        "authorized_handoff_manifest_sha256": None,
        "immutability_commitment_accepted": False,
    }
    for field, expected in required.items():
        if gate.get(field) != expected:
            raise ValueError(f"Manual launch gate differs at {field}")
    if not gate.get("prepared_handoff_manifest") or not gate.get("prepared_handoff_manifest_sha256"):
        raise ValueError("Prepared handoff identity is missing")
    validate_profile(read_auth_profile())
    for profile_path in (
        ROOT / "reviewer/auth_budget/profile.json",
        ROOT / "reviewer/execution/profile.json",
        ROOT / "reviewer/runtime/profile.json",
        ROOT / "reviewer/egress/profile.json",
    ):
        profile = read_json(profile_path)
        if profile.get("formal_execution_authorized") is not False:
            raise ValueError(f"Codex execution must remain disabled in {profile_path}")
    for file, pointer, before, _ in ACTIVATION_CHANGES:
        if pointer_value(read_json(ROOT / file), pointer) != before:
            raise ValueError(f"Pre-approval value changed at {file}{pointer}")


def build_package(prepared_at_utc: str | None = None) -> dict[str, Any]:
    _assert_preparation_only_state()
    return _package_document(prepared_at_utc or utc_now())


def _package_document(prepared_at_utc: str) -> dict[str, Any]:
    attestation = read_json(ATTESTATION_PATH)
    return {
        "schema_version": "2.0",
        "status": "prepared_waiting_security_engineer_manual_launch_approval",
        "prepared_at_utc": prepared_at_utc,
        "candidate": {
            "attestation": ATTESTATION_PATH.relative_to(ROOT).as_posix(),
            "attestation_sha256": sha256(ATTESTATION_PATH),
            "source_commit": attestation["source_commit"],
            "fixture_id": attestation["fixture_id"],
            "scenario_id": attestation["scenario_id"],
            "bundle_id": attestation["bundle_id"],
            "bundle_manifest_sha256": attestation["bundle_manifest_sha256"],
            "claude_command_sha256": attestation["claude_command_sha256"],
        },
        "prepared_handoff": {
            "manifest": read_json(START_GATE_PATH)["prepared_handoff_manifest"],
            "manifest_sha256": read_json(START_GATE_PATH)["prepared_handoff_manifest_sha256"],
        },
        "responsibility_boundary": {
            "codex": [
                "generate_reviewer_bundle",
                "prepare_isolated_workspace_and_compose",
                "configure_read_only_input_and_writable_output",
                "prepare_interactive_static_review_launcher",
            ],
            "security_engineer": ["approve_manual_launch", "supply_credential_outside_project", "run_manual_docker_command"],
            "claude": ["read_isolated_bundle", "static_code_review", "write_draft_findings_and_advice"],
            "codex_may_launch_claude": False,
        },
        "remaining_human_decisions": {
            "assessment_window_immutability_commitment": "pending",
            "manual_launch_approval": "pending",
            "approver": None,
            "approved_at_utc": None,
        },
        "activation_changes": activation_changes(),
        "start_gate_required_values": {
            "status": "approved_for_security_engineer_manual_launch",
            "manual_launch_approved": True,
            "codex_may_launch_claude": False,
            "approved_by": "<security-engineer-identifier>",
            "approved_at_utc": "<UTC-timestamp>",
            "authorized_attestation_sha256": sha256(ATTESTATION_PATH),
            "authorized_handoff_manifest_sha256": "<sha256-of-prepared-handoff-manifest>",
            "immutability_commitment_accepted": True,
        },
        "approval_record_required_changes": {
            "approval_status": "ready_for_claude_review",
            "assessment_window_immutability_checkbox": True,
            "final_approver_and_time_checkbox": True,
        },
        "credential_boundary": {
            "api_key_value_managed_by_project": False,
            "api_key_value_recorded_in_approval": False,
            "security_engineer_supplies_at_manual_launch": True,
        },
        "codex_execution_authorized": False,
    }


def write_package(path: Path = PACKAGE_PATH) -> dict[str, Any]:
    package = build_package()
    with Path(path).open("w", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(package, indent=2) + "\n")
    return package


def validate_prepared_package(path: Path = PACKAGE_PATH) -> dict[str, Any]:
    package = read_json(path)
    expected = _package_document(package.get("prepared_at_utc"))
    if package != expected:
        raise ValueError("Prepared package differs from the manual handoff approval plan")
    return package


def write_json(path: Path, value: dict[str, Any]) -> None:
    with Path(path).open("w", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(value, indent=2) + "\n")


def approve_manual_launch(approver: str, approved_at_utc: str | None = None) -> dict[str, Any]:
    """Bind the prepared package and handoff for Security Engineer manual launch."""
    if not approver.strip():
        raise ValueError("Approver must be a non-empty Security Engineer identifier")
    package = validate_prepared_package()
    _assert_preparation_only_state()
    gate = read_json(START_GATE_PATH)
    handoff_manifest_path = ROOT / gate["prepared_handoff_manifest"]
    handoff_hash = sha256(handoff_manifest_path)
    if handoff_hash != gate["prepared_handoff_manifest_sha256"]:
        raise ValueError("Prepared handoff hash differs from the start gate")
    if handoff_hash != package["prepared_handoff"]["manifest_sha256"]:
        raise ValueError("Prepared handoff hash differs from the approval package")

    approved_at = approved_at_utc or utc_now()
    reviewer_manifest_path = ROOT / ACTIVATION_CHANGES[0][0]
    reviewer_manifest = read_json(reviewer_manifest_path)
    for _, pointer, before, after in ACTIVATION_CHANGES:
        key = pointer.lstrip("/")
        if reviewer_manifest.get(key) != before:
            raise ValueError(f"Reviewer manifest differs at {pointer}")
        reviewer_manifest[key] = after

    gate.update({
        "status": "approved_for_security_engineer_manual_launch",
        "manual_launch_approved": True,
        "codex_may_launch_claude": False,
        "approved_by": approver,
        "approved_at_utc": approved_at,
        "authorized_attestation_sha256": package["candidate"]["attestation_sha256"],
        "authorized_handoff_manifest_sha256": handoff_hash,
        "immutability_commitment_accepted": True,
    })
    workspace_approval_path = handoff_manifest_path.parent / "approval" / "manual-launch-approval.json"
    workspace_approval = read_json(workspace_approval_path)
    if workspace_approval.get("manual_launch_approved") is not False:
        raise ValueError("Workspace manual launch has already been approved")
    workspace_approval.update({
        "status": "approved_for_security_engineer_manual_launch",
        "manual_launch_approved": True,
        "approved_by": approver,
        "approved_at_utc": approved_at,
        "handoff_manifest_sha256": handoff_hash,
    })

    write_json(reviewer_manifest_path, reviewer_manifest)
    write_json(START_GATE_PATH, gate)
    write_json(workspace_approval_path, workspace_approval)
    return {
        "status": gate["status"],
        "approved_by": approver,
        "approved_at_utc": approved_at,
        "authorized_attestation_sha256": gate["authorized_attestation_sha256"],
        "authorized_handoff_manifest_sha256": handoff_hash,
        "codex_may_launch_claude": False,
    }

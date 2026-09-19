"""Prepare and verify the fail-closed formal reviewer start approval package."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
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
    ("reviewer/auth_budget/profile.json", "/status", "approved_not_formally_authorized", "formally_authorized"),
    ("reviewer/auth_budget/profile.json", "/formal_execution_authorized", False, True),
    ("reviewer/auth_budget/profile.json", "/model_invocation_enabled", False, True),
    ("reviewer/execution/profile.json", "/status", "implemented_not_formally_authorized", "formally_authorized"),
    ("reviewer/execution/profile.json", "/formal_execution_authorized", False, True),
    (
        "reviewer/runtime/profile.json",
        "/status",
        "image_definition_implemented_execution_not_authorized",
        "formal_execution_authorized",
    ),
    ("reviewer/runtime/profile.json", "/network_mode", "none", "internal_proxy_only"),
    (
        "reviewer/runtime/profile.json",
        "/credential_injection",
        "disabled",
        "runtime_read_only_secret_file",
    ),
    ("reviewer/runtime/profile.json", "/formal_execution_authorized", False, True),
    (
        "reviewer/egress/profile.json",
        "/status",
        "egress_foundation_implemented_not_active",
        "active_for_formal_reviewer",
    ),
    ("reviewer/egress/profile.json", "/active_in_reviewer_runner", False, True),
    ("reviewer/egress/profile.json", "/formal_execution_authorized", False, True),
    (
        "assessment/appsec/v1/reviewer-input-manifest.json",
        "/status",
        "requirements_approved",
        "ready_for_claude_review",
    ),
    (
        "assessment/appsec/v1/reviewer-input-manifest.json",
        "/tool_access_status",
        "isolation_and_phase_gates_implemented_not_authorized",
        "formal_execution_authorized",
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


def _assert_closed_state() -> None:
    gate = read_json(START_GATE_PATH)
    required_closed = {
        "status": "awaiting_final_approval",
        "formal_execution_authorized": False,
        "approved_by": None,
        "approved_at_utc": None,
        "authorized_attestation_sha256": None,
        "authorized_approval_package_sha256": None,
        "immutability_commitment_accepted": False,
    }
    for field, expected in required_closed.items():
        if gate.get(field) != expected:
            raise ValueError(f"Start gate is not closed at {field}")
    external = gate.get("external_prerequisites", {})
    if external.get("dedicated_api_key_created") is not False:
        raise ValueError("Dedicated API key must not be marked created during package preparation")
    if any(
        external.get(field) is not None
        for field in (
            "anthropic_workspace_name",
            "api_key_label",
            "workspace_spend_limit_usd",
            "workspace_spend_limit_period",
            "auto_reload_enabled",
        )
    ):
        raise ValueError("External prerequisite values must remain empty before final approval")
    validate_profile(read_auth_profile())
    for file, pointer, before, _ in ACTIVATION_CHANGES:
        if pointer_value(read_json(ROOT / file), pointer) != before:
            raise ValueError(f"Pre-approval value changed at {file}{pointer}")


def build_package(prepared_at_utc: str | None = None) -> dict[str, Any]:
    _assert_closed_state()
    attestation = read_json(ATTESTATION_PATH)
    if attestation.get("formal_execution_authorized") is not False:
        raise ValueError("Candidate attestation must remain unauthorized")
    return {
        "schema_version": "1.0",
        "status": "prepared_not_approved",
        "prepared_at_utc": prepared_at_utc or utc_now(),
        "candidate": {
            "attestation": ATTESTATION_PATH.relative_to(ROOT).as_posix(),
            "attestation_sha256": sha256(ATTESTATION_PATH),
            "source_commit": attestation["source_commit"],
            "fixture_id": attestation["fixture_id"],
            "scenario_id": attestation["scenario_id"],
            "bundle_id": attestation["bundle_id"],
            "bundle_manifest_sha256": attestation["bundle_manifest_sha256"],
            "runtime_local_image_id": attestation["images"]["runtime_local_image_id"],
            "egress_local_image_id": attestation["images"]["egress_local_image_id"],
            "claude_command_sha256": attestation["claude_command_sha256"],
        },
        "approved_run_boundaries": {
            "model": "claude-sonnet-5",
            "maximum_cost_usd": "1.00",
            "maximum_agentic_turns": 12,
            "maximum_duration_seconds": 900,
            "maximum_captured_output_bytes": 1048576,
            "allowed_tools": ["Read", "Glob", "Grep"],
            "allowed_egress": ["api.anthropic.com:443"],
        },
        "remaining_human_decisions": {
            "assessment_window_immutability_commitment": "pending",
            "formal_start_approval": "pending",
            "approver": None,
            "approved_at_utc": None,
        },
        "external_prerequisites": {
            "dedicated_anthropic_workspace_created": False,
            "dedicated_api_key_created": False,
            "workspace_spend_limit_recorded": False,
            "auto_reload_confirmed_disabled": False,
            "secret_value_must_not_be_recorded": True,
        },
        "activation_changes": activation_changes(),
        "start_gate_required_values": {
            "status": "formal_execution_authorized",
            "formal_execution_authorized": True,
            "approved_by": "<security-engineer-identifier>",
            "approved_at_utc": "<UTC-timestamp>",
            "authorized_attestation_sha256": sha256(ATTESTATION_PATH),
            "authorized_approval_package_sha256": "<sha256-of-this-unchanged-package-file>",
            "immutability_commitment_accepted": True,
            "external_prerequisites": {
                "anthropic_workspace_name": "<non-secret-workspace-name>",
                "api_key_label": "<non-secret-key-label>",
                "workspace_spend_limit_usd": "<positive-value-no-greater-than-1.00>",
                "workspace_spend_limit_period": "<provider-console-period>",
                "auto_reload_enabled": False,
                "dedicated_api_key_created": True,
            },
        },
        "approval_record_required_changes": {
            "approval_status": "ready_for_claude_review",
            "assessment_window_immutability_checkbox": True,
            "final_approver_and_time_checkbox": True,
        },
        "credential_handling": {
            "secret_storage": "ephemeral_file_outside_repository",
            "secret_in_repository_or_approval_records": False,
            "secret_in_command_line": False,
            "revoke_after_run": True,
        },
        "formal_execution_authorized": False,
    }


def write_package(path: Path = PACKAGE_PATH) -> dict[str, Any]:
    package = build_package()
    with Path(path).open("w", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(package, indent=2) + "\n")
    return package


def validate_prepared_package(path: Path = PACKAGE_PATH) -> dict[str, Any]:
    package = read_json(path)
    expected = build_package(package.get("prepared_at_utc"))
    if package != expected:
        raise ValueError("Prepared approval package differs from the closed-gate plan")
    return package


def validate_authorized_start() -> None:
    package = read_json(PACKAGE_PATH)
    gate = read_json(START_GATE_PATH)
    if package.get("status") != "prepared_not_approved" or package.get("formal_execution_authorized") is not False:
        raise ValueError("The immutable approval package is not a prepared closed-gate plan")
    required = {
        "status": "formal_execution_authorized",
        "formal_execution_authorized": True,
        "authorized_attestation_sha256": package["candidate"]["attestation_sha256"],
        "authorized_approval_package_sha256": sha256(PACKAGE_PATH),
        "immutability_commitment_accepted": True,
    }
    for field, expected in required.items():
        if gate.get(field) != expected:
            raise PermissionError(f"Formal start gate is incomplete at {field}")
    if not gate.get("approved_by") or not gate.get("approved_at_utc"):
        raise PermissionError("Formal start approver and UTC time are required")
    external = gate.get("external_prerequisites", {})
    if not external.get("anthropic_workspace_name") or not external.get("api_key_label"):
        raise PermissionError("Dedicated workspace and non-secret key label are required")
    if external.get("dedicated_api_key_created") is not True or external.get("auto_reload_enabled") is not False:
        raise PermissionError("Dedicated key and disabled auto-reload are required")
    try:
        spend_limit = Decimal(str(external.get("workspace_spend_limit_usd")))
    except (InvalidOperation, TypeError):
        raise PermissionError("A numeric workspace spend limit is required") from None
    if not Decimal("0") < spend_limit <= Decimal("1.00"):
        raise PermissionError("Workspace spend limit must be positive and no greater than $1.00")
    if not external.get("workspace_spend_limit_period"):
        raise PermissionError("Workspace spend-limit period is required")
    for file, pointer, _, after in ACTIVATION_CHANGES:
        if pointer_value(read_json(ROOT / file), pointer) != after:
            raise PermissionError(f"Authorized value is missing at {file}{pointer}")
    validate_profile(read_auth_profile())

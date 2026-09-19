"""Fail-closed validation for the proposed reviewer credential and budget profile."""
from __future__ import annotations

from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = Path(__file__).with_name("profile.json")
DEFAULT_OUTPUT_ROOT = ROOT / ".local" / "reviewer-auth-budget"
SENSITIVE_ENVIRONMENT_VARIABLES = frozenset(
    {"ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"}
)


def read_profile(path: Path = PROFILE_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def planning_cost(profile: Mapping[str, Any]) -> Decimal:
    budget = profile["budget"]
    input_cost = (
        Decimal(budget["maximum_aggregate_input_tokens"])
        * Decimal(budget["standard_input_usd_per_million_tokens"])
        / Decimal(1_000_000)
    )
    output_cost = (
        Decimal(budget["maximum_aggregate_output_tokens"])
        * Decimal(budget["standard_output_usd_per_million_tokens"])
        / Decimal(1_000_000)
    )
    return (input_cost + output_cost).quantize(Decimal("0.01"))


def approval_subject_sha256(profile: Mapping[str, Any]) -> str:
    subject = {
        key: profile[key]
        for key in ("credential", "model", "budget", "limitations")
    }
    serialized = json.dumps(subject, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(serialized).hexdigest()


def validate_profile(profile: Mapping[str, Any]) -> None:
    if profile.get("formal_execution_authorized") is not False:
        raise ValueError("Credential and budget profile must not authorize formal execution")
    if profile.get("model_invocation_enabled") is not False:
        raise ValueError("Model invocation must remain disabled")
    if profile.get("status") not in {
        "proposed_tested_not_approved",
        "approved_not_formally_authorized",
    }:
        raise ValueError("Credential and budget profile status is invalid")
    credential = profile["credential"]
    if credential.get("type") != "dedicated_anthropic_workspace_api_key":
        raise ValueError("A dedicated Anthropic workspace API key is required")
    if credential.get("runtime_environment_variable") != "ANTHROPIC_API_KEY":
        raise ValueError("The approved runtime credential name is fixed")
    if credential.get("key_identifier") is not None:
        raise ValueError("No real key identifier may be recorded before approval")
    forbidden_true = (
        "host_personal_claude_login_allowed",
        "bundle_storage_allowed",
        "command_line_allowed",
        "image_layer_storage_allowed",
        "log_or_output_storage_allowed",
    )
    if any(credential.get(field) is not False for field in forbidden_true):
        raise ValueError("Credential exposure controls must fail closed")
    if profile["model"].get("model_id") != "claude-sonnet-5":
        raise ValueError("Reviewer model must remain fixed")
    budget = profile["budget"]
    for field in (
        "maximum_aggregate_input_tokens",
        "maximum_aggregate_output_tokens",
        "maximum_model_api_calls",
        "maximum_agentic_turns",
        "maximum_supplemental_tool_calls",
        "maximum_run_duration_seconds",
    ):
        if not isinstance(budget.get(field), int) or budget[field] <= 0:
            raise ValueError(f"{field} must be a positive integer")
    if planning_cost(profile) != Decimal(budget["standard_planning_cost_usd"]):
        raise ValueError("Recorded planning cost does not match the token ceilings")
    if planning_cost(profile) > Decimal(budget["maximum_approved_cost_usd"]):
        raise ValueError("Planning cost exceeds the proposed per-run cost ceiling")
    approval = profile["approval"]
    if profile["status"] == "proposed_tested_not_approved":
        if approval.get("approved") is not False or any(
            approval.get(field) is not None
            for field in ("approved_by", "approved_at_utc", "approved_profile_sha256")
        ):
            raise ValueError("Approval fields must remain empty before human approval")
    else:
        if approval.get("approved") is not True:
            raise ValueError("Approved profile must record approval")
        if not approval.get("approved_by") or not approval.get("approved_at_utc"):
            raise ValueError("Approved profile must record approver and time")
        if approval.get("approved_profile_sha256") != approval_subject_sha256(profile):
            raise ValueError("Approved profile hash does not match the approval subject")
        if profile["model"].get("selection_status") != "approved":
            raise ValueError("Approved profile must record the model decision")


def sanitized_subprocess_environment(environment: Mapping[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in environment.items()
        if key.upper() not in SENSITIVE_ENVIRONMENT_VARIABLES
    }


def execution_envelope(profile: Mapping[str, Any]) -> dict[str, Any]:
    validate_profile(profile)
    return {
        "schema_version": "1.0",
        "execution_authorized": False,
        "model_invocation_enabled": False,
        "network_mode": "none",
        "credential_injection": "disabled",
        "credential_source_type": profile["credential"]["type"],
        "credential_environment_variable": profile["credential"]["runtime_environment_variable"],
        "credential_value_present": False,
        "model_id": profile["model"]["model_id"],
        "budget": {
            key: profile["budget"][key]
            for key in (
                "maximum_aggregate_input_tokens",
                "maximum_aggregate_output_tokens",
                "maximum_model_api_calls",
                "maximum_agentic_turns",
                "maximum_supplemental_tool_calls",
                "maximum_run_duration_seconds",
                "standard_planning_cost_usd",
                "maximum_approved_cost_usd",
                "currency",
            )
        },
    }


def _contains(path: Path, needle: bytes) -> bool:
    if path.is_file():
        return needle in path.read_bytes()
    return any(needle in item.read_bytes() for item in path.rglob("*") if item.is_file())


def run_synthetic_smoke(output_root: Path = DEFAULT_OUTPUT_ROOT, bundle: Path | None = None) -> dict[str, Any]:
    """Exercise the boundary with a memory-only fake key; never contact Anthropic."""
    profile = read_profile()
    validate_profile(profile)
    sentinel = f"sk-ant-synthetic-{secrets.token_hex(24)}"
    candidate_environment = dict(os.environ)
    candidate_environment["ANTHROPIC_API_KEY"] = sentinel
    child_environment = sanitized_subprocess_environment(candidate_environment)
    probe_code = (
        "import json,os; "
        "names=('ANTHROPIC_API_KEY','ANTHROPIC_AUTH_TOKEN','CLAUDE_CODE_OAUTH_TOKEN'); "
        "print(json.dumps({'sensitive_environment_present': any(n in os.environ for n in names)}))"
    )
    command = [sys.executable, "-c", probe_code]
    completed = subprocess.run(
        command,
        env=child_environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    probe = json.loads(completed.stdout)
    if probe != {"sensitive_environment_present": False}:
        raise RuntimeError("Synthetic credential reached the child process")

    run_directory = Path(output_root) / f"smoke-{secrets.token_hex(6)}"
    run_directory.mkdir(parents=True, exist_ok=False)
    envelope = execution_envelope(profile)
    result = {
        "schema_version": "1.0",
        "status": "passed",
        "real_credential_used": False,
        "model_called": False,
        "network_used": False,
        "formal_execution_authorized": False,
        "checks": {
            "profile_valid": True,
            "sentinel_absent_from_command_line": sentinel not in "\0".join(command),
            "sentinel_absent_from_subprocess_environment": sentinel not in child_environment.values(),
            "sensitive_environment_absent_from_child": True,
            "sentinel_absent_from_bundle": bundle is None or not _contains(Path(bundle), sentinel.encode()),
            "sentinel_absent_from_log_and_output": True,
        },
        "execution_envelope": envelope,
    }
    if not all(result["checks"].values()):
        raise RuntimeError("Synthetic credential boundary check failed")
    result_path = run_directory / "result.json"
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if _contains(run_directory, sentinel.encode()):
        raise RuntimeError("Synthetic credential entered smoke output")
    return {"run_directory": str(run_directory), **result}


def main() -> int:
    candidate = ROOT / ".local" / "formal-candidate" / "reviewer-bundle"
    bundles = [path for path in candidate.iterdir()] if candidate.is_dir() else []
    bundle = next((path for path in bundles if path.is_dir()), None)
    result = run_synthetic_smoke(bundle=bundle)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

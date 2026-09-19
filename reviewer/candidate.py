"""Validate and attest the exact frozen reviewer candidate without authorizing execution."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

from reviewer.auth_budget.gate import approval_subject_sha256, read_profile as read_auth_profile, validate_profile
from reviewer.bundle import FORBIDDEN_MARKERS
from reviewer.execution.controller import PROFILE_PATH as EXECUTION_PROFILE_PATH, claude_arguments
from reviewer.runner import validate_bundle


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ATTESTATION = ROOT / "assessment" / "appsec" / "v1" / "formal-candidate-attestation.json"
RUNTIME_PROFILE_PATH = ROOT / "reviewer" / "runtime" / "profile.json"
EGRESS_PROFILE_PATH = ROOT / "reviewer" / "egress" / "profile.json"
START_GATE_PATH = ROOT / "assessment" / "appsec" / "v1" / "start-gate.json"
EXPECTED = {
    "source_commit": "14a7b48ae30b833962752e4d65b7e03ade5664a1",
    "fixture_id": "fixture-256eb13b57860e22",
    "scenario_id": "scenario-7f3a",
    "bundle_id": "bundle-6a1a247aca19153c0d22",
    "requirement_version": "appsec-v1.0",
}
CONTROL_FILES = (
    "reviewer/auth_budget/gate.py",
    "reviewer/start_approval.py",
    "reviewer/execution/controller.py",
    "reviewer/runtime/Dockerfile",
    "reviewer/runtime/managed-settings.json",
    "reviewer/runtime/credential-exec.sh",
    "reviewer/runtime/credential-probe.sh",
    "reviewer/egress/Dockerfile",
    "reviewer/egress/proxy.js",
)


def read_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_value(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def validate_candidate(bundle: Path, fixture_directory: Path, runtime_image_id: str, egress_image_id: str) -> dict:
    bundle, manifest, access = validate_bundle(bundle)
    actual = {field: manifest[field] for field in EXPECTED}
    if actual != EXPECTED:
        raise ValueError(f"Candidate identity differs from the approved freeze record: {actual}")
    if manifest.get("source_worktree_dirty") is not False:
        raise ValueError("Candidate source worktree was dirty when the bundle was generated")
    if access.get("status") != "requirements_approved":
        raise ValueError("Reviewer input requirements are not approved")
    if manifest.get("status") != "draft_not_for_claude":
        raise ValueError("Candidate bundle status changed before final start approval")

    combined = b"\n".join(path.read_bytes() for path in bundle.rglob("*") if path.is_file())
    for marker in FORBIDDEN_MARKERS:
        if marker.encode() in combined:
            raise ValueError(f"Candidate contains forbidden ground-truth marker: {marker}")
    credentials_path = Path(fixture_directory) / "credentials.json"
    if credentials_path.is_file():
        credentials = read_json(credentials_path)
        for token in credentials.get("tokens", {}).values():
            if token.encode() in combined:
                raise ValueError("Candidate contains a raw application credential")

    ref_targets = {
        "assessment/v1-vulnerable": git_value("rev-parse", "assessment/v1-vulnerable"),
        "remediation/v1": git_value("rev-parse", "remediation/v1"),
        "appsec-v1-vulnerable^{}": git_value("rev-parse", "appsec-v1-vulnerable^{}"),
    }
    if any(value != EXPECTED["source_commit"] for value in ref_targets.values()):
        raise ValueError("A frozen Git reference no longer points to the approved commit")

    auth = read_auth_profile()
    validate_profile(auth)
    if auth["approval"].get("approved") is not True:
        raise ValueError("Credential, model, and budget proposal is not approved")
    start = read_json(START_GATE_PATH)
    if start.get("formal_execution_authorized") is not False:
        raise ValueError("Candidate validation must occur before formal start authorization")
    execution = read_json(EXECUTION_PROFILE_PATH)
    if execution.get("formal_execution_authorized") is not False:
        raise ValueError("Execution profile must remain unauthorized")
    commands = {
        phase: claude_arguments(phase)
        for phase in execution["phases"]
    }
    serialized_commands = json.dumps(commands, sort_keys=True, separators=(",", ":"))
    if "sk-ant-" in serialized_commands or "ANTHROPIC_API_KEY=" in serialized_commands:
        raise ValueError("Credential material entered the approved Claude command")

    return {
        "schema_version": "1.0",
        "status": "validated_waiting_formal_start_approval",
        "validated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        **EXPECTED,
        "bundle_embedded_status": manifest["status"],
        "bundle_manifest_sha256": sha256(bundle / "bundle-manifest.json"),
        "frozen_ref_targets": ref_targets,
        "profiles": {
            "runtime_sha256": sha256(RUNTIME_PROFILE_PATH),
            "egress_sha256": sha256(EGRESS_PROFILE_PATH),
            "execution_sha256": sha256(EXECUTION_PROFILE_PATH),
            "approved_auth_budget_subject_sha256": approval_subject_sha256(auth),
        },
        "control_files_sha256": {
            relative: sha256(ROOT / relative)
            for relative in CONTROL_FILES
        },
        "images": {
            "runtime_local_image_id": runtime_image_id,
            "egress_local_image_id": egress_image_id,
            "registry_digest_required_for_cloud_deployment": True,
        },
        "claude_command_sha256": hashlib.sha256(serialized_commands.encode()).hexdigest(),
        "checks": {
            "bundle_allowlist_and_hashes_valid": True,
            "source_commit_and_fixture_frozen": True,
            "neutral_scenario_recorded": True,
            "ground_truth_markers_absent": True,
            "raw_application_credentials_absent": True,
            "credential_model_budget_approved": True,
            "formal_execution_still_unauthorized": True,
        },
        "formal_execution_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--fixture-directory", type=Path, required=True)
    parser.add_argument("--runtime-image-id", required=True)
    parser.add_argument("--egress-image-id", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_ATTESTATION)
    args = parser.parse_args()
    attestation = validate_candidate(
        args.bundle, args.fixture_directory, args.runtime_image_id, args.egress_image_id
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(attestation, indent=2) + "\n")
    print(json.dumps(attestation, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Adapt a prepared static-review handoff for remediation verification without launching Claude."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shlex

from reviewer.auth_budget.gate import read_profile as read_auth_profile, validate_profile
from reviewer.execution.controller import PROFILE_PATH


ROOT = Path(__file__).resolve().parents[1]
PROMPT = ROOT / "reviewer" / "execution" / "prompts" / "remediation-verification.txt"
SCHEMA = ROOT / "reviewer" / "execution" / "schemas" / "remediation-verification.schema.json"
OUTPUTS = [
    "verification-log.json",
    "remediation-verification.json",
    "remediation-verification.md",
    "remediation-verification.en.md",
    "limitations.md",
    "limitations.en.md",
]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def claude_arguments() -> list[str]:
    profile = read_json(PROFILE_PATH)
    auth = read_auth_profile()
    validate_profile(auth)
    return [
        "claude", "--restricted", "--bare",
        "--add-dir", "/review/output",
        "--disable-slash-commands", "--no-chrome", "--strict-mcp-config",
        "--model", auth["model"]["model_id"],
        "--permission-mode", "dontAsk",
        "--tools", ",".join(profile["allowed_tools"]),
        "--allowedTools", ",".join(profile["allowed_tools"]),
        "--disallowedTools", ",".join(profile["disallowed_tools"]),
        "--", PROMPT.read_text(encoding="utf-8").strip(),
    ]


def adapt(workspace: Path) -> None:
    workspace = workspace.resolve()
    manifest_path = workspace / "handoff-manifest.json"
    approval_path = workspace / "approval" / "manual-launch-approval.json"
    if not manifest_path.is_file() or not approval_path.is_file():
        raise ValueError("Prepared handoff is incomplete")
    approval = read_json(approval_path)
    if approval.get("manual_launch_approved") is not False:
        raise ValueError("Cannot adapt an already approved handoff")
    json.loads(SCHEMA.read_text(encoding="utf-8"))
    command = shlex.join(claude_arguments())
    (workspace / "launch" / "launch.sh").write_text(
        "#!/bin/sh\nset -eu\n"
        "if ! node -e \"const a=require('/review/approval/manual-launch-approval.json');"
        "if(a.manual_launch_approved!==true)process.exit(1)\"; then\n"
        "  echo 'Security Engineer manual-launch approval is missing' >&2\n"
        "  exit 78\n"
        "fi\n"
        "ulimit -f 2048\n"
        f"exec timeout --signal=TERM --kill-after=10s 900s /usr/local/bin/reviewer-credential-exec {command}\n",
        encoding="utf-8", newline="\n",
    )
    manifest = read_json(manifest_path)
    manifest.update({
        "phase": "remediation_verification",
        "review_mode": "interactive_static_remediation_verification_only",
        "required_outputs": OUTPUTS,
        "expected_outputs": OUTPUTS,
        "prompt": PROMPT.relative_to(ROOT).as_posix(),
        "reference_output_schema": SCHEMA.relative_to(ROOT).as_posix(),
        "remediation_prompt_sha256": sha256(PROMPT),
        "remediation_schema_sha256": sha256(SCHEMA),
        "manual_claude_command": claude_arguments(),
        "remediation_verification": {
            "finding_id": "F1",
            "allowed_statuses": ["remediation_verified", "remediation_rejected", "needs_more_evidence"],
            "final_acceptance_authority": "security_engineer",
        },
    })
    write_json(manifest_path, manifest)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    adapt(args.workspace)
    print(f"Adapted remediation-verification handoff without launching Claude: {args.workspace.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

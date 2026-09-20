"""Prepare a static-only interactive Claude reviewer handoff without launching it."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil

from reviewer.auth_budget.gate import planning_cost, read_profile as read_auth_profile, validate_profile
from reviewer.runner import validate_bundle


ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = Path(__file__).with_name("profile.json")
RUNTIME_PROFILE_PATH = ROOT / "reviewer" / "runtime" / "profile.json"
EGRESS_PROFILE_PATH = ROOT / "reviewer" / "egress" / "profile.json"
DEFAULT_HANDOFF_ROOT = ROOT / ".local" / "reviewer-handoffs"
DEFAULT_RESULTS_ROOT = ROOT / ".local" / "reviewer-results"
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def read_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    with Path(path).open("w", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(value, indent=2) + "\n")


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def phase_configuration(phase: str) -> tuple[dict, Path, Path]:
    profile = read_json(PROFILE_PATH)
    if phase not in profile["phases"]:
        raise ValueError(f"Unsupported reviewer phase: {phase}")
    configured = profile["phases"][phase]
    prompt = (ROOT / configured["prompt"]).resolve()
    schema = (ROOT / configured["output_schema"]).resolve()
    if not prompt.is_file() or not schema.is_file():
        raise ValueError("Reviewer prompt or output schema is missing")
    json.loads(schema.read_text(encoding="utf-8"))
    return profile, prompt, schema


def claude_arguments(phase: str) -> list[str]:
    profile, prompt_path, _ = phase_configuration(phase)
    auth = read_auth_profile()
    validate_profile(auth)
    return [
        "claude", "--restricted", "--bare",
        "--add-dir", "/review/output",
        "--disable-slash-commands", "--no-chrome",
        "--strict-mcp-config",
        "--model", auth["model"]["model_id"],
        "--permission-mode", "dontAsk",
        "--tools", ",".join(profile["allowed_tools"]),
        "--allowedTools", ",".join(profile["allowed_tools"]),
        "--disallowedTools", ",".join(profile["disallowed_tools"]),
        "--",
        prompt_path.read_text(encoding="utf-8").strip(),
    ]


def build_handoff_plan(input_directory: Path, output_directory: Path, phase: str) -> dict:
    profile, prompt_path, schema_path = phase_configuration(phase)
    auth = read_auth_profile()
    validate_profile(auth)
    budget = auth["budget"]
    runtime = read_json(RUNTIME_PROFILE_PATH)
    egress = read_json(EGRESS_PROFILE_PATH)
    return {
        "schema_version": "3.0",
        "phase": phase,
        "review_mode": "interactive_static_code_review_only",
        "status": "prepared_waiting_human_manual_launch_approval",
        "codex_may_launch_claude": False,
        "human_manual_launch_required": True,
        "source_repository_mounted": False,
        "credential_value_handled_by_project": False,
        "workspace": {
            "input": str(Path(input_directory).resolve()),
            "input_mount": "/review/input:ro",
            "output": str(Path(output_directory).resolve()),
            "output_mount": "/review/output:rw",
            "working_directory": "/review/input",
        },
        "runtime": {
            "image": runtime["image"],
            "claude_code_version": runtime["claude_code_version"],
            "container_user": runtime["container_user"],
            "interactive_tty": True,
        },
        "network": {
            "reviewer_internal_network": True,
            "direct_reviewer_egress": False,
            "anthropic_proxy_target": egress["allowed_connect_targets"],
            "application_target_present": False,
            "dynamic_test_gateway_present": False,
        },
        "static_review_boundary": {
            "allowed_tools": profile["allowed_tools"],
            "disallowed_tools": profile["disallowed_tools"],
            "dynamic_testing_allowed": False,
            "application_requests_allowed": False,
            "application_credentials_present": False,
            "input_writable": False,
            "output_writable": True,
        },
        "required_outputs": profile["required_outputs"],
        "model": auth["model"]["model_id"],
        "budget": {
            "maximum_agentic_turns": budget["maximum_agentic_turns"],
            "maximum_run_duration_seconds": budget["maximum_run_duration_seconds"],
            "maximum_approved_cost_usd": budget["maximum_approved_cost_usd"],
            "standard_planning_cost_usd": str(planning_cost(auth)),
            "interactive_cli_native_cost_stop_available": False,
            "provider_spend_limit_and_post_run_reconciliation_required": True,
        },
        "prompt": prompt_path.relative_to(ROOT).as_posix(),
        "reference_output_schema": schema_path.relative_to(ROOT).as_posix(),
        "manual_claude_command": claude_arguments(phase),
    }


def _compose_text(runtime_image: str, egress_image: str) -> str:
    return f"""services:
  egress-proxy:
    image: {egress_image}
    build:
      context: ./egress
      provenance: false
    read_only: true
    user: "10002:10002"
    cap_drop: [ALL]
    security_opt: ["no-new-privileges:true"]
    networks: [reviewer-lab, reviewer-outbound]
    healthcheck:
      test: ["CMD", "node", "-e", "const s=require('net').connect(3128,'127.0.0.1');s.on('connect',()=>{{s.destroy();process.exit(0)}});s.on('error',()=>process.exit(1))"]
      interval: 2s
      timeout: 2s
      retries: 20
  reviewer:
    image: {runtime_image}
    build:
      context: ./runtime
      provenance: false
      args:
        CLAUDE_CODE_VERSION: "2.1.278"
    read_only: true
    user: "10001:10001"
    cap_drop: [ALL]
    security_opt: ["no-new-privileges:true"]
    pids_limit: 128
    mem_limit: 1g
    cpus: 1
    stdin_open: true
    tty: true
    networks: [reviewer-lab]
    depends_on:
      egress-proxy: {{condition: service_healthy}}
    environment:
      HTTPS_PROXY: http://egress-proxy:3128
      HTTP_PROXY: http://egress-proxy:3128
      NO_PROXY: ""
      REVIEWER_CREDENTIAL_FILE: /run/secrets/anthropic_api_key
    secrets: [anthropic_api_key]
    volumes:
      - ./input:/review/input:ro
      - ${{REVIEWER_OUTPUT_DIR:?Set REVIEWER_OUTPUT_DIR}}:/review/output:rw
      - ./approval:/review/approval:ro
      - ./launch:/review/launch:ro
    tmpfs:
      - /run/claude-config:rw,noexec,nosuid,nodev,size=16m,uid=10001,gid=10001,mode=0700
      - /tmp:rw,noexec,nosuid,nodev,size=16m,uid=10001,gid=10001,mode=0700
    working_dir: /review/input
    entrypoint: ["/bin/sh", "/review/launch/launch.sh"]
  preflight:
    image: {runtime_image}
    read_only: true
    user: "10001:10001"
    cap_drop: [ALL]
    security_opt: ["no-new-privileges:true"]
    pids_limit: 64
    mem_limit: 512m
    cpus: 0.5
    stdin_open: false
    tty: false
    networks: [reviewer-lab]
    depends_on:
      egress-proxy: {{condition: service_healthy}}
    environment:
      HTTPS_PROXY: http://egress-proxy:3128
      HTTP_PROXY: http://egress-proxy:3128
      NO_PROXY: ""
      REVIEWER_CREDENTIAL_FILE: /run/secrets/anthropic_api_key
    secrets: [anthropic_api_key]
    volumes:
      - ./preflight:/review/input:ro
      - ./preflight-output:/review/output:rw
      - ./launch:/review/launch:ro
    tmpfs:
      - /run/claude-config:rw,noexec,nosuid,nodev,size=8m,uid=10001,gid=10001,mode=0700
      - /tmp:rw,noexec,nosuid,nodev,size=8m,uid=10001,gid=10001,mode=0700
    working_dir: /review/input
    entrypoint: ["/bin/sh", "/review/launch/preflight.sh"]
secrets:
  anthropic_api_key:
    file: ${{ANTHROPIC_API_KEY_FILE:?Pass a repository-external key file to START-CLAUDE.cmd}}
networks:
  reviewer-lab:
    internal: true
  reviewer-outbound:
"""


def _windows_launcher(workspace: Path, output_directory: Path) -> str:
    compose = workspace / "compose.yaml"
    return (
        "@echo off\r\n"
        "setlocal\r\n"
        "if \"%~1\"==\"\" (echo Usage: START-CLAUDE.cmd C:\\path\\to\\anthropic-api-key.txt 1>&2 & exit /b 64)\r\n"
        "if not exist \"%~1\" (echo API key file does not exist 1>&2 & exit /b 66)\r\n"
        "for %%I in (\"%~1\") do set \"ANTHROPIC_API_KEY_FILE=%%~fI\"\r\n"
        f"set \"REVIEWER_OUTPUT_DIR={output_directory}\"\r\n"
        f"docker compose --project-directory \"{workspace}\" -f \"{compose}\" build reviewer egress-proxy\r\n"
        "if errorlevel 1 exit /b %errorlevel%\r\n"
        f"docker compose --project-directory \"{workspace}\" -f \"{compose}\" run --rm reviewer\r\n"
        "set \"REVIEW_EXIT=%errorlevel%\"\r\n"
        f"docker compose --project-directory \"{workspace}\" -f \"{compose}\" down -v\r\n"
        "exit /b %REVIEW_EXIT%\r\n"
    )


def _windows_preflight_launcher(workspace: Path) -> str:
    compose = workspace / "compose.yaml"
    return (
        "@echo off\r\n"
        "setlocal\r\n"
        "if \"%~1\"==\"\" (echo Usage: START-PREFLIGHT.cmd C:\\path\\to\\anthropic-api-key.txt 1>&2 & exit /b 64)\r\n"
        "if not exist \"%~1\" (echo API key file does not exist 1>&2 & exit /b 66)\r\n"
        "for %%I in (\"%~1\") do set \"ANTHROPIC_API_KEY_FILE=%%~fI\"\r\n"
        "set \"REVIEWER_OUTPUT_DIR=NUL\"\r\n"
        f"docker compose --project-directory \"{workspace}\" -f \"{compose}\" build reviewer egress-proxy\r\n"
        "if errorlevel 1 exit /b %errorlevel%\r\n"
        f"docker compose --project-directory \"{workspace}\" -f \"{compose}\" run --rm preflight\r\n"
        "set \"PREFLIGHT_EXIT=%errorlevel%\"\r\n"
        f"docker compose --project-directory \"{workspace}\" -f \"{compose}\" down -v\r\n"
        "exit /b %PREFLIGHT_EXIT%\r\n"
    )


def prepare_handoff(
    bundle: Path,
    output_root: Path,
    phase: str,
    run_id: str,
    results_root: Path | None = None,
) -> Path:
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError("Run ID must contain 1-64 safe filename characters")
    bundle, bundle_manifest, _ = validate_bundle(bundle)
    workspace = Path(output_root).resolve() / run_id
    result_base = Path(results_root).resolve() if results_root else Path(output_root).resolve().parent / "reviewer-results"
    output_directory = result_base / run_id
    if workspace.exists():
        raise ValueError("Reviewer handoff workspace already exists")
    if output_directory.exists():
        raise ValueError("Reviewer result directory already exists")

    input_directory = workspace / "input"
    approval_directory = workspace / "approval"
    launch_directory = workspace / "launch"
    preflight_directory = workspace / "preflight"
    preflight_output_directory = workspace / "preflight-output"
    shutil.copytree(bundle, input_directory)
    output_directory.mkdir(parents=True)
    approval_directory.mkdir(parents=True)
    launch_directory.mkdir()
    preflight_directory.mkdir()
    preflight_output_directory.mkdir()
    for path in input_directory.rglob("*"):
        if path.is_file():
            path.chmod(0o444)

    shutil.copytree(ROOT / "reviewer" / "runtime", workspace / "runtime")
    shutil.copytree(ROOT / "reviewer" / "egress", workspace / "egress")
    runtime = read_json(RUNTIME_PROFILE_PATH)
    egress = read_json(EGRESS_PROFILE_PATH)
    plan = build_handoff_plan(input_directory, output_directory, phase)
    command = shlex.join(claude_arguments(phase))
    (launch_directory / "launch.sh").write_text(
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
    probe_value = "REVIEWER_READ_CHANNEL_OK_8D2F4A61"
    (preflight_directory / "read-probe.txt").write_text(
        probe_value + "\n", encoding="utf-8", newline="\n"
    )
    (launch_directory / "preflight.sh").write_text(
        "#!/bin/sh\nset -eu\n"
        "test \"$(cat /review/input/read-probe.txt)\" = \"REVIEWER_READ_CHANNEL_OK_8D2F4A61\"\n"
        "rm -f /review/output/write-probe.txt\n"
        "exec timeout --signal=TERM --kill-after=5s 120s /usr/local/bin/reviewer-credential-exec "
        "claude --restricted --bare --print --no-session-persistence --max-turns 3 --max-budget-usd 0.05 "
        "--add-dir /review/output --model claude-sonnet-5 --permission-mode dontAsk --tools Read,Edit --allowedTools Read,Edit "
        "--disallowedTools Bash,Glob,Grep,WebFetch,WebSearch,mcp__* -- "
        "\"Use Read to read read-probe.txt. Use Edit to create /review/output/write-probe.txt with its exact single-line content. Then return only the same content.\"\n",
        encoding="utf-8", newline="\n",
    )
    write_json(approval_directory / "manual-launch-approval.json", {
        "schema_version": "1.0", "status": "awaiting_security_engineer_approval",
        "manual_launch_approved": False, "approved_by": None,
        "approved_at_utc": None, "handoff_manifest_sha256": None,
    })
    (workspace / "compose.yaml").write_text(
        _compose_text(runtime["image"], egress["image"]), encoding="utf-8", newline="\n"
    )
    (workspace / "START-CLAUDE.cmd").write_text(
        _windows_launcher(workspace, output_directory), encoding="utf-8", newline=""
    )
    (workspace / "START-PREFLIGHT.cmd").write_text(
        _windows_preflight_launcher(workspace), encoding="utf-8", newline=""
    )

    manifest = {
        **plan,
        "run_id": run_id,
        "created_at_utc": utc_now(),
        "bundle_id": bundle_manifest["bundle_id"],
        "bundle_manifest_sha256": sha256(input_directory / "bundle-manifest.json"),
        "compose_file": "compose.yaml",
        "approval_file": "approval/manual-launch-approval.json",
        "windows_launcher": "START-CLAUDE.cmd",
        "preflight_launcher": "START-PREFLIGHT.cmd",
        "preflight_expected_output": probe_value,
        "preflight_has_bundle_access": False,
        "preflight_write_probe": "preflight-output/write-probe.txt",
        "manual_launch_command": f'{workspace / "START-CLAUDE.cmd"} "C:\\secure\\anthropic-api-key.txt"',
        "output_directory": str(output_directory),
        "expected_outputs": plan["required_outputs"],
    }
    write_json(workspace / "handoff-manifest.json", manifest)
    (workspace / "MANUAL-LAUNCH.txt").write_text(
        "SECURITY ENGINEER ONLY. Do not run before approval.\n\n"
        "Keep the API key file outside this repository, then run this single command in Windows Terminal:\n"
        f"{manifest['manual_launch_command']}\n\n"
        f"Static review results remain in:\n{output_directory}\n",
        encoding="utf-8", newline="\n",
    )
    return workspace


def approve_manual_launch(workspace: Path, approver: str) -> dict:
    workspace = Path(workspace).resolve()
    manifest_path = workspace / "handoff-manifest.json"
    approval_path = workspace / "approval" / "manual-launch-approval.json"
    if not manifest_path.is_file() or not approval_path.is_file():
        raise ValueError("Prepared handoff manifest or approval file is missing")
    if read_json(approval_path).get("manual_launch_approved") is not False:
        raise ValueError("Manual launch approval has already been recorded")
    approval = {
        "schema_version": "1.0", "status": "approved_for_security_engineer_manual_launch",
        "manual_launch_approved": True, "approved_by": approver,
        "approved_at_utc": utc_now(), "handoff_manifest_sha256": sha256(manifest_path),
    }
    write_json(approval_path, approval)
    return approval


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="operation", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--bundle", type=Path, required=True)
    prepare.add_argument("--output-root", type=Path, default=DEFAULT_HANDOFF_ROOT)
    prepare.add_argument("--results-root", type=Path, default=DEFAULT_RESULTS_ROOT)
    prepare.add_argument("--run-id", required=True)
    prepare.add_argument("--phase", choices=tuple(read_json(PROFILE_PATH)["phases"]), required=True)
    approve = subparsers.add_parser("approve-manual-launch")
    approve.add_argument("--workspace", type=Path, required=True)
    approve.add_argument("--approver", required=True)
    args = parser.parse_args()
    if args.operation == "prepare":
        workspace = prepare_handoff(args.bundle, args.output_root, args.phase, args.run_id, args.results_root)
        print(f"Prepared interactive static-review handoff without launching Docker or Claude: {workspace}")
    else:
        print(json.dumps(approve_manual_launch(args.workspace, args.approver), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

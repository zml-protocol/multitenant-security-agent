"""Build and, only after every gate is approved, supervise a Claude reviewer run."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
import uuid

from reviewer.auth_budget.gate import planning_cost, read_profile as read_auth_profile, validate_profile
from reviewer.start_approval import validate_authorized_start


ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = Path(__file__).with_name("profile.json")
RUNTIME_PROFILE_PATH = ROOT / "reviewer" / "runtime" / "profile.json"
EGRESS_PROFILE_PATH = ROOT / "reviewer" / "egress" / "profile.json"
START_GATE_PATH = ROOT / "assessment" / "appsec" / "v1" / "start-gate.json"


def read_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


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
    profile, prompt_path, schema_path = phase_configuration(phase)
    auth = read_auth_profile()
    validate_profile(auth)
    schema = json.dumps(read_json(schema_path), separators=(",", ":"))
    prompt = prompt_path.read_text(encoding="utf-8").strip()
    budget = auth["budget"]
    return [
        "claude",
        "--print",
        "--restricted",
        "--bare",
        "--disable-slash-commands",
        "--no-chrome",
        "--model", auth["model"]["model_id"],
        "--max-budget-usd", budget["maximum_approved_cost_usd"],
        "--max-turns", str(budget["maximum_agentic_turns"]),
        "--output-format", "json",
        "--json-schema", schema,
        "--no-session-persistence",
        "--permission-prompts", profile["permission_prompts"],
        "--tools", ",".join(profile["allowed_tools"]),
        "--disallowedTools", "mcp__*",
        prompt,
    ]


def build_execution_plan(input_directory: Path, output_directory: Path, phase: str) -> dict:
    profile, prompt_path, schema_path = phase_configuration(phase)
    auth = read_auth_profile()
    validate_profile(auth)
    runtime = read_json(RUNTIME_PROFILE_PATH)
    egress = read_json(EGRESS_PROFILE_PATH)
    command = claude_arguments(phase)
    return {
        "schema_version": "1.0",
        "phase": phase,
        "execution_authorized": False,
        "network_mode": profile["network_mode"],
        "source_repository_mounted": False,
        "credential": {
            "source": "runtime_read_only_secret_file",
            "container_path": profile["credential_file_in_container"],
            "value_in_command_or_plan": False,
        },
        "runtime": {
            "image": runtime["image"],
            "claude_code_version": runtime["claude_code_version"],
            "container_user": runtime["container_user"],
        },
        "egress": {
            "image": egress["image"],
            "allowed_connect_targets": egress["allowed_connect_targets"],
            "proxy_url": profile["proxy_url"],
            "direct_egress_allowed": False,
        },
        "model": auth["model"]["model_id"],
        "budget": {
            **{
                field: auth["budget"][field]
                for field in (
                    "maximum_aggregate_input_tokens",
                    "maximum_aggregate_output_tokens",
                    "maximum_model_api_calls",
                    "maximum_agentic_turns",
                    "maximum_supplemental_tool_calls",
                    "maximum_run_duration_seconds",
                    "maximum_approved_cost_usd",
                    "currency",
                )
            },
            "standard_planning_cost_usd": str(planning_cost(auth)),
        },
        "prompt": prompt_path.relative_to(ROOT).as_posix(),
        "output_schema": schema_path.relative_to(ROOT).as_posix(),
        "command": command,
        "docker_template": {
            "internal_network": "<ephemeral-internal-network>",
            "credential_mount_source": "<ephemeral-secret-file-path>",
            "input_mount_source": str(Path(input_directory).resolve()),
            "output_mount_source": str(Path(output_directory).resolve()),
        },
    }


def assert_execution_authorized() -> None:
    execution = read_json(PROFILE_PATH)
    runtime = read_json(RUNTIME_PROFILE_PATH)
    egress = read_json(EGRESS_PROFILE_PATH)
    auth = read_auth_profile()
    start = read_json(START_GATE_PATH)
    validate_profile(auth)
    checks = {
        "execution profile": execution.get("formal_execution_authorized"),
        "runtime profile": runtime.get("formal_execution_authorized"),
        "egress profile": egress.get("formal_execution_authorized"),
        "egress activation": egress.get("active_in_reviewer_runner"),
        "credential approval": auth["approval"].get("approved"),
        "model invocation": auth.get("model_invocation_enabled"),
        "formal start gate": start.get("formal_execution_authorized"),
    }
    missing = [name for name, value in checks.items() if value is not True]
    if missing:
        raise PermissionError("Formal reviewer execution is not authorized: " + ", ".join(missing))
    validate_authorized_start()


def _run(command: list[str], *, capture: bool = False, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=check, text=True, capture_output=capture)


def _image_id(image: str) -> str:
    return _run(["docker", "image", "inspect", "--format", "{{.Id}}", image], capture=True).stdout.strip()


def _supervised_container(command: list[str], container_name: str, directory: Path, timeout: int, maximum_bytes: int):
    stdout_path = directory / "claude.stdout"
    stderr_path = directory / "claude.stderr"
    started = time.monotonic()
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr)
        while process.poll() is None:
            if time.monotonic() - started > timeout:
                _run(["docker", "rm", "--force", container_name], capture=True, check=False)
                process.kill()
                raise TimeoutError("Claude reviewer exceeded the approved duration")
            if stdout_path.stat().st_size + stderr_path.stat().st_size > maximum_bytes:
                _run(["docker", "rm", "--force", container_name], capture=True, check=False)
                process.kill()
                raise RuntimeError("Claude reviewer exceeded the captured-output limit")
            time.sleep(0.1)
        if process.returncode != 0:
            raise RuntimeError(f"Claude reviewer exited with code {process.returncode}")
    return stdout_path, stderr_path


def execute(input_directory: Path, output_directory: Path, credential_file: Path, phase: str) -> dict:
    """Run only after the separately approved formal start gate is complete."""
    assert_execution_authorized()
    if shutil.which("docker") is None:
        raise RuntimeError("docker was not found")
    input_directory = Path(input_directory).resolve()
    output_directory = Path(output_directory).resolve()
    credential_file = Path(credential_file).resolve()
    if not input_directory.is_dir() or not output_directory.is_dir() or not credential_file.is_file():
        raise ValueError("Input, output, or credential path is invalid")
    if credential_file.is_relative_to(input_directory) or credential_file.is_relative_to(output_directory):
        raise ValueError("Credential file must remain outside reviewer input and output")

    execution = read_json(PROFILE_PATH)
    runtime = read_json(RUNTIME_PROFILE_PATH)
    egress = read_json(EGRESS_PROFILE_PATH)
    auth = read_auth_profile()
    suffix = uuid.uuid4().hex[:12]
    internal = f"reviewer-formal-internal-{suffix}"
    outbound = f"reviewer-formal-outbound-{suffix}"
    proxy_name = f"reviewer-formal-egress-{suffix}"
    reviewer_name = f"reviewer-formal-{suffix}"
    evidence = output_directory / ".supervisor"
    evidence.mkdir(exist_ok=False)
    created_networks: list[str] = []
    proxy_started = False
    try:
        _run(["docker", "network", "create", "--internal", internal])
        created_networks.append(internal)
        _run(["docker", "network", "create", outbound])
        created_networks.append(outbound)
        _run([
            "docker", "run", "--detach", "--name", proxy_name,
            "--read-only", "--user", egress["container_user"],
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
            "--pids-limit", "64", "--memory", "128m", "--cpus", "0.5",
            "--network", outbound,
            "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=8m,uid=10002,gid=10002,mode=0700",
            _image_id(egress["image"]),
        ])
        proxy_started = True
        _run(["docker", "network", "connect", "--alias", "egress-proxy", internal, proxy_name])

        reviewer = [
            "docker", "run", "--rm", "--name", reviewer_name, "--read-only",
            "--user", runtime["container_user"], "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true", "--pids-limit", "128",
            "--memory", "1g", "--cpus", "1", "--network", internal,
            "--env", f"HTTPS_PROXY={execution['proxy_url']}",
            "--env", f"HTTP_PROXY={execution['proxy_url']}",
            "--env", "NO_PROXY=",
            "--env", f"REVIEWER_CREDENTIAL_FILE={execution['credential_file_in_container']}",
            "--tmpfs", "/run/claude-config:rw,noexec,nosuid,nodev,size=16m,uid=10001,gid=10001,mode=0700",
            "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=16m,uid=10001,gid=10001,mode=0700",
            "--mount", f"type=bind,src={input_directory},dst=/review/input,readonly",
            "--mount", f"type=bind,src={output_directory},dst=/review/output",
            "--mount", f"type=bind,src={credential_file},dst={execution['credential_file_in_container']},readonly",
            "--workdir", "/review/input",
            "--entrypoint", execution["credential_wrapper"],
            _image_id(runtime["image"]),
            *claude_arguments(phase),
        ]
        stdout_path, stderr_path = _supervised_container(
            reviewer,
            reviewer_name,
            evidence,
            auth["budget"]["maximum_run_duration_seconds"],
            execution["maximum_captured_output_bytes"],
        )
        secret = credential_file.read_text(encoding="utf-8").strip()
        combined = stdout_path.read_bytes() + stderr_path.read_bytes()
        proxy_logs = _run(["docker", "logs", proxy_name], capture=True).stdout
        if secret.encode() in combined or secret in proxy_logs:
            raise RuntimeError("Credential value entered reviewer or proxy output")
        envelope = json.loads(stdout_path.read_text(encoding="utf-8"))
        structured = envelope.get("structured_output")
        if not isinstance(structured, dict):
            raise RuntimeError("Claude result did not contain structured_output")
        result_path = output_directory / "phase-result.json"
        result_path.write_text(json.dumps(structured, indent=2) + "\n", encoding="utf-8")
        record = {
            "schema_version": "1.0",
            "phase": phase,
            "completed_at_utc": utc_now(),
            "runtime_image_id": _image_id(runtime["image"]),
            "egress_image_id": _image_id(egress["image"]),
            "model": auth["model"]["model_id"],
            "result_sha256": sha256(result_path),
            "credential_value_persisted": False,
        }
        (output_directory / "execution-record.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        return record
    finally:
        _run(["docker", "rm", "--force", reviewer_name], capture=True, check=False)
        if proxy_started:
            _run(["docker", "rm", "--force", proxy_name], capture=True, check=False)
        for network in reversed(created_networks):
            _run(["docker", "network", "rm", network], capture=True, check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="operation", required=True)
    plan = subparsers.add_parser("plan")
    plan.add_argument("--input", type=Path, required=True)
    plan.add_argument("--output", type=Path, required=True)
    plan.add_argument("--phase", choices=tuple(read_json(PROFILE_PATH)["phases"]), required=True)
    run = subparsers.add_parser("execute")
    run.add_argument("--input", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--credential-file", type=Path, required=True)
    run.add_argument("--phase", choices=tuple(read_json(PROFILE_PATH)["phases"]), required=True)
    args = parser.parse_args()
    if args.operation == "plan":
        print(json.dumps(build_execution_plan(args.input, args.output, args.phase), indent=2))
    else:
        print(json.dumps(execute(args.input, args.output, args.credential_file, args.phase), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

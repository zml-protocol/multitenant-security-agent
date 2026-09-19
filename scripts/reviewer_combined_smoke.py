"""Verify the combined runtime, secret-file, and proxy-only reviewer boundary without a model call."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

from scripts.reviewer_egress_smoke import parse_probe, probe_arguments


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIRECTORY = ROOT / "reviewer" / "runtime"
EGRESS_DIRECTORY = ROOT / "reviewer" / "egress"
RUNTIME_PROFILE = RUNTIME_DIRECTORY / "profile.json"
EGRESS_PROFILE = EGRESS_DIRECTORY / "profile.json"
EXECUTION_PROFILE = ROOT / "reviewer" / "execution" / "profile.json"
RESULT_ROOT = ROOT / ".local" / "reviewer-combined"
SECRET_ROOT = ROOT / ".local" / "reviewer-secrets"


def run(command, *, capture=False, check=True, timeout=None):
    try:
        return subprocess.run(
            command,
            check=check,
            text=True,
            capture_output=capture,
            timeout=timeout,
        )
    except subprocess.CalledProcessError as error:
        if capture:
            if error.stdout:
                print(error.stdout, end="")
            if error.stderr:
                print(error.stderr, end="", file=sys.stderr)
        raise


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    if shutil.which("docker") is None:
        raise SystemExit("docker was not found")
    runtime = read_json(RUNTIME_PROFILE)
    egress = read_json(EGRESS_PROFILE)
    execution = read_json(EXECUTION_PROFILE)
    if any((runtime["formal_execution_authorized"], egress["formal_execution_authorized"], execution["formal_execution_authorized"])):
        raise SystemExit("combined smoke requires every formal execution gate to remain closed")

    run([
        "docker", "build", "--provenance=false",
        "--build-arg", f"CLAUDE_CODE_VERSION={runtime['claude_code_version']}",
        "--tag", runtime["image"], str(RUNTIME_DIRECTORY),
    ])
    run(["docker", "build", "--provenance=false", "--tag", egress["image"], str(EGRESS_DIRECTORY)])
    runtime_id = run(["docker", "image", "inspect", "--format", "{{.Id}}", runtime["image"]], capture=True).stdout.strip()
    egress_id = run(["docker", "image", "inspect", "--format", "{{.Id}}", egress["image"]], capture=True).stdout.strip()
    doctor = run([
        "docker", "run", "--rm", "--read-only", "--user", runtime["container_user"],
        "--network", "none",
        "--tmpfs", "/run/claude-config:rw,noexec,nosuid,nodev,size=8m,uid=10001,gid=10001,mode=0700",
        "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=8m,uid=10001,gid=10001,mode=0700",
        runtime_id, "doctor",
    ], capture=True, timeout=30)
    if "No installation issues found." not in doctor.stdout or "Auto-updates: disabled" not in doctor.stdout:
        raise RuntimeError("Claude doctor did not accept the managed runtime configuration")

    suffix = uuid.uuid4().hex[:12]
    sentinel = f"sk-ant-synthetic-{uuid.uuid4().hex}{uuid.uuid4().hex}"
    secret_directory = SECRET_ROOT / suffix
    secret_directory.mkdir(parents=True, exist_ok=False)
    secret_file = secret_directory / "anthropic_api_key"
    secret_file.write_text(sentinel + "\n", encoding="utf-8")
    internal = f"reviewer-combined-internal-{suffix}"
    outbound = f"reviewer-combined-outbound-{suffix}"
    proxy_name = f"reviewer-combined-egress-{suffix}"
    reviewer_name = f"reviewer-combined-runtime-{suffix}"
    created_networks = []
    proxy_started = False
    reviewer_created = False
    try:
        run(["docker", "network", "create", "--internal", internal])
        created_networks.append(internal)
        run(["docker", "network", "create", outbound])
        created_networks.append(outbound)
        run([
            "docker", "run", "--detach", "--name", proxy_name,
            "--read-only", "--user", egress["container_user"],
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
            "--pids-limit", "64", "--memory", "128m", "--cpus", "0.5",
            "--network", outbound,
            "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=8m,uid=10002,gid=10002,mode=0700",
            egress_id,
        ])
        proxy_started = True
        run(["docker", "network", "connect", "--alias", "egress-proxy", internal, proxy_name])
        time.sleep(0.5)

        run([
            "docker", "create", "--name", reviewer_name, "--read-only",
            "--user", runtime["container_user"], "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true", "--pids-limit", "64",
            "--memory", "256m", "--cpus", "0.5", "--network", internal,
            "--env", f"HTTPS_PROXY={execution['proxy_url']}",
            "--env", f"HTTP_PROXY={execution['proxy_url']}",
            "--env", "NO_PROXY=",
            "--env", f"REVIEWER_CREDENTIAL_FILE={execution['credential_file_in_container']}",
            "--tmpfs", "/run/claude-config:rw,noexec,nosuid,nodev,size=8m,uid=10001,gid=10001,mode=0700",
            "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=8m,uid=10001,gid=10001,mode=0700",
            "--mount", f"type=bind,src={secret_file.resolve()},dst={execution['credential_file_in_container']},readonly",
            "--entrypoint", execution["credential_wrapper"],
            runtime_id, "/usr/local/bin/reviewer-credential-probe",
        ], capture=True)
        reviewer_created = True
        inspect = run(["docker", "inspect", reviewer_name], capture=True).stdout
        if sentinel in inspect:
            raise RuntimeError("Synthetic credential entered Docker inspect metadata")
        probe_output = run(["docker", "start", "--attach", reviewer_name], capture=True, timeout=20).stdout
        probe = json.loads(probe_output.strip().splitlines()[-1])
        if probe != {
            "credential_present_in_wrapper": True,
            "sensitive_environment_present_in_probe_child": False,
            "managed_settings_valid": True,
        }:
            raise RuntimeError(f"Credential/runtime probe failed: {probe}")
        if sentinel in probe_output:
            raise RuntimeError("Synthetic credential entered reviewer output")

        allowed = parse_probe(run(probe_arguments(internal, runtime_id, "allowed"), capture=True))
        blocked = parse_probe(run(probe_arguments(internal, runtime_id, "blocked"), capture=True))
        direct = parse_probe(run(probe_arguments(internal, runtime_id, "direct"), capture=True))
        proxy_logs = run(["docker", "logs", proxy_name], capture=True).stdout
        if sentinel in proxy_logs:
            raise RuntimeError("Synthetic credential entered proxy logs")

        result = {
            "schema_version": "1.0",
            "status": "passed",
            "tested_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "runtime_image_id": runtime_id,
            "egress_image_id": egress_id,
            "real_credential_used": False,
            "model_invoked": False,
            "formal_execution_authorized": False,
            "observations": {
                "credential_loaded_only_inside_wrapper": True,
                "credential_absent_from_docker_inspect": True,
                "credential_absent_from_probe_child": True,
                "credential_absent_from_output_and_proxy_logs": True,
                "managed_settings_file_validated": True,
                "claude_doctor_no_installation_issues": True,
                "allowlisted_tls_connect": allowed,
                "non_allowlisted_connect": blocked,
                "direct_reviewer_egress": direct,
            },
        }
        result_directory = RESULT_ROOT / f"smoke-{suffix}"
        result_directory.mkdir(parents=True, exist_ok=False)
        result_path = result_directory / "result.json"
        result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        if sentinel in result_path.read_text(encoding="utf-8"):
            raise RuntimeError("Synthetic credential entered persisted smoke evidence")
        print(json.dumps(result, indent=2))
        print(f"result_path={result_path}")
    finally:
        if reviewer_created:
            run(["docker", "rm", "--force", reviewer_name], capture=True, check=False)
        if proxy_started:
            run(["docker", "rm", "--force", proxy_name], capture=True, check=False)
        for network in reversed(created_networks):
            run(["docker", "network", "rm", network], capture=True, check=False)
        if secret_file.exists():
            secret_file.unlink()
        if secret_directory.exists():
            secret_directory.rmdir()


if __name__ == "__main__":
    main()

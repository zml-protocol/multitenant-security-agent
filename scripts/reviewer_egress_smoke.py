"""Build and verify the inactive, credential-free reviewer egress boundary."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid


ROOT = Path(__file__).resolve().parents[1]
EGRESS_DIRECTORY = ROOT / "reviewer" / "egress"
EGRESS_PROFILE_PATH = EGRESS_DIRECTORY / "profile.json"
RUNTIME_PROFILE_PATH = ROOT / "reviewer" / "runtime" / "profile.json"
RESULT_ROOT = ROOT / ".local" / "reviewer-egress"
SENSITIVE_SENTINEL = "SMOKE_SECRET_MUST_NOT_APPEAR"


def run(command, *, capture=False, check=True):
    try:
        return subprocess.run(
            command,
            check=check,
            text=True,
            capture_output=capture,
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


def probe_arguments(network, reviewer_image_id, mode):
    return [
        "docker", "run", "--rm", "--read-only",
        "--user", "10001:10001",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges:true",
        "--pids-limit", "64",
        "--memory", "256m",
        "--cpus", "0.5",
        "--network", network,
        "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=8m,uid=10001,gid=10001,mode=0700",
        "--mount", f"type=bind,src={(EGRESS_DIRECTORY / 'smoke-client.js').resolve()},dst=/smoke/client.js,readonly",
        "--entrypoint", "node",
        reviewer_image_id,
        "/smoke/client.js", mode,
    ]


def parse_probe(completed):
    result = json.loads(completed.stdout.strip().splitlines()[-1])
    if result.get("passed") is not True:
        raise RuntimeError(f"Egress probe failed: {result}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-build", action="store_true", help="Test existing tagged images")
    args = parser.parse_args()

    if shutil.which("docker") is None:
        raise SystemExit("docker was not found")

    egress = read_json(EGRESS_PROFILE_PATH)
    runtime = read_json(RUNTIME_PROFILE_PATH)
    if egress["active_in_reviewer_runner"] or egress["formal_execution_authorized"]:
        raise SystemExit("egress profile must remain inactive and unauthorized")
    if egress["credential_injection"] != "disabled" or egress["model_invocation"] != "disabled":
        raise SystemExit("egress smoke must remain credential-free with model invocation disabled")

    if not args.skip_build:
        run([
            "docker", "build", "--provenance=false",
            "--tag", egress["image"],
            str(EGRESS_DIRECTORY),
        ])

    proxy_image_id = run(
        ["docker", "image", "inspect", "--format", "{{.Id}}", egress["image"]],
        capture=True,
    ).stdout.strip()
    reviewer_image_id = run(
        ["docker", "image", "inspect", "--format", "{{.Id}}", runtime["image"]],
        capture=True,
    ).stdout.strip()

    suffix = uuid.uuid4().hex[:12]
    internal_network = f"reviewer-internal-{suffix}"
    outbound_network = f"reviewer-outbound-{suffix}"
    proxy_container = f"reviewer-egress-{suffix}"
    created_networks = []
    started_proxy = False
    try:
        run(["docker", "network", "create", "--internal", internal_network])
        created_networks.append(internal_network)
        run(["docker", "network", "create", outbound_network])
        created_networks.append(outbound_network)
        run([
            "docker", "run", "--detach", "--name", proxy_container,
            "--read-only", "--user", egress["container_user"],
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true",
            "--pids-limit", "64", "--memory", "128m", "--cpus", "0.5",
            "--network", outbound_network,
            "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=8m,uid=10002,gid=10002,mode=0700",
            proxy_image_id,
        ])
        started_proxy = True
        run(["docker", "network", "connect", "--alias", "egress-proxy", internal_network, proxy_container])
        time.sleep(0.5)

        allowed = parse_probe(run(probe_arguments(internal_network, reviewer_image_id, "allowed"), capture=True))
        blocked = parse_probe(run(probe_arguments(internal_network, reviewer_image_id, "blocked"), capture=True))
        direct = parse_probe(run(probe_arguments(internal_network, reviewer_image_id, "direct"), capture=True))
        logs = run(["docker", "logs", proxy_container], capture=True).stdout
        if SENSITIVE_SENTINEL in logs or "Proxy-Authorization" in logs or "X-Smoke-Sensitive" in logs:
            raise RuntimeError("proxy logs contain sensitive request header material")

        log_events = [json.loads(line) for line in logs.splitlines() if line.strip()]
        decisions = {(event.get("decision"), event.get("target")) for event in log_events}
        if ("allow", "api.anthropic.com:443") not in decisions:
            raise RuntimeError("proxy log is missing the allowed decision")
        if ("deny", "example.com:443") not in decisions:
            raise RuntimeError("proxy log is missing the denied decision")

        result = {
            "schema_version": "1.0",
            "status": "passed",
            "tested_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "profile": EGRESS_PROFILE_PATH.relative_to(ROOT).as_posix(),
            "proxy_image_id": proxy_image_id,
            "reviewer_image_id": reviewer_image_id,
            "formal_execution_authorized": False,
            "credential_injection": "disabled",
            "model_invoked": False,
            "observations": {
                "allowlisted_tls_connect": allowed,
                "non_allowlisted_connect": blocked,
                "direct_reviewer_egress": direct,
                "proxy_log_sensitive_material": False,
            },
        }
        result_directory = RESULT_ROOT / f"smoke-{suffix}"
        result_directory.mkdir(parents=True)
        result_path = result_directory / "result.json"
        result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
        print(f"result_path={result_path}")
    finally:
        if started_proxy:
            run(["docker", "rm", "--force", proxy_container], capture=True, check=False)
        for network in reversed(created_networks):
            run(["docker", "network", "rm", network], capture=True, check=False)


if __name__ == "__main__":
    main()

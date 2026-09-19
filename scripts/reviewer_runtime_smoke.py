"""Build and verify the credential-free, offline Claude reviewer image."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIRECTORY = ROOT / "reviewer" / "runtime"
PROFILE_PATH = RUNTIME_DIRECTORY / "profile.json"
RESULT_ROOT = ROOT / ".local" / "reviewer-runtime"


def run(command, *, capture=False):
    try:
        return subprocess.run(
            command,
            check=True,
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


def load_profile():
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def docker_arguments(image, input_directory, output_directory):
    return [
        "docker", "run", "--rm", "--read-only",
        "--user", "10001:10001",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges:true",
        "--pids-limit", "128",
        "--memory", "1g",
        "--cpus", "1",
        "--network", "none",
        "--tmpfs", "/run/claude-config:rw,noexec,nosuid,nodev,size=16m,uid=10001,gid=10001,mode=0700",
        "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=16m,uid=10001,gid=10001,mode=0700",
        "--mount", f"type=bind,src={input_directory},dst=/review/input,readonly",
        "--mount", f"type=bind,src={output_directory},dst=/review/output",
        "--workdir", "/review/input",
        "--entrypoint", "/usr/local/bin/reviewer-runtime-smoke",
        image,
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-build", action="store_true", help="Test the existing tagged image")
    args = parser.parse_args()

    if shutil.which("docker") is None:
        raise SystemExit("docker was not found")

    profile = load_profile()
    if not args.skip_build:
        run([
            "docker", "build",
            "--provenance=false",
            "--build-arg", f"CLAUDE_CODE_VERSION={profile['claude_code_version']}",
            "--tag", profile["image"],
            str(RUNTIME_DIRECTORY),
        ])

    image_id = run(
        ["docker", "image", "inspect", "--format", "{{.Id}}", profile["image"]],
        capture=True,
    ).stdout.strip()
    if not image_id.startswith("sha256:"):
        raise SystemExit("docker returned an invalid image ID")

    smoke_root = RESULT_ROOT / f"smoke-{uuid.uuid4().hex[:12]}"
    input_directory = smoke_root / "input"
    output_directory = smoke_root / "output"
    input_directory.mkdir(parents=True)
    output_directory.mkdir()
    (input_directory / "smoke-input.txt").write_text("offline runtime smoke input\n", encoding="utf-8")

    completed = run(
        docker_arguments(image_id, input_directory.resolve(), output_directory.resolve()),
        capture=True,
    )
    observation = json.loads(completed.stdout.strip().splitlines()[-1])
    if observation["claude_code_version"] != profile["claude_code_version"]:
        raise SystemExit("smoke output version differs from runtime profile")

    result = {
        "schema_version": "1.0",
        "status": "passed",
        "tested_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "profile": PROFILE_PATH.relative_to(ROOT).as_posix(),
        "image_tag": profile["image"],
        "image_id": image_id,
        "formal_execution_authorized": False,
        "credential_injection": "disabled",
        "model_invoked": False,
        "observation": observation,
    }
    result_path = smoke_root / "result.json"
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"result_path={result_path}")


if __name__ == "__main__":
    main()

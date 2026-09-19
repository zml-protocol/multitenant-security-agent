"""Prepare and enforce the two-phase, bundle-only reviewer handoff."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import uuid


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_ROOT = ROOT / ".local" / "reviewer-runs"
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
PHASE1 = "decision_path_and_independent_matrix"
PHASE2 = "difference_review"
REDACTED_AUTHORIZATION_VALUES = {"[REDACTED]", "[MISSING]"}
FORBIDDEN_RESULT_KEYS = {
    "token",
    "tokens",
    "password",
    "secret",
    "credentials",
    "credential_digest",
    "raw_response",
    "response_body",
    "name",
    "email",
    "phone",
}


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def set_read_only(path):
    path = Path(path)
    path.chmod(stat.S_IREAD)


def ensure_safe_relative(relative):
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts:
        raise ValueError(f"Unsafe manifest path: {relative}")
    return candidate


def run_path(run_directory, relative):
    run_directory = Path(run_directory).resolve()
    resolved = (run_directory / ensure_safe_relative(relative)).resolve()
    if not resolved.is_relative_to(run_directory):
        raise ValueError(f"Run manifest path escapes the run directory: {relative}")
    return resolved


def bundle_files(bundle):
    return {
        path.relative_to(bundle).as_posix()
        for path in bundle.rglob("*")
        if path.is_file()
    }


def validate_bundle(bundle):
    bundle = Path(bundle).resolve()
    if not bundle.is_dir():
        raise ValueError("Reviewer bundle directory does not exist")
    if any(path.is_symlink() for path in bundle.rglob("*")):
        raise ValueError("Reviewer bundle may not contain symbolic links")
    manifest_path = bundle / "bundle-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("Reviewer bundle manifest is missing")
    manifest = read_json(manifest_path)
    readable = manifest.get("readable_files")
    if not isinstance(readable, list) or len(readable) != len(set(readable)):
        raise ValueError("Bundle readable_files must be a unique list")
    for relative in readable:
        ensure_safe_relative(relative)
    if set(readable) != bundle_files(bundle):
        raise ValueError("Bundle files differ from the manifest allowlist")
    hashes = manifest.get("file_sha256", {})
    if set(hashes) != set(readable) - {"bundle-manifest.json"}:
        raise ValueError("Bundle hash inventory differs from the readable allowlist")
    for relative, expected in hashes.items():
        if sha256(bundle / ensure_safe_relative(relative)) != expected:
            raise ValueError(f"Bundle integrity check failed: {relative}")
    access_path = bundle / "assessment" / "reviewer-input-manifest.json"
    access = read_json(access_path)
    if access.get("version") != "2.0" or access.get("access_model") != "generated_bundle_only":
        raise ValueError("Bundle does not contain the approved reviewer access model")
    return bundle, manifest, access


def docker_plan(input_directory, output_directory, phase):
    input_directory = Path(input_directory).resolve()
    output_directory = Path(output_directory).resolve()
    return {
        "schema_version": "1.0",
        "phase": phase,
        "execution_authorized": False,
        "network_mode": "none",
        "credential_injection": "disabled",
        "source_repository_mounted": False,
        "placeholders": {
            "image": "<approved-reviewer-image>",
            "command": "<approved-reviewer-command>"
        },
        "docker_arguments_template": [
            "docker", "run", "--rm", "--read-only",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true",
            "--pids-limit", "128",
            "--memory", "1g",
            "--cpus", "1",
            "--network", "none",
            "--mount", f"type=bind,src={input_directory},dst=/review/input,readonly",
            "--mount", f"type=bind,src={output_directory},dst=/review/output",
            "--workdir", "/review/input",
            "<approved-reviewer-image>",
            "<approved-reviewer-command>"
        ]
    }


def update_run(run_directory, **changes):
    path = Path(run_directory) / "run-manifest.json"
    manifest = read_json(path)
    manifest.update(changes)
    write_json(path, manifest)
    return manifest


def prepare_run(bundle, output_root=DEFAULT_RUN_ROOT, run_id=None):
    bundle, bundle_manifest, access = validate_bundle(bundle)
    run_id = run_id or f"review-{uuid.uuid4().hex[:16]}"
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError("Run ID must be 1-64 safe filename characters")
    run_directory = Path(output_root).resolve() / run_id
    if run_directory.exists():
        raise ValueError("Reviewer run directory already exists")
    phase_directory = run_directory / "phase1"
    phase_input = phase_directory / "input"
    reviewer_output = phase_directory / "reviewer-output"
    shutil.copytree(bundle, phase_input)
    reviewer_output.mkdir(parents=True)
    validate_bundle(phase_input)
    for path in phase_input.rglob("*"):
        if path.is_file():
            set_read_only(path)
    plan = docker_plan(phase_input, reviewer_output, PHASE1)
    write_json(phase_directory / "docker-plan.json", plan)
    manifest = {
        "run_schema_version": "1.0",
        "run_id": run_id,
        "state": "phase1_prepared",
        "created_at_utc": utc_now(),
        "bundle_id": bundle_manifest["bundle_id"],
        "bundle_manifest_sha256": sha256(phase_input / "bundle-manifest.json"),
        "source_commit": bundle_manifest["source_commit"],
        "fixture_id": bundle_manifest["fixture_id"],
        "requirement_version": bundle_manifest["requirement_version"],
        "bundle_status": bundle_manifest["status"],
        "reviewer_access_version": access["version"],
        "formal_execution_authorized": False,
        "phase1_input": "phase1/input",
        "phase1_output": "phase1/reviewer-output",
        "phase1_docker_plan": "phase1/docker-plan.json"
    }
    write_json(run_directory / "run-manifest.json", manifest)
    return run_directory, manifest


def load_run(run_directory, expected_state=None):
    run_directory = Path(run_directory).resolve()
    manifest_path = run_directory / "run-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("Reviewer run manifest is missing")
    manifest = read_json(manifest_path)
    if expected_state and manifest.get("state") != expected_state:
        raise ValueError(f"Reviewer run must be in state {expected_state}")
    phase_input = run_path(run_directory, manifest["phase1_input"])
    _, bundle_manifest, _ = validate_bundle(phase_input)
    if bundle_manifest["bundle_id"] != manifest["bundle_id"]:
        raise ValueError("Run bundle ID differs from the prepared bundle")
    if sha256(phase_input / "bundle-manifest.json") != manifest["bundle_manifest_sha256"]:
        raise ValueError("Prepared bundle manifest changed after run creation")
    return run_directory, manifest


def required_phase1_outputs(run_directory):
    access = read_json(Path(run_directory) / "phase1" / "input" / "assessment" / "reviewer-input-manifest.json")
    phase = next((item for item in access["review_phases"] if item["phase"] == PHASE1), None)
    if phase is None:
        raise ValueError("Phase 1 is missing from the reviewer access manifest")
    return phase["required_outputs"]


def validate_phase1_submission(run_directory, submission):
    if not isinstance(submission, dict):
        raise ValueError("Phase 1 submission must be a JSON object")
    required = required_phase1_outputs(run_directory)
    missing = [key for key in required if key not in submission]
    if missing:
        raise ValueError(f"Phase 1 submission is missing required outputs: {', '.join(missing)}")
    if not submission["authentication_authorization_decision_path"]:
        raise ValueError("Decision path may not be empty")
    if not submission["independent_test_matrix"]:
        raise ValueError("Independent test matrix may not be empty")
    if not isinstance(submission["limitations_and_unexecuted_tests"], list):
        raise ValueError("Limitations and unexecuted tests must be a list")


def seal_phase1(run_directory, submission_path):
    run_directory, manifest = load_run(run_directory, "phase1_prepared")
    submission_path = Path(submission_path).resolve()
    reviewer_output = run_path(run_directory, manifest["phase1_output"])
    if not submission_path.is_file() or not submission_path.is_relative_to(reviewer_output):
        raise ValueError("Phase 1 submission must be a file in the isolated reviewer output directory")
    submission = read_json(submission_path)
    validate_phase1_submission(run_directory, submission)
    sealed_path = run_directory / "phase1" / "sealed-output.json"
    write_json(sealed_path, submission)
    output_hash = sha256(sealed_path)
    seal = {
        "seal_schema_version": "1.0",
        "run_id": manifest["run_id"],
        "phase": PHASE1,
        "sealed_at_utc": utc_now(),
        "bundle_id": manifest["bundle_id"],
        "bundle_manifest_sha256": manifest["bundle_manifest_sha256"],
        "sealed_output": "sealed-output.json",
        "sealed_output_sha256": output_hash,
        "integrity_model": "read_only_copy_with_sha256_verification"
    }
    seal_path = run_directory / "phase1" / "seal.json"
    write_json(seal_path, seal)
    set_read_only(sealed_path)
    set_read_only(seal_path)
    update_run(
        run_directory,
        state="phase1_sealed",
        phase1_sealed_output="phase1/sealed-output.json",
        phase1_seal="phase1/seal.json",
        phase1_sealed_output_sha256=output_hash,
    )
    return seal


def verify_phase1_seal(run_directory):
    run_directory, manifest = load_run(run_directory)
    if manifest.get("state") not in {"phase1_sealed", "phase2_staged", "phase2_authorized", "phase2_released"}:
        raise ValueError("Phase 1 has not been sealed")
    seal_path = run_path(run_directory, manifest["phase1_seal"])
    sealed_path = run_path(run_directory, manifest["phase1_sealed_output"])
    seal = read_json(seal_path)
    if seal["run_id"] != manifest["run_id"] or seal["bundle_id"] != manifest["bundle_id"]:
        raise ValueError("Phase 1 seal identity does not match the run")
    if sha256(sealed_path) != seal["sealed_output_sha256"]:
        raise ValueError("Phase 1 sealed output failed integrity verification")
    if seal["sealed_output_sha256"] != manifest["phase1_sealed_output_sha256"]:
        raise ValueError("Phase 1 seal hash differs from the run manifest")
    return seal


def validate_authorization_matrix(run_directory, permissions):
    fixture = read_json(Path(run_directory) / "phase1" / "input" / "inputs" / "fixture.json")
    aliases = [user["alias"] for user in fixture["users"]]
    if set(permissions) != {"version", "aliases", "detail_allow", "list_allow"}:
        raise ValueError("Authorization matrix does not use the approved schema")
    if permissions["aliases"] != aliases or len(set(aliases)) != 6:
        raise ValueError("Authorization matrix must match the six approved aliases in order")
    for field in ("detail_allow", "list_allow"):
        mapping = permissions[field]
        if set(mapping) != set(aliases):
            raise ValueError(f"Authorization matrix {field} keys must match the approved aliases")
        for actor, allowed in mapping.items():
            if not isinstance(allowed, list) or len(allowed) != len(set(allowed)) or not set(allowed) <= set(aliases):
                raise ValueError(f"Authorization matrix contains invalid values for {field}.{actor}")


def stage_phase2(run_directory, permissions_path, results_path):
    run_directory, manifest = load_run(run_directory, "phase1_sealed")
    verify_phase1_seal(run_directory)
    permissions = read_json(permissions_path)
    results = read_json(results_path)
    validate_authorization_matrix(run_directory, permissions)
    validate_redacted_results(results)
    staged = run_directory / "phase2" / "staged"
    if staged.exists():
        raise ValueError("Phase 2 staging directory already exists")
    staged.mkdir(parents=True)
    matrix_path = staged / "authorization-matrix.json"
    results_copy = staged / "deterministic-results.json"
    write_json(matrix_path, permissions)
    write_json(results_copy, results)
    staging = {
        "staging_schema_version": "1.0",
        "run_id": manifest["run_id"],
        "staged_at_utc": utc_now(),
        "phase1_output_sha256": manifest["phase1_sealed_output_sha256"],
        "authorization_matrix_sha256": sha256(matrix_path),
        "deterministic_results_sha256": sha256(results_copy),
        "files": ["authorization-matrix.json", "deterministic-results.json"]
    }
    staging_path = staged / "staging-manifest.json"
    write_json(staging_path, staging)
    for path in staged.iterdir():
        set_read_only(path)
    update_run(
        run_directory,
        state="phase2_staged",
        phase2_staged="phase2/staged",
        phase2_staging_manifest="phase2/staged/staging-manifest.json",
        phase2_staging_manifest_sha256=sha256(staging_path),
    )
    return staging


def verify_phase2_staging(run_directory, manifest):
    staging_path = run_path(run_directory, manifest["phase2_staging_manifest"])
    if sha256(staging_path) != manifest["phase2_staging_manifest_sha256"]:
        raise ValueError("Phase 2 staging manifest failed integrity verification")
    staging = read_json(staging_path)
    staged = run_path(run_directory, manifest["phase2_staged"])
    if staging.get("run_id") != manifest["run_id"]:
        raise ValueError("Phase 2 staging run ID does not match")
    if staging.get("phase1_output_sha256") != manifest["phase1_sealed_output_sha256"]:
        raise ValueError("Phase 2 staging references a different phase 1 output")
    if set(staging.get("files", [])) != {"authorization-matrix.json", "deterministic-results.json"}:
        raise ValueError("Phase 2 staging file list is invalid")
    if sha256(staged / "authorization-matrix.json") != staging["authorization_matrix_sha256"]:
        raise ValueError("Staged authorization matrix failed integrity verification")
    if sha256(staged / "deterministic-results.json") != staging["deterministic_results_sha256"]:
        raise ValueError("Staged deterministic results failed integrity verification")
    return staging


def authorize_phase2(run_directory, approved_by, reason):
    run_directory, manifest = load_run(run_directory, "phase2_staged")
    if not approved_by.strip() or not reason.strip():
        raise ValueError("Phase 2 authorization requires an approver and reason")
    verify_phase1_seal(run_directory)
    verify_phase2_staging(run_directory, manifest)
    seal_path = run_path(run_directory, manifest["phase1_seal"])
    authorization = {
        "authorization_schema_version": "1.0",
        "run_id": manifest["run_id"],
        "decision": "approved",
        "approved_by": approved_by,
        "approved_at_utc": utc_now(),
        "reason": reason,
        "phase1_seal_sha256": sha256(seal_path),
        "phase1_output_sha256": manifest["phase1_sealed_output_sha256"],
        "phase2_staging_manifest_sha256": manifest["phase2_staging_manifest_sha256"]
    }
    authorization_path = run_directory / "phase2" / "authorization.json"
    write_json(authorization_path, authorization)
    set_read_only(authorization_path)
    update_run(
        run_directory,
        state="phase2_authorized",
        phase2_authorization="phase2/authorization.json",
        phase2_authorization_sha256=sha256(authorization_path),
    )
    return authorization


def validate_redacted_results(value, path="results"):
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = key.lower()
            child_path = f"{path}.{key}"
            if normalized == "authorization":
                if child not in REDACTED_AUTHORIZATION_VALUES:
                    raise ValueError(f"Unredacted Authorization value at {child_path}")
            elif normalized in FORBIDDEN_RESULT_KEYS:
                raise ValueError(f"Forbidden sensitive result field at {child_path}")
            validate_redacted_results(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            validate_redacted_results(child, f"{path}[{index}]")
    elif isinstance(value, str) and re.search(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+", value):
        raise ValueError(f"Possible raw bearer token at {path}")


def verify_authorization(run_directory, manifest):
    authorization_path = run_path(run_directory, manifest["phase2_authorization"])
    if sha256(authorization_path) != manifest["phase2_authorization_sha256"]:
        raise ValueError("Phase 2 authorization failed integrity verification")
    authorization = read_json(authorization_path)
    if authorization.get("decision") != "approved" or authorization.get("run_id") != manifest["run_id"]:
        raise ValueError("Phase 2 authorization is invalid")
    if authorization["phase1_output_sha256"] != manifest["phase1_sealed_output_sha256"]:
        raise ValueError("Phase 2 authorization references a different phase 1 output")
    if authorization["phase1_seal_sha256"] != sha256(run_path(run_directory, manifest["phase1_seal"])):
        raise ValueError("Phase 2 authorization references a different phase 1 seal")
    if authorization["phase2_staging_manifest_sha256"] != manifest["phase2_staging_manifest_sha256"]:
        raise ValueError("Phase 2 authorization references different staged inputs")
    return authorization


def release_phase2(run_directory):
    run_directory, manifest = load_run(run_directory, "phase2_authorized")
    verify_phase1_seal(run_directory)
    verify_phase2_staging(run_directory, manifest)
    authorization = verify_authorization(run_directory, manifest)

    phase2 = run_directory / "phase2"
    phase_input = phase2 / "input"
    if phase_input.exists():
        raise ValueError("Phase 2 input already exists")
    shutil.copytree(run_path(run_directory, manifest["phase1_input"]), phase_input / "bundle")
    shutil.copy2(run_path(run_directory, manifest["phase1_sealed_output"]), phase_input / "phase1-output.json")
    staged = run_path(run_directory, manifest["phase2_staged"])
    shutil.copy2(staged / "authorization-matrix.json", phase_input / "authorization-matrix.json")
    shutil.copy2(staged / "deterministic-results.json", phase_input / "deterministic-results.json")
    content_files = sorted(
        path.relative_to(phase_input).as_posix()
        for path in phase_input.rglob("*")
        if path.is_file()
    )
    hashes = {relative: sha256(phase_input / relative) for relative in content_files}
    release = {
        "release_schema_version": "1.0",
        "run_id": manifest["run_id"],
        "phase": PHASE2,
        "released_at_utc": utc_now(),
        "approved_by": authorization["approved_by"],
        "authorization_sha256": manifest["phase2_authorization_sha256"],
        "staging_manifest_sha256": manifest["phase2_staging_manifest_sha256"],
        "phase1_output_sha256": manifest["phase1_sealed_output_sha256"],
        "readable_files": ["release-manifest.json", *content_files],
        "file_sha256": hashes
    }
    write_json(phase_input / "release-manifest.json", release)
    for path in phase_input.rglob("*"):
        if path.is_file():
            set_read_only(path)
    reviewer_output = phase2 / "reviewer-output"
    reviewer_output.mkdir()
    write_json(phase2 / "docker-plan.json", docker_plan(phase_input, reviewer_output, PHASE2))
    update_run(
        run_directory,
        state="phase2_released",
        phase2_input="phase2/input",
        phase2_release_manifest="phase2/input/release-manifest.json",
        phase2_release_manifest_sha256=sha256(phase_input / "release-manifest.json"),
        phase2_output="phase2/reviewer-output",
        phase2_docker_plan="phase2/docker-plan.json",
    )
    return release


def verify_run(run_directory):
    run_directory, manifest = load_run(run_directory)
    if manifest["state"] in {"phase1_sealed", "phase2_staged", "phase2_authorized", "phase2_released"}:
        verify_phase1_seal(run_directory)
    if manifest["state"] in {"phase2_staged", "phase2_authorized", "phase2_released"}:
        verify_phase2_staging(run_directory, manifest)
    if manifest["state"] in {"phase2_authorized", "phase2_released"}:
        verify_authorization(run_directory, manifest)
    if manifest["state"] == "phase2_released":
        release_path = run_path(run_directory, manifest["phase2_release_manifest"])
        if sha256(release_path) != manifest["phase2_release_manifest_sha256"]:
            raise ValueError("Phase 2 release manifest failed integrity verification")
        release = read_json(release_path)
        input_directory = release_path.parent
        if set(release["readable_files"]) != bundle_files(input_directory):
            raise ValueError("Phase 2 files differ from the release allowlist")
        for relative, expected in release["file_sha256"].items():
            if sha256(input_directory / ensure_safe_relative(relative)) != expected:
                raise ValueError(f"Phase 2 integrity check failed: {relative}")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="Validate and copy a bundle into an isolated phase 1 run")
    prepare.add_argument("--bundle", type=Path, required=True)
    prepare.add_argument("--output-root", type=Path, default=DEFAULT_RUN_ROOT)
    prepare.add_argument("--run-id")

    seal = subparsers.add_parser("seal-phase1", help="Validate and seal a phase 1 JSON submission")
    seal.add_argument("--run", type=Path, required=True)
    seal.add_argument("--submission", type=Path, required=True)

    authorize = subparsers.add_parser("authorize-phase2", help="Record explicit human authorization for phase 2")
    authorize.add_argument("--run", type=Path, required=True)
    authorize.add_argument("--approved-by", required=True)
    authorize.add_argument("--reason", required=True)

    stage = subparsers.add_parser("stage-phase2", help="Validate and stage phase 2 comparison inputs")
    stage.add_argument("--run", type=Path, required=True)
    stage.add_argument("--permissions", type=Path, required=True)
    stage.add_argument("--results", type=Path, required=True)

    release = subparsers.add_parser("release-phase2", help="Release the exact staged and approved inputs")
    release.add_argument("--run", type=Path, required=True)

    verify = subparsers.add_parser("verify", help="Verify the run hash chain and current state")
    verify.add_argument("--run", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "prepare":
        directory, result = prepare_run(args.bundle, args.output_root, args.run_id)
        result = {"run_directory": str(directory), **result}
    elif args.command == "seal-phase1":
        result = seal_phase1(args.run, args.submission)
    elif args.command == "stage-phase2":
        result = stage_phase2(args.run, args.permissions, args.results)
    elif args.command == "authorize-phase2":
        result = authorize_phase2(args.run, args.approved_by, args.reason)
    elif args.command == "release-phase2":
        result = release_phase2(args.run)
    else:
        result = verify_run(args.run)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

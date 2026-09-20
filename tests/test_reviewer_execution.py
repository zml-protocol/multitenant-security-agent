import inspect
import json
from pathlib import Path

from evaluation.operator import catalog
from reviewer.bundle import build_bundle
from reviewer.execution import controller
from reviewer.execution.controller import (
    PROFILE_PATH,
    approve_manual_launch,
    build_handoff_plan,
    claude_arguments,
    prepare_handoff,
)


PHASE1 = "decision_path_and_independent_matrix"


def test_handoff_plan_is_interactive_static_only_and_codex_cannot_launch(tmp_path: Path):
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    plan = build_handoff_plan(tmp_path / "input", tmp_path / "results", PHASE1)
    command = plan["manual_claude_command"]
    assert profile["formal_execution_authorized"] is False
    assert profile["codex_may_launch_claude"] is False
    assert plan["review_mode"] == "interactive_static_code_review_only"
    assert plan["codex_may_launch_claude"] is False
    assert plan["human_manual_launch_required"] is True
    assert plan["credential_value_handled_by_project"] is False
    assert plan["source_repository_mounted"] is False
    assert plan["runtime"]["interactive_tty"] is True
    assert plan["network"]["application_target_present"] is False
    assert plan["network"]["dynamic_test_gateway_present"] is False
    assert plan["static_review_boundary"]["dynamic_testing_allowed"] is False
    assert plan["static_review_boundary"]["application_credentials_present"] is False
    assert command == claude_arguments(PHASE1)
    assert "--print" not in command
    assert command[command.index("--add-dir") + 1] == "/review/output"
    assert command[command.index("--tools") + 1] == "Read,Glob,Grep,Edit"
    assert command[command.index("--allowedTools") + 1] == "Read,Glob,Grep,Edit"
    assert "Bash" in command[command.index("--disallowedTools") + 1]
    assert "ANTHROPIC_API_KEY=" not in json.dumps(plan)
    assert "sk-ant-" not in json.dumps(plan)


def test_preparer_contains_no_model_or_container_execution_path():
    source = inspect.getsource(controller)
    assert "subprocess" not in source
    assert "Popen" not in source
    assert "def execute(" not in source


def test_prepare_creates_interactive_static_handoff_and_separate_results(lab, tmp_path: Path):
    fixture_directory, _, _ = lab
    scenario_id = next(iter(catalog().values()))["scenario_id"]
    bundle, _ = build_bundle(scenario_id, fixture_directory / "fixture.json", tmp_path / "bundles")
    workspace = prepare_handoff(
        bundle,
        tmp_path / "handoffs",
        PHASE1,
        "manual-review",
        tmp_path / "results",
    )
    result_directory = tmp_path / "results" / "manual-review"
    manifest = json.loads((workspace / "handoff-manifest.json").read_text(encoding="utf-8"))
    approval_path = workspace / "approval" / "manual-launch-approval.json"
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "prepared_waiting_human_manual_launch_approval"
    assert manifest["review_mode"] == "interactive_static_code_review_only"
    assert manifest["codex_may_launch_claude"] is False
    assert approval["manual_launch_approved"] is False
    assert (workspace / "input" / "bundle-manifest.json").is_file()
    assert result_directory.is_dir()
    assert not any(result_directory.iterdir())
    assert not (workspace / "target").exists()
    assert not (workspace / "gateway").exists()
    assert (workspace / "runtime" / "Dockerfile").is_file()
    assert (workspace / "egress" / "Dockerfile").is_file()
    assert (workspace / "START-CLAUDE.cmd").is_file()
    compose = (workspace / "compose.yaml").read_text(encoding="utf-8")
    assert str(controller.ROOT) not in compose
    assert "./input:/review/input:ro" in compose
    assert "REVIEWER_OUTPUT_DIR" in compose
    assert "stdin_open: true" in compose
    assert "tty: true" in compose
    assert "target:" not in compose
    assert "reviewer-tool-gateway" not in compose
    assert compose.count("provenance: false") == 2
    assert "ANTHROPIC_API_KEY_FILE" in compose
    assert "ANTHROPIC_API_KEY=" not in compose
    launch = (workspace / "launch" / "launch.sh").read_text(encoding="utf-8")
    assert launch.index("manual_launch_approved") < launch.index("reviewer-credential-exec")
    assert "timeout --signal=TERM --kill-after=10s 900s" in launch
    assert "claude --restricted --bare" in launch
    assert "--add-dir /review/output" in launch
    assert "--allowedTools Read,Glob,Grep,Edit" in launch
    assert "--disallowedTools" in launch
    assert " -- 'The container" in launch
    assert "--print" not in launch
    windows_launcher = (workspace / "START-CLAUDE.cmd").read_text(encoding="utf-8")
    assert "docker compose" in windows_launcher
    assert "run --rm reviewer" in windows_launcher
    assert "ANTHROPIC_API_KEY_FILE" in windows_launcher
    assert "type " not in windows_launcher.lower()
    preflight_launcher = (workspace / "START-PREFLIGHT.cmd").read_text(encoding="utf-8")
    assert "run --rm preflight" in preflight_launcher
    assert (workspace / "preflight" / "read-probe.txt").read_text(encoding="utf-8").strip() == manifest["preflight_expected_output"]
    preflight_launch = (workspace / "launch" / "preflight.sh").read_text(encoding="utf-8")
    assert "--tools Read,Edit" in preflight_launch
    assert "--max-budget-usd 0.05" in preflight_launch
    assert "--no-session-persistence" in preflight_launch
    assert "bundle-manifest" not in preflight_launch
    assert "./preflight:/review/input:ro" in compose
    assert "./preflight-output:/review/output:rw" in compose
    recorded = approve_manual_launch(workspace, "security_engineer")
    assert recorded["manual_launch_approved"] is True
    assert recorded["handoff_manifest_sha256"]
    assert manifest["codex_may_launch_claude"] is False


def test_output_schemas_remain_static_review_reference_contracts():
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    for phase, required in {
        "decision_path_and_independent_matrix": {
            "authentication_authorization_decision_path",
            "independent_test_matrix",
            "limitations_and_unexecuted_tests",
        },
        "difference_review": {
            "matrix_difference_review",
            "proposed_supplemental_negative_tests",
            "evidence_gaps",
            "evidence_index",
            "draft_findings",
        },
    }.items():
        schema = json.loads(Path(profile["phases"][phase]["output_schema"]).read_text(encoding="utf-8"))
        assert set(schema["required"]) == required
        assert schema["additionalProperties"] is False

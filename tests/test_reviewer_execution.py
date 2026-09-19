import json
from pathlib import Path

import pytest

from reviewer.execution.controller import (
    PROFILE_PATH,
    assert_execution_authorized,
    build_execution_plan,
    claude_arguments,
)


PHASE1 = "decision_path_and_independent_matrix"


def test_execution_profile_and_command_are_fixed_but_not_authorized(tmp_path: Path):
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    plan = build_execution_plan(tmp_path / "input", tmp_path / "output", PHASE1)
    command = plan["command"]

    assert profile["formal_execution_authorized"] is False
    assert plan["execution_authorized"] is False
    assert plan["network_mode"] == "internal_proxy_only"
    assert plan["source_repository_mounted"] is False
    assert plan["credential"]["value_in_command_or_plan"] is False
    assert plan["egress"]["allowed_connect_targets"] == ["api.anthropic.com:443"]
    assert command == claude_arguments(PHASE1)
    assert command[0] == "claude"
    assert "--restricted" in command
    assert "--bare" in command
    assert "--disable-slash-commands" in command
    assert "--no-chrome" in command
    assert command[command.index("--model") + 1] == "claude-sonnet-5"
    assert command[command.index("--max-budget-usd") + 1] == "1.00"
    assert command[command.index("--max-turns") + 1] == "12"
    assert command[command.index("--permission-prompts") + 1] == "none"
    assert command[command.index("--tools") + 1] == "Read,Glob,Grep"
    assert command[command.index("--disallowedTools") + 1] == "mcp__*"
    assert "ANTHROPIC_API_KEY=" not in json.dumps(plan)
    assert "sk-ant-" not in json.dumps(plan)


def test_formal_execution_fails_closed_before_final_start_approval():
    with pytest.raises(PermissionError, match="not authorized"):
        assert_execution_authorized()


def test_output_schemas_match_runner_required_keys():
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

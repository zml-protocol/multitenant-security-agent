import json
from pathlib import Path

import pytest

from reviewer.auth_budget.gate import (
    PROFILE_PATH,
    approval_subject_sha256,
    execution_envelope,
    planning_cost,
    read_profile,
    run_synthetic_smoke,
    sanitized_subprocess_environment,
    validate_profile,
)


def test_approved_profile_is_fixed_but_execution_is_not_authorized():
    profile = read_profile()

    validate_profile(profile)
    assert profile["formal_execution_authorized"] is False
    assert profile["model_invocation_enabled"] is False
    assert profile["model"]["model_id"] == "claude-sonnet-5"
    assert str(planning_cost(profile)) == "0.40"
    assert profile["approval"]["approved"] is True
    assert profile["approval"]["approved_by"] == "project_owner"
    assert profile["approval"]["approved_profile_sha256"] == approval_subject_sha256(profile)
    assert PROFILE_PATH.is_file()


def test_execution_envelope_contains_policy_but_no_secret_value():
    serialized = json.dumps(execution_envelope(read_profile()))

    assert "claude-sonnet-5" in serialized
    assert "ANTHROPIC_API_KEY" in serialized
    assert "sk-ant-" not in serialized
    assert '"execution_authorized": false' in serialized
    assert '"credential_injection": "disabled"' in serialized


def test_subprocess_environment_scrubs_all_supported_credential_names():
    environment = {
        "PATH": "safe",
        "ANTHROPIC_API_KEY": "sentinel-a",
        "anthropic_auth_token": "sentinel-b",
        "CLAUDE_CODE_OAUTH_TOKEN": "sentinel-c",
    }

    assert sanitized_subprocess_environment(environment) == {"PATH": "safe"}


def test_profile_rejects_premature_authorization():
    profile = read_profile()
    profile["formal_execution_authorized"] = True

    with pytest.raises(ValueError, match="never be authorized"):
        validate_profile(profile)


def test_profile_rejects_project_model_invocation_even_with_status_change():
    profile = read_profile()
    profile["status"] = "formally_authorized"
    profile["formal_execution_authorized"] = True
    profile["model_invocation_enabled"] = True

    with pytest.raises(ValueError):
        validate_profile(profile)


def test_synthetic_smoke_leaves_no_sentinel_in_outputs(tmp_path: Path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "safe.txt").write_text("reviewer input", encoding="utf-8")

    result = run_synthetic_smoke(tmp_path / "results", bundle=bundle)

    assert result["status"] == "passed"
    assert result["real_credential_used"] is False
    assert result["model_called"] is False
    assert result["network_used"] is False
    assert all(result["checks"].values())
    persisted = json.loads(
        (Path(result["run_directory"]) / "result.json").read_text(encoding="utf-8")
    )
    assert persisted["checks"] == result["checks"]
    assert "sk-ant-synthetic-" not in json.dumps(result)
    assert "sk-ant-synthetic-" not in json.dumps(persisted)

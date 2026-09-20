import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "reviewer" / "runtime"


def test_runtime_profile_matches_pinned_image_definition():
    profile = json.loads((RUNTIME / "profile.json").read_text(encoding="utf-8"))
    dockerfile = (RUNTIME / "Dockerfile").read_text(encoding="utf-8")
    settings = json.loads((RUNTIME / "managed-settings.json").read_text(encoding="utf-8"))
    dockerignore = (RUNTIME / ".dockerignore").read_text(encoding="utf-8").splitlines()

    assert profile["formal_execution_authorized"] is False
    assert profile["network_mode"] == "none"
    assert profile["credential_injection"] == "disabled"
    assert profile["image"].endswith(f":{profile['claude_code_version']}")
    assert profile["base_image_digest"].startswith("sha256:")
    assert f"{profile['base_image']}@{profile['base_image_digest']}" in dockerfile
    assert "npm ci --omit=dev --no-audit --no-fund" in dockerfile
    assert "bubblewrap socat ca-certificates" in dockerfile
    lock = json.loads((RUNTIME / "package-lock.json").read_text(encoding="utf-8"))
    locked = lock["packages"]["node_modules/@anthropic-ai/claude-code"]
    assert locked["version"] == profile["claude_code_version"]
    assert locked["integrity"] == profile["claude_code_npm_integrity"]
    assert "USER 10001:10001" in dockerfile
    assert dockerignore[0] == "*"
    assert set(dockerignore[1:]) == {
        "!Dockerfile",
        "!managed-settings.json",
        "!package.json",
        "!package-lock.json",
        "!smoke.sh",
        "!credential-exec.sh",
        "!credential-probe.sh",
    }

    assert settings["allowManagedPermissionRulesOnly"] is True
    assert settings["disableClaudeAiConnectors"] is True
    assert settings["enableArtifact"] is False
    assert settings["syncClaudeAiSkills"] is False
    assert settings["syncClaudeAiPlugins"] is False
    assert settings["availableModels"] == ["claude-sonnet-5"]
    assert settings["permissions"]["disableBypassPermissionsMode"] == "disable"
    assert settings["permissions"]["allow"] == [
        "Read", "Glob", "Grep", "Edit"
    ]
    assert "Bash(*)" in settings["permissions"]["deny"]
    assert "Edit(/review/input/**)" in settings["permissions"]["deny"]
    assert settings["env"]["DISABLE_AUTOUPDATER"] == "1"
    assert settings["env"]["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] == "1"
    assert settings["env"]["CLAUDE_CODE_SUBPROCESS_ENV_SCRUB"] == "1"
    assert settings["env"]["CLAUDE_CODE_SKIP_PROMPT_HISTORY"] == "1"
    assert settings["env"]["DISABLE_UPDATES"] == "1"
    assert "reviewer-credential-exec" in dockerfile
    assert "reviewer-credential-probe" in dockerfile
    assert "reviewer-tool" not in dockerfile

import json
from pathlib import Path

from scripts.reviewer_egress_smoke import probe_arguments


ROOT = Path(__file__).resolve().parents[1]
EGRESS = ROOT / "reviewer" / "egress"


def test_egress_profile_and_proxy_are_deny_by_default():
    profile = json.loads((EGRESS / "profile.json").read_text(encoding="utf-8"))
    dockerfile = (EGRESS / "Dockerfile").read_text(encoding="utf-8")
    proxy = (EGRESS / "proxy.js").read_text(encoding="utf-8")

    assert profile["allowed_connect_targets"] == ["api.anthropic.com:443"]
    assert profile["reviewer_network_internal"] is True
    assert profile["proxy_only_egress"] is True
    assert profile["request_headers_logged"] is False
    assert profile["request_bodies_logged"] is False
    assert profile["credential_injection"] == "disabled"
    assert profile["model_invocation"] == "disabled"
    assert profile["active_in_reviewer_runner"] is False
    assert profile["formal_execution_authorized"] is False
    assert f"{profile['base_image']}@{profile['base_image_digest']}" in dockerfile
    assert f"USER {profile['container_user']}" in dockerfile
    assert "not_allowlisted" in proxy
    assert "Proxy-Authorization" not in proxy
    assert "process.env.EGRESS_ALLOWED_HOST" not in proxy
    assert 'const allowedHost = "api.anthropic.com"' in proxy


def test_smoke_probe_has_internal_network_and_no_credentials():
    arguments = probe_arguments("test-internal", "sha256:" + "a" * 64, "allowed")

    assert arguments[arguments.index("--network") + 1] == "test-internal"
    assert arguments[arguments.index("--user") + 1] == "10001:10001"
    assert "--read-only" in arguments
    assert arguments[arguments.index("--cap-drop") + 1] == "ALL"
    assert not any(value.startswith("ANTHROPIC_") or value.startswith("CLAUDE_") for value in arguments)

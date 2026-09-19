import hashlib
import importlib.util
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.main import create_app
from evaluation.operator import catalog
from reviewer.bundle import build_bundle, FORBIDDEN_MARKERS
from scanner.run import run_matrix


def load_bundled_policy(path, scenario_id):
    spec = importlib.util.spec_from_file_location(f"bundled_policy_{scenario_id}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("label,record", tuple(catalog().items()))
def test_bundle_isolated_and_behavior_preserved(lab, tmp_path, label, record):
    directory, fixture, credentials = lab
    destination, manifest = build_bundle(record["scenario_id"], directory / "fixture.json", tmp_path / "bundles")
    assert manifest["status"] == "draft_not_for_claude"
    assert manifest["scenario_id"] == record["scenario_id"]
    assert manifest["requirement_version"] == "appsec-v1.0"
    assert manifest["fixture_id"] == fixture["fixture_id"]
    assert isinstance(manifest["source_worktree_dirty"], bool)
    assert len(manifest["source_commit"]) == 40

    paths = {path.relative_to(destination).as_posix() for path in destination.rglob("*") if path.is_file()}
    assert "app/policy.py" in paths
    assert "bundle-manifest.json" in paths
    assert "assessment/reviewer-input-manifest.json" in paths
    assert not any(path.startswith(("tests/", "scanner/", "evaluation/", "reports/", ".local/")) for path in paths)
    assert not any("credential" in path.lower() or path.endswith(".sqlite3") for path in paths)

    fixture_copy = json.loads((destination / "inputs" / "fixture.json").read_text(encoding="utf-8"))
    assert all(set(user) == {"alias", "user_id", "tenant_id", "role"} for user in fixture_copy["users"])
    combined = "\n".join(path.read_text(encoding="utf-8") for path in destination.rglob("*") if path.is_file())
    assert not any(marker in combined for marker in FORBIDDEN_MARKERS)
    assert not any(token in combined for token in credentials["tokens"].values())
    assert all(user[field] not in combined for user in fixture["users"] for field in ("name", "email", "phone"))

    stored = json.loads((destination / "bundle-manifest.json").read_text(encoding="utf-8"))
    assert "bundle-manifest.json" in stored["readable_files"]
    assert set(stored["file_sha256"]) == paths - {"bundle-manifest.json"}
    for relative, expected in stored["file_sha256"].items():
        assert hashlib.sha256((destination / relative).read_bytes()).hexdigest() == expected

    reviewer_access = json.loads(
        (destination / "assessment" / "reviewer-input-manifest.json").read_text(encoding="utf-8")
    )
    assert reviewer_access["version"] == "2.0"
    assert reviewer_access["access_model"] == "generated_bundle_only"
    assert reviewer_access["isolation_requirements"]["bundle_is_only_accessible_workspace"] is True
    assert reviewer_access["isolation_requirements"]["prompt_only_restriction_is_sufficient"] is False
    assert "readable_inputs" not in reviewer_access
    assert reviewer_access["tool_access_status"] == "not_implemented_not_authorized"

    policy = load_bundled_policy(destination / "app" / "policy.py", record["scenario_id"])
    with TestClient(create_app(directory / "app.sqlite3", policy)) as client:
        report = run_matrix(client, fixture, credentials, interval=0)
    assert report["summary"]["confirmed_violation"] == record["expected_confirmed_violations"]


def test_bundle_refuses_labels_unknown_ids_and_overwrite(lab, tmp_path):
    directory, _, _ = lab
    with pytest.raises(ValueError, match="neutral scenario IDs"):
        build_bundle("secure", directory / "fixture.json", tmp_path / "bundles")
    with pytest.raises(ValueError, match="Unknown evaluation scenario"):
        build_bundle("scenario-unknown", directory / "fixture.json", tmp_path / "bundles")
    scenario_id = next(iter(catalog().values()))["scenario_id"]
    build_bundle(scenario_id, directory / "fixture.json", tmp_path / "bundles")
    with pytest.raises(ValueError, match="already exists"):
        build_bundle(scenario_id, directory / "fixture.json", tmp_path / "bundles")

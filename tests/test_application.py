import hashlib
import json
import logging
import sqlite3
import uuid

from fastapi.testclient import TestClient
import pytest

from app.main import create_app, MODES
from app.seed import initialize
from scanner.run import run_matrix


@pytest.mark.parametrize("mode,count", [("secure", 0), ("same_tenant_bypass", 8),
                                       ("cross_tenant_bypass", 18), ("list_role_bypass", 4)])
def test_complete_matrix_and_independent_modes(lab, mode, count):
    path, fixture, credentials = lab
    with TestClient(create_app(path / "app.sqlite3", mode)) as client:
        report = run_matrix(client, fixture, credentials, interval=0)
    assert report["summary"]["matrix_executed"] == 48
    assert report["summary"]["authentication_executed"] == 6
    assert report["summary"]["confirmed_violation"] == count
    assert report["summary"]["passed"] == 54 - count
    assert report["summary"]["inconclusive"] == 0
    assert report["summary"]["functional_anomalies"] == 0
    users = {u["alias"]: u for u in fixture["users"]}
    expected_cases = set()
    for actor, user in users.items():
        if mode == "list_role_bypass" and user["role"] == "user":
            expected_cases.add(f"list:{actor}")
        for target, other in users.items():
            if mode == "same_tenant_bypass" and user["role"] == "user" and actor != target and user["tenant_id"] == other["tenant_id"]:
                expected_cases.add(f"detail:{actor}:{target}")
            if mode == "cross_tenant_bypass" and user["tenant_id"] != other["tenant_id"]:
                expected_cases.add(f"detail:{actor}:{target}")
    assert {r["case_id"] for r in report["results"] if r["outcome"] == "confirmed_violation"} == expected_cases
    assert all(r["passed"] for r in report["results"] if r["group"] == "authentication")
    if mode != "secure":
        with TestClient(create_app(path / "app.sqlite3", "secure")) as client:
            fixed = run_matrix(client, fixture, credentials, interval=0)
        assert fixed["fixture_id"] == report["fixture_id"]
        assert fixed["summary"]["passed"] == 54
        assert fixed["summary"]["confirmed_violation"] == 0
        assert {r["case_id"] for r in fixed["results"]} == {r["case_id"] for r in report["results"]}


def test_credentials_random_but_snapshot_reproducible(lab, tmp_path):
    path, fixture, credentials = lab
    other = tmp_path / "other"
    assert initialize(other) == fixture
    new = json.loads((other / "credentials.json").read_text())
    assert all(new["tokens"][alias] != token for alias, token in credentials["tokens"].items())
    assert len(set(credentials["tokens"].values())) == 6
    assert all(len(token) >= 43 for token in credentials["tokens"].values())
    with sqlite3.connect(path / "app.sqlite3") as db:
        hashes = {row[0] for row in db.execute("SELECT token_hash FROM users")}
    assert hashes == {hashlib.sha256(token.encode()).hexdigest() for token in credentials["tokens"].values()}
    before = (path / "app.sqlite3").read_bytes()
    with pytest.raises(ValueError, match="already exists"):
        initialize(path)
    assert (path / "app.sqlite3").read_bytes() == before


@pytest.mark.parametrize("mode", MODES)
def test_spoofing_malformed_auth_and_read_only(lab, mode):
    path, fixture, credentials = lab
    users = {u["alias"]: u for u in fixture["users"]}
    headers = {"Authorization": f"Bearer {credentials['tokens']['a_user1']}",
               "X-Tenant-ID": "tenant_b", "X-Role": "admin", "X-User-ID": users["b_admin"]["user_id"],
               "X-Lab-Mode": "cross_tenant_bypass"}
    before = (path / "app.sqlite3").read_bytes()
    with TestClient(create_app(path / "app.sqlite3", mode)) as client:
        response = client.get("/api/me?mode=cross_tenant_bypass", headers=headers)
        assert response.json()["user_id"] == users["a_user1"]["user_id"]
        assert response.json()["role"] == "user"
        cross = client.get(f"/api/users/{users['b_user1']['user_id']}", headers=headers)
        assert cross.status_code == (200 if mode == "cross_tenant_bypass" else 403)
        same = client.get(f"/api/users/{users['a_user2']['user_id']}", headers=headers)
        assert same.status_code == (200 if mode == "same_tenant_bypass" else 403)
        listing = client.get("/api/users", headers=headers)
        assert listing.status_code == (200 if mode == "list_role_bypass" else 403)
        if listing.status_code == 200:
            assert {u["tenant_id"] for u in listing.json()} == {"tenant_a"}
        for bad in ("Bearer", "Basic value", "Bearer value extra", "Bearer invalid", ""):
            for route in ("/api/me", "/api/users", f"/api/users/{users['a_user1']['user_id']}"):
                denied = client.get(route, headers={"Authorization": bad})
                assert denied.status_code == 401
                assert denied.json() == {"detail": "Unauthorized"}
        for route in ("/api/me", "/api/users", f"/api/users/{users['a_user1']['user_id']}"):
            for method in ("POST", "PUT", "PATCH", "DELETE"):
                assert client.request(method, route, headers=headers).status_code == 405
        assert client.get("/api/users/not-a-user", headers=headers).status_code == 404
        assert client.get("/api/users/' OR '1'='1", headers=headers).status_code == 404
        for route in ("/docs", "/openapi.json", "/api/mode"):
            assert client.get(route, headers=headers).status_code == 404
    assert (path / "app.sqlite3").read_bytes() == before


def test_fail_closed_config_and_default(lab, monkeypatch):
    path, _, _ = lab
    monkeypatch.delenv("LAB_MODE", raising=False)
    assert len(create_app(path / "app.sqlite3").routes) == 3
    with pytest.raises(ValueError, match="Unknown LAB_MODE"):
        create_app(path / "app.sqlite3", "typo")
    with pytest.raises(ValueError, match="Database missing"):
        create_app(path / "missing.sqlite3", "secure")


def test_log_correlation_and_no_secrets(lab, caplog):
    path, fixture, credentials = lab
    with caplog.at_level(logging.INFO, logger="lab.access"):
        with TestClient(create_app(path / "app.sqlite3", "secure")) as client:
            report = run_matrix(client, fixture, credentials, interval=0)
            client.get("/api/users/untrusted-secret?token=untrusted-secret",
                       headers={"X-Request-ID": "untrusted-secret", "X-Run-ID": "untrusted-secret"})
    entries = [json.loads(record.message) for record in caplog.records if record.name == "lab.access"]
    assert len(entries) == 55
    logs = {entry["request_id"]: entry for entry in entries}
    for result in report["results"]:
        log = logs[result["request_id"]]
        assert log["run_id"] == report["run_id"]
        assert log["status"] == result["status_code"]
        assert log["identity"] == (result["actor"] or "unknown")
    assert entries[-1]["identity"] == "unknown"
    uuid.UUID(entries[-1]["request_id"])
    combined = json.dumps(entries) + json.dumps(report)
    assert "untrusted-secret" not in combined
    for token in credentials["tokens"].values():
        assert token not in combined
    for user in fixture["users"]:
        for key in ("name", "email", "phone"):
            assert user[key] not in combined

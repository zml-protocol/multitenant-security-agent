import copy
import json

import httpx
import pytest

from scanner.assess import assess
from scanner.matrix import build_cases, TEMPLATE
from scanner.run import run_matrix, write_report


def denied_case(fixture):
    return next(c for c in build_cases(fixture)[1] if c["case_id"] == "detail:a_user1:a_user2")


@pytest.mark.parametrize("status,body,error", [(200, {}, False), (200, [], False), (429, {}, False),
                                             (500, {}, False), (302, {}, False), (None, None, True),
                                             (403, {"unexpected": "unknown data"}, False)])
def test_uncertainty_is_not_a_pass(lab, status, body, error):
    _, fixture, _ = lab
    result = assess(denied_case(fixture), status, body, fixture, error)
    assert result["outcome"] == "inconclusive"
    assert not result["passed"]


@pytest.mark.parametrize("status", [200, 401, 403, 500])
def test_protected_data_inside_errors_is_evidence(lab, status):
    _, fixture, _ = lab
    target = next(u for u in fixture["users"] if u["alias"] == "a_user2")
    result = assess(denied_case(fixture), status, {"error": {"debug": target["email"]}}, fixture)
    assert result["outcome"] == "confirmed_violation"
    assert result["response_summary"]["leaked_records"][0]["fields"] == ["email"]
    assert target["email"] not in json.dumps(result)


def test_plain_text_leak_and_cross_tenant_admin_list(lab):
    _, fixture, _ = lab
    user = next(u for u in fixture["users"] if u["alias"] == "b_user1")
    case = next(c for c in build_cases(fixture)[1] if c["case_id"] == "list:a_admin")
    assert assess(case, 403, f"debug: {user['phone']}", fixture)["outcome"] == "confirmed_violation"
    assert assess(case, 200, [user], fixture)["outcome"] == "confirmed_violation"


@pytest.mark.parametrize("status,body", [(403, {"detail": "Forbidden"}), (200, {}), (200, [])])
def test_legal_access_failure_is_anomaly(lab, status, body):
    _, fixture, _ = lab
    case = next(c for c in build_cases(fixture)[1] if c["case_id"] == "me:a_user1")
    result = assess(case, status, body, fixture)
    assert result["functional_anomaly"]
    assert not result["passed"]


def test_runner_timeout_redirect_no_forwarding_and_report(lab, tmp_path):
    _, fixture, credentials = lab
    seen = []

    def handler(request):
        seen.append(request)
        if len(seen) == 1:
            raise httpx.ReadTimeout("secret exception detail", request=request)
        return httpx.Response(302, headers={"Location": "https://outside.invalid/"})

    with httpx.Client(base_url="http://127.0.0.1:8000", transport=httpx.MockTransport(handler)) as client:
        report = run_matrix(client, fixture, credentials, interval=0)
    assert len(seen) == 54
    assert all(req.url.host == "127.0.0.1" and req.method == "GET" for req in seen)
    assert report["summary"]["inconclusive"] == 54
    assert report["summary"]["passed"] == 0
    write_report(report, tmp_path / "reports")
    output = (tmp_path / "reports" / "report.json").read_text(encoding="utf-8")
    assert "secret exception detail" not in output
    assert (tmp_path / "reports" / "report.md").is_file()
    assert (tmp_path / "reports" / "report.en.md").is_file()
    assert "Fixed Authorization Matrix Report" in (tmp_path / "reports" / "report.en.md").read_text(encoding="utf-8")


def test_fixture_validation(lab):
    _, fixture, credentials = lab
    bad = copy.deepcopy(fixture)
    bad["users"][0]["user_id"] = "../outside"
    with pytest.raises(ValueError):
        build_cases(bad)
    bad = copy.deepcopy(fixture)
    bad["users"][0]["user_id"] = bad["users"][1]["user_id"]
    with pytest.raises(ValueError):
        build_cases(bad)
    wrong = {**credentials, "fixture_id": "other"}
    with pytest.raises(ValueError, match="snapshots differ"):
        run_matrix(None, fixture, wrong, interval=0)


@pytest.mark.parametrize("change", [{"method": "POST"}, {"path": "https://outside.invalid/"},
                                   {"path": "/api/users/../outside"}, {"identity_alias": "unknown"},
                                   {"headers": {"Authorization": "secret"}}, {"target_alias": "b_user1"}])
def test_request_scope_rejected_before_network(lab, tmp_path, change):
    _, fixture, credentials = lab
    template = json.loads(TEMPLATE.read_text())
    template.update(change)
    custom = tmp_path / "request-template.json"
    custom.write_text(json.dumps(template))
    with pytest.raises(ValueError):
        run_matrix(None, fixture, credentials, interval=0, template_path=custom)

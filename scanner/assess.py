"""Inspect data, not just HTTP status. No raw response enters a report."""
import json

PROTECTED = ("name", "email", "phone")
PUBLIC = ("user_id", "tenant_id", "role", *PROTECTED)


def assess(case, status, body, fixture, transport_error=False):
    users = fixture["users"]
    allowed = set(case["allowed_aliases"])
    text = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
    # Also catches known protected values in nested errors or non-JSON text.
    matches = []
    for user in users:
        fields = [field for field in PROTECTED if user[field] in text]
        if fields:
            matches.append({"alias": user["alias"], "user_id": user["user_id"],
                            "tenant_id": user["tenant_id"], "fields": fields})
    leaks = [match for match in matches if match["alias"] not in allowed]
    summary = {"matched_records": matches, "leaked_records": leaks}

    def result(outcome, reason, passed=False, anomaly=False):
        return {"outcome": outcome, "reason": reason, "passed": passed,
                "functional_anomaly": anomaly, "response_summary": summary}

    if leaks:
        return result("confirmed_violation", "protected_data_outside_permission")
    if transport_error or status is None or status == 429 or status >= 500 or 300 <= status < 400:
        return result("inconclusive", "transport_rate_limit_server_error_or_redirect")
    if case["expected"] == "allow":
        expected = [{key: user[key] for key in PUBLIC} for user in users if user["alias"] in allowed]
        if case["kind"] == "list":
            complete = isinstance(body, list) and len(body) == len(expected) and all(user in body for user in expected)
        else:
            complete = len(expected) == 1 and body == expected[0]
        if status == 200 and complete:
            return result("no_violation_observed", "expected_data_returned", passed=True)
        return result("inconclusive", "allowed_request_failed_or_incomplete", anomaly=True)
    expected_status = 401 if case["group"] == "authentication" else 403
    # Only the expected generic denial is a pass. Unknown content needs review.
    generic = {"detail": "Unauthorized" if expected_status == 401 else "Forbidden"}
    if status == expected_status and body == generic:
        return result("no_violation_observed", "expected_denial_without_data", passed=True)
    return result("inconclusive", "unexpected_response_without_proven_leak")

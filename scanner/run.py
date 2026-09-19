import argparse
from collections import Counter
import json
from pathlib import Path
import time
import uuid

import httpx

from scanner.assess import assess
from scanner.matrix import build_cases, load_template, RULES, TEMPLATE

TARGET = "http://127.0.0.1:8000"


def run_matrix(client, fixture, credentials, interval=0.5, rules_path=RULES, template_path=TEMPLATE):
    if credentials["fixture_id"] != fixture["fixture_id"]:
        raise ValueError("Credential and fixture snapshots differ")
    version, cases = build_cases(fixture, rules_path)
    template = load_template(fixture, template_path)
    baseline = next(case for case in cases if case["case_id"] == f"detail:{template['identity_alias']}:{template['target_alias']}")
    if baseline["expected"] != "allow":
        raise ValueError("Normal request template must describe an allowed request")
    if set(credentials["tokens"]) != {user["alias"] for user in fixture["users"]}:
        raise ValueError("Credentials must match all fixture aliases")
    run_id = str(uuid.uuid4())
    results = []
    previous_start = None
    for case in cases:
        if previous_start is not None:
            time.sleep(max(0, interval - (time.perf_counter() - previous_start)))
        previous_start = time.perf_counter()
        request_id = str(uuid.uuid4())
        headers = {"X-Request-ID": request_id, "X-Run-ID": run_id}
        if case["credential"] != "missing":
            token = credentials["tokens"][case["actor"]] if case["credential"] == "valid" else "invalid-lab-credential"
            headers["Authorization"] = f"Bearer {token}"
        status, body, error, fixture_matches, correlated = None, None, False, False, False
        try:
            response = client.get(case["path"], headers=headers, follow_redirects=False)
            status = response.status_code
            fixture_matches = response.headers.get("x-fixture-id") == fixture["fixture_id"]
            correlated = response.headers.get("x-request-id") == request_id
            try:
                body = response.json()
            except ValueError:
                body = response.text
        except httpx.RequestError:
            # Exception text can contain URLs and secrets; never persist it.
            error = True
        assessment = assess(case, status, body, fixture, error)
        if not error and (not fixture_matches or not correlated) and assessment["outcome"] != "confirmed_violation":
            assessment.update(outcome="inconclusive", passed=False, functional_anomaly=True,
                              reason="fixture_or_correlation_mismatch")
        results.append({
            **case, **assessment, "run_id": run_id, "evidence_id": f"{run_id}:{case['case_id']}",
            "request_id": request_id, "status_code": status,
            "elapsed_ms": round((time.perf_counter() - previous_start) * 1000, 3),
            "request": {"method": "GET", "path": case["path"], "credential": case["credential"],
                        "Authorization": "[REDACTED]" if case["credential"] != "missing" else "[MISSING]"},
            "fixture_matches": fixture_matches, "correlated": correlated,
        })
    counts = Counter(result["outcome"] for result in results)
    return {
        "run_id": run_id, "fixture_id": fixture["fixture_id"], "permission_version": version,
        "normal_request_template": template,
        "agent_analysis": "not_implemented; deterministic results only",
        "scope": "Known six identities and three read-only endpoints; not a whole-application security claim.",
        "summary": {"matrix_planned": 48, "matrix_executed": sum(r["group"] == "matrix" for r in results),
                    "authentication_executed": sum(r["group"] == "authentication" for r in results),
                    "passed": sum(r["passed"] for r in results),
                    "functional_anomalies": sum(r["functional_anomaly"] for r in results),
                    **{key: counts[key] for key in ("confirmed_violation", "no_violation_observed", "inconclusive")}},
        "results": results,
    }


def write_report(report, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# 固定权限矩阵报告", "", "[English](report.en.md) | 中文", "",
             f"- run_id: {report['run_id']}", f"- fixture_id: {report['fixture_id']}",
             f"- 权限版本: {report['permission_version']}", "- Agent 补证尚未实现；本报告仅包含确定性测试。",
             "- 范围限于六个已知身份和三个只读接口，不代表应用整体安全。", "",
             "```json", json.dumps(report["summary"], indent=2), "```", "",
             "| 用例 | 预期 | 状态码 | 结论 | 依据 |", "| --- | --- | --- | --- | --- |"]
    for row in report["results"]:
        lines.append(f"| {row['case_id']} | {row['expected']} | {row['status_code']} | {row['outcome']} | {row['reason']} |")
    lines.extend(["", "## 证据与复现", "", "JSON 中每项包含 evidence_id、request_id、脱敏请求、命中的用户 ID 和字段名。",
                  "使用同一 fixture，以 actor 对应的本地凭据发送 GET path；不要将凭据复制到报告。", "",
                  "## 修复原则", "", "详情必须同时执行租户边界和对象归属/管理员检查；列表必须同时检查管理员角色和租户过滤。",
                  "由操作者切回 secure 并复用数据快照复测，确认违规消失且合法访问仍成功。", ""])
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")
    english = ["# Fixed Authorization Matrix Report", "", "English | [中文](report.md)", "",
               f"- run_id: {report['run_id']}", f"- fixture_id: {report['fixture_id']}",
               f"- Authorization version: {report['permission_version']}",
               "- Agent supplemental analysis is not implemented; this report contains deterministic test results only.",
               "- Scope is limited to six known identities and three read-only endpoints; this is not a whole-application security claim.",
               "", "```json", json.dumps(report["summary"], indent=2), "```", "",
               "| Case | Expected | Status | Conclusion | Basis |", "| --- | --- | --- | --- | --- |"]
    for row in report["results"]:
        english.append(f"| {row['case_id']} | {row['expected']} | {row['status_code']} | {row['outcome']} | {row['reason']} |")
    english.extend(["", "## Evidence and Reproduction", "",
                    "Each JSON result contains an evidence ID, request ID, redacted request, matched test user IDs, and matched field names.",
                    "Using the same fixture, send GET to the recorded path with the local credential for the actor; never copy credentials into a report.",
                    "", "## Remediation Principle", "",
                    "Detail access must enforce both the tenant boundary and object ownership/administrator check. List access must enforce both the administrator role and tenant filtering.",
                    "The operator switches back to `secure` and reuses the same data snapshot for regression testing, confirming that violations disappear while legitimate access still succeeds.", ""])
    (output / "report.en.md").write_text("\n".join(english), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Run the fixed local matrix (54 requests, at most 2/s).")
    parser.add_argument("--base-url", default=TARGET, choices=[TARGET])
    parser.add_argument("--directory", type=Path, default=Path(".local"))
    parser.add_argument("--output", type=Path, default=Path("reports/local/latest"))
    parser.add_argument("--permissions", type=Path, default=RULES)
    parser.add_argument("--request-template", type=Path, default=TEMPLATE)
    args = parser.parse_args()
    fixture = json.loads((args.directory / "fixture.json").read_text(encoding="utf-8"))
    credentials = json.loads((args.directory / "credentials.json").read_text(encoding="utf-8"))
    # An exact loopback target prevents arbitrary URLs, proxies and redirect credential forwarding.
    with httpx.Client(base_url=args.base_url, trust_env=False, follow_redirects=False, timeout=10) as client:
        report = run_matrix(client, fixture, credentials, rules_path=args.permissions, template_path=args.request_template)
    report["target"] = args.base_url
    write_report(report, args.output)
    print(json.dumps(report["summary"], indent=2))
    raise SystemExit(1 if report["summary"]["confirmed_violation"] else 2 if report["summary"]["inconclusive"] else 0)


if __name__ == "__main__":
    main()

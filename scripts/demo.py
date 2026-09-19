"""Generate mode-isolated evidence and secure retests against one snapshot, in process."""
import argparse
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from evaluation.operator import catalog, load_policy
from scanner.run import run_matrix, write_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path(".local"))
    parser.add_argument("--output", type=Path, default=Path("reports/local/demo"))
    args = parser.parse_args()
    fixture = json.loads((args.directory / "fixture.json").read_text(encoding="utf-8"))
    credentials = json.loads((args.directory / "credentials.json").read_text(encoding="utf-8"))
    truth = catalog()
    scenarios = [("secure", "secure", truth["secure"]["expected_confirmed_violations"])]
    for label in ("same_tenant_bypass", "cross_tenant_bypass", "list_role_bypass"):
        scenarios.extend([(label, label, truth[label]["expected_confirmed_violations"]), (f"{label}_fixed", "secure", 0)])
    comparisons = []
    for label, mode, expected in scenarios:
        with TestClient(create_app(args.directory / "app.sqlite3", load_policy(mode))) as client:
            report = run_matrix(client, fixture, credentials, interval=0)
        report["transport"] = "in_process_testclient"
        write_report(report, args.output / label)
        summary = report["summary"]
        correct = summary["confirmed_violation"] == expected and summary["passed"] == 54 - expected
        comparisons.append({"scenario": label, "fixture_id": fixture["fixture_id"], "run_id": report["run_id"],
                            "expected_violations": expected, "verified": correct, **summary})
        print(f"{label}: violations={summary['confirmed_violation']}, passed={summary['passed']}/54, verified={correct}")
    (args.output / "comparison.json").write_text(json.dumps(comparisons, indent=2) + "\n", encoding="utf-8")
    raise SystemExit(0 if all(row["verified"] for row in comparisons) else 1)


if __name__ == "__main__":
    main()

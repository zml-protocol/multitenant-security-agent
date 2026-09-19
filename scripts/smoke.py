"""Start a temporary real HTTP server, run the secure matrix, verify logs, stop it."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx

from scanner.run import run_matrix, TARGET, write_report


def main():
    directory = Path(".local")
    fixture = json.loads((directory / "fixture.json").read_text(encoding="utf-8"))
    credentials = json.loads((directory / "credentials.json").read_text(encoding="utf-8"))
    # Do not replace or terminate another service already using the lab port.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 8000))
    log_path = directory / "smoke-access.log"
    env = {**os.environ, "LAB_MODE": "secure", "LAB_DB": str((directory / "app.sqlite3").resolve())}
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen([sys.executable, "-m", "app.serve"], env=env, stdout=log, stderr=log)
        try:
            with httpx.Client(base_url=TARGET, trust_env=False, follow_redirects=False, timeout=10) as client:
                for _ in range(50):
                    if process.poll() is not None:
                        raise RuntimeError("Server exited; inspect .local/smoke-access.log")
                    try:
                        ready = client.get("/api/me")
                        if ready.status_code == 401 and ready.headers.get("x-fixture-id") == fixture["fixture_id"]:
                            break
                    except httpx.RequestError:
                        pass
                    time.sleep(0.1)
                else:
                    raise RuntimeError("Server readiness timeout")
                report = run_matrix(client, fixture, credentials)
                report["transport"] = "real_http_loopback"
                report["target"] = TARGET
                write_report(report, "reports/local/http-secure")
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    text = log_path.read_text(encoding="utf-8")
    entries = []
    for line in text.splitlines():
        if line.startswith("{"):
            entries.append(json.loads(line))
    by_id = {entry["request_id"]: entry for entry in entries}
    for result in report["results"]:
        entry = by_id[result["request_id"]]
        if entry["run_id"] != report["run_id"] or entry["status"] != result["status_code"]:
            raise RuntimeError("Audit correlation mismatch")
    for token in credentials["tokens"].values():
        if token in text:
            raise RuntimeError("Credential appeared in server log")
    for user in fixture["users"]:
        if any(user[field] in text for field in ("name", "email", "phone")):
            raise RuntimeError("Protected data appeared in server log")
    print(json.dumps(report["summary"], indent=2))
    print(f"Verified {len(report['results'])} correlated log entries; server stopped.")
    raise SystemExit(0 if report["summary"]["passed"] == 54 else 1)


if __name__ == "__main__":
    main()

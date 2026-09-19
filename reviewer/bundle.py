"""Build a draft, scenario-isolated source bundle for independent review."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from evaluation.operator import load_policy, scenario_record


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = ROOT / ".local" / "reviewer-bundles"
FORBIDDEN_MARKERS = (
    "same_tenant_bypass",
    "cross_tenant_bypass",
    "list_role_bypass",
    "operator-truth",
    "expected_confirmed_violations",
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_value(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def write_text(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def copy_file(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def sanitized_fixture(fixture):
    allowed = ("alias", "user_id", "tenant_id", "role")
    return {
        "fixture_id": fixture["fixture_id"],
        "users": [{key: user[key] for key in allowed} for user in fixture["users"]],
    }


def instructions_zh():
    return """# Reviewer Bundle 使用说明

[English](README.en.md) | 中文

状态：`draft_not_for_claude`

这是单一中性场景的隔离评估输入。当前 bundle 仅用于验证打包和隔离，尚未通过正式启动门槛，不能交给 Claude 开始正式评估。

Reviewer 在获批后应先阅读 reviewer input manifest、assessment brief 和 security requirements，再检查 `app/main.py`、`app/policy.py` 与 `app/seed.py`，输出 authentication/authorization decision path 和独立测试矩阵。不要把 scenario ID 当作漏洞答案，不要尝试访问 bundle 之外的文件。

`inputs/fixture.json` 仅包含脱敏身份映射；不含姓名、邮箱、电话或凭据。`bundle-manifest.json` 记录允许读取的文件、源版本和 SHA-256 完整性信息。

manifest 本身不是操作系统沙箱。正式运行必须将本 bundle 复制或只读挂载为 Reviewer 唯一可访问的工作区；不得从包含源仓库的父目录启动 Claude。
"""


def instructions_en():
    return """# Reviewer Bundle Instructions

English | [中文](README.md)

Status: `draft_not_for_claude`

This is an isolated assessment input for one neutral scenario. The current bundle exists only to validate packaging and isolation. It has not passed the formal start gate and must not yet be given to Claude for a formal assessment.

Once approved, the reviewer reads the reviewer input manifest, assessment brief, and security requirements first, then reviews `app/main.py`, `app/policy.py`, and `app/seed.py` to produce an authentication/authorization decision path and an independent test matrix. Do not treat the scenario ID as a vulnerability answer or attempt to access files outside the bundle.

`inputs/fixture.json` contains a redacted identity mapping only; it has no names, email addresses, phone values, or credentials. `bundle-manifest.json` records readable files, source version, and SHA-256 integrity data.

The manifest is not an operating-system sandbox. A formal run must copy or read-only mount this bundle as the reviewer's only accessible workspace. Never start Claude from a parent directory that also contains the source repository.
"""


def build_bundle(scenario_id, fixture_path, output_root=DEFAULT_OUTPUT_ROOT):
    record = scenario_record(scenario_id)
    if record["scenario_id"] != scenario_id:
        raise ValueError("Reviewer bundles accept neutral scenario IDs only")
    fixture_path = Path(fixture_path).resolve()
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    destination = Path(output_root).resolve() / scenario_id
    if destination.exists():
        raise ValueError("Bundle destination already exists; do not overwrite review evidence")
    destination.mkdir(parents=True)

    sources = {
        "app/__init__.py": ROOT / "app" / "__init__.py",
        "app/main.py": ROOT / "app" / "main.py",
        "app/seed.py": ROOT / "app" / "seed.py",
        "assessment/assessment-brief.md": ROOT / "assessment" / "appsec" / "v1" / "assessment-brief.md",
        "assessment/assessment-brief.en.md": ROOT / "assessment" / "appsec" / "v1" / "assessment-brief.en.md",
        "assessment/security-requirements.json": ROOT / "assessment" / "appsec" / "v1" / "security-requirements.json",
        "assessment/reviewer-input-manifest.json": ROOT / "assessment" / "appsec" / "v1" / "reviewer-input-manifest.json",
        "inputs/request-template.json": ROOT / "fixtures" / "request-template.v1.json",
    }
    for relative, source in sources.items():
        copy_file(source, destination / relative)
    selected_policy = Path(load_policy(scenario_id).__file__).resolve()
    copy_file(selected_policy, destination / "app" / "policy.py")
    write_text(destination / "inputs" / "fixture.json", json.dumps(sanitized_fixture(fixture), indent=2) + "\n")
    write_text(destination / "README.md", instructions_zh())
    write_text(destination / "README.en.md", instructions_en())

    content_files = sorted(
        path.relative_to(destination).as_posix()
        for path in destination.rglob("*")
        if path.is_file()
    )
    for relative in content_files:
        content = (destination / relative).read_text(encoding="utf-8")
        for marker in FORBIDDEN_MARKERS:
            if marker in content:
                raise ValueError(f"Reviewer bundle contains forbidden operator marker in {relative}")

    credentials_path = fixture_path.with_name("credentials.json")
    if credentials_path.is_file():
        credentials = json.loads(credentials_path.read_text(encoding="utf-8"))
        combined = "\n".join((destination / relative).read_text(encoding="utf-8") for relative in content_files)
        if any(token in combined for token in credentials.get("tokens", {}).values()):
            raise ValueError("Reviewer bundle contains a raw credential")

    file_hashes = {relative: sha256(destination / relative) for relative in content_files}
    source_commit = git_value("rev-parse", "HEAD")
    source_dirty = bool(git_value("status", "--porcelain"))
    requirements = json.loads((destination / "assessment" / "security-requirements.json").read_text(encoding="utf-8"))
    identity = {
        "scenario_id": scenario_id,
        "source_commit": source_commit,
        "requirement_version": requirements["requirement_version"],
        "fixture_id": fixture["fixture_id"],
        "file_sha256": file_hashes,
    }
    bundle_id = "bundle-" + hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:20]
    manifest = {
        "bundle_schema_version": "1.0",
        "bundle_id": bundle_id,
        "status": "draft_not_for_claude",
        "scenario_id": scenario_id,
        "source_commit": source_commit,
        "source_worktree_dirty": source_dirty,
        "requirement_version": requirements["requirement_version"],
        "fixture_id": fixture["fixture_id"],
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "review_phase": "decision_path_and_independent_matrix",
        "readable_files": ["bundle-manifest.json", *content_files],
        "excluded_categories": [
            "raw credentials and databases",
            "operator scenario mapping and labels",
            "other scenario implementations",
            "existing test and scanner code",
            "historical reports and evidence",
        ],
        "file_sha256": file_hashes,
    }
    write_text(destination / "bundle-manifest.json", json.dumps(manifest, indent=2) + "\n")
    return destination, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario-id", required=True, help="Neutral operator-provided scenario ID")
    parser.add_argument("--fixture", type=Path, default=Path(".local/fixture.json"))
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    destination, manifest = build_bundle(args.scenario_id, args.fixture, args.output_root)
    print(json.dumps({"bundle": str(destination), "bundle_id": manifest["bundle_id"],
                      "status": manifest["status"], "source_worktree_dirty": manifest["source_worktree_dirty"]}, indent=2))


if __name__ == "__main__":
    main()

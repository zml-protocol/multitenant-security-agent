"""Build a read-only, credential-free bundle for Claude remediation verification."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def copy(relative: str, bundle: Path, target: str | None = None) -> None:
    destination = bundle / (target or relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / relative, destination)


def git(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8"
    )
    return result.stdout.strip()


def build(output: Path, vulnerable_ref: str, fixed_ref: str) -> Path:
    output = output.resolve()
    if output.exists():
        raise ValueError("Remediation reviewer bundle already exists")
    output.mkdir(parents=True)

    copies = {
        "app/main.py": None,
        "app/policy.py": None,
        "app/seed.py": None,
        "scanner/assess.py": None,
        "scanner/matrix.py": None,
        "tests/test_application.py": None,
        "fixtures/permissions.v1.json": "inputs/permissions.json",
        "assessment/appsec/v1/security-requirements.json": "assessment/security-requirements.json",
        "assessment/appsec/v1/claude-review-v4/adjudication-record.json": "assessment/adjudication-record.json",
        "assessment/appsec/v1/claude-review-v4/adjudication-record.md": "assessment/adjudication-record.md",
        "assessment/appsec/v1/claude-review-v4/adjudication-record.en.md": "assessment/adjudication-record.en.md",
        "assessment/appsec/v1/claude-review-v4/evidence/f1-minimum-dynamic-evidence.json": "evidence/before.json",
        "remediation/appsec/v1/regression-evidence.json": "evidence/after.json",
        "remediation/appsec/v1/remediation-record.md": "remediation/remediation-record.md",
        "remediation/appsec/v1/remediation-record.en.md": "remediation/remediation-record.en.md",
    }
    for source, target in copies.items():
        copy(source, output, target)

    diff = git(
        "diff", "--no-ext-diff", f"{vulnerable_ref}..{fixed_ref}", "--",
        "app/main.py", "scanner/assess.py", "tests/test_application.py",
    )
    (output / "changes").mkdir()
    (output / "changes" / "remediation.diff").write_text(diff + "\n", encoding="utf-8", newline="\n")

    readme = (
        "# AppSec v1 Remediation Verification Bundle\n\n"
        "This credential-free bundle contains the confirmed F1 decision, minimized before/after evidence, "
        "the fixed authorization path, regression tests, the independent scanner oracle, and the exact remediation diff. "
        "Claude must independently verify the remediation and may write only to `/review/output`.\n"
    )
    (output / "README.en.md").write_text(readme, encoding="utf-8", newline="\n")
    (output / "README.md").write_text(
        "# AppSec v1 修复验收 Bundle\n\n"
        "本 bundle 不含凭据，包含 F1 confirmed 裁决、最小化的修复前后证据、修复后的授权路径、回归测试、独立 scanner oracle 和精确修复 diff。"
        "Claude 必须独立判断修复是否满足验收标准，并且只能写入 `/review/output`。\n",
        encoding="utf-8", newline="\n",
    )
    access = {
        "version": "2.1",
        "status": "ready_for_claude_remediation_verification",
        "reviewer": "claude",
        "access_model": "generated_bundle_only",
        "execution_mode": "interactive_static_remediation_verification_only",
        "review_phases": [{
            "phase": "remediation_verification",
            "input_source": "bundle-manifest.json readable_files",
            "source_repository_access": False,
            "required_outputs": [
                "verification-log.json", "remediation-verification.json",
                "remediation-verification.md", "remediation-verification.en.md",
                "limitations.md", "limitations.en.md",
            ],
        }],
        "reviewer_may_not": [
            "modify application code", "execute Bash or application code", "send HTTP requests",
            "use Web, MCP, or browsers", "read credentials", "create the appsec-v1-fixed tag",
        ],
        "final_acceptance_authority": "security_engineer",
    }
    write_json(output / "assessment" / "reviewer-input-manifest.json", access)

    content = sorted(
        path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()
    )
    hashes = {relative: sha256(output / relative) for relative in content}
    identity = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()[:20]
    manifest = {
        "bundle_schema_version": "1.0",
        "bundle_id": f"remediation-bundle-{identity}",
        "status": "ready_for_claude_remediation_verification",
        "review_phase": "remediation_verification",
        "finding_id": "F1",
        "vulnerable_commit": vulnerable_ref,
        "source_commit": fixed_ref,
        "source_worktree_dirty": False,
        "requirement_version": "appsec-v1.0+F1-adjudication",
        "fixture_id": "fixture-256eb13b57860e22",
        "readable_files": ["bundle-manifest.json", *content],
        "file_sha256": hashes,
        "excluded_categories": [
            "raw credentials and databases", "operator scenario mappings", "unrelated historical outputs",
            "source repository and parent directories",
        ],
    }
    write_json(output / "bundle-manifest.json", manifest)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--vulnerable-ref", default="appsec-v1-vulnerable^{}")
    parser.add_argument("--fixed-ref", default="HEAD")
    args = parser.parse_args()
    vulnerable = git("rev-parse", args.vulnerable_ref)
    fixed = git("rev-parse", args.fixed_ref)
    print(build(args.output, vulnerable, fixed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

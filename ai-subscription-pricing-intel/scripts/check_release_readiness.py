#!/usr/bin/env python3
"""Check whether the project is ready for a GitHub release."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
PROJECT_ROOT = SKILL_ROOT.parent

ROOT_FILES = [
    "README.md",
    ".gitignore",
    ".gitattributes",
    "LICENSE",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    "RELEASE_CHECKLIST.md",
]

SKILL_FILES = [
    "ai-subscription-pricing-intel/README.md",
    "ai-subscription-pricing-intel/SKILL.md",
    "ai-subscription-pricing-intel/requirements.txt",
    "ai-subscription-pricing-intel/config/product-monitoring.yml",
    "ai-subscription-pricing-intel/config/retention.yml",
    "ai-subscription-pricing-intel/references/environment.md",
    "ai-subscription-pricing-intel/scripts/check_environment.py",
]

GITHUB_FILES = [
    ".github/workflows/validate.yml",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/pull_request_template.md",
]

RUNTIME_DIRS = [
    "ai-subscription-pricing-intel/data/raw/appstoreprice",
    "ai-subscription-pricing-intel/data/normalized",
    "ai-subscription-pricing-intel/data/snapshots",
    "ai-subscription-pricing-intel/data/fx",
    "ai-subscription-pricing-intel/outputs",
]


def status_row(status: str, message: str, **extra: Any) -> dict[str, Any]:
    row = {"status": status, "message": message}
    row.update(extra)
    return row


def existing_files(project_root: Path, paths: list[str]) -> tuple[list[str], list[str]]:
    present = []
    missing = []
    for rel in paths:
        if (project_root / rel).is_file():
            present.append(rel)
        else:
            missing.append(rel)
    return present, missing


def check_required_files(project_root: Path, label: str, paths: list[str]) -> dict[str, Any]:
    present, missing = existing_files(project_root, paths)
    if missing:
        return status_row("error", f"{label} files are incomplete", files=present, missing=missing)
    return status_row("ok", f"{label} files are present", files=present)


def parse_frontmatter(skill_md: Path) -> dict[str, str]:
    text = skill_md.read_text(encoding="utf-8-sig")
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    payload: dict[str, str] = {}
    for raw_line in match.group(1).splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        payload[key.strip()] = value.strip().strip("'\"")
    return payload


def check_skill_frontmatter(project_root: Path) -> dict[str, Any]:
    skill_md = project_root / "ai-subscription-pricing-intel" / "SKILL.md"
    if not skill_md.exists():
        return status_row("error", "SKILL.md is missing")
    meta = parse_frontmatter(skill_md)
    name = meta.get("name", "")
    description = meta.get("description", "")
    issues = []
    if not re.fullmatch(r"[a-z0-9-]{1,64}", name):
        issues.append("name must be hyphen-case and <= 64 chars")
    if not description:
        issues.append("description is required")
    if len(description) > 1024:
        issues.append("description must be <= 1024 chars")
    if issues:
        return status_row("error", "Skill frontmatter is invalid", issues=issues, frontmatter=meta)
    return status_row("ok", "Skill frontmatter is valid", frontmatter=meta)


def git_check_ignored(project_root: Path, rel_path: str) -> bool | None:
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", rel_path],
            cwd=project_root,
            text=True,
            capture_output=True,
            check=False,
        )
    except (OSError, FileNotFoundError):
        return None
    return result.returncode == 0


def check_runtime_artifacts(project_root: Path) -> dict[str, Any]:
    unprotected = []
    not_ignored = []
    for rel_dir in RUNTIME_DIRS:
        directory = project_root / rel_dir
        if not directory.exists():
            unprotected.append({"path": rel_dir, "issue": "directory missing"})
            continue
        gitkeep = directory / ".gitkeep"
        if not gitkeep.exists():
            unprotected.append({"path": f"{rel_dir}/.gitkeep", "issue": "missing"})
        for child in directory.iterdir():
            if child.name == ".gitkeep":
                continue
            rel_child = child.relative_to(project_root).as_posix()
            ignored = git_check_ignored(project_root, rel_child)
            if ignored is False:
                not_ignored.append(rel_child)
    if unprotected or not_ignored:
        return status_row(
            "error",
            "Runtime artifact directories are not release-safe",
            unprotected=unprotected,
            not_ignored=not_ignored,
        )
    return status_row("ok", "Runtime artifact directories are release-safe", runtime_dirs=RUNTIME_DIRS)


def check_git_state(project_root: Path) -> dict[str, Any]:
    try:
        inside = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=project_root,
            text=True,
            capture_output=True,
            check=False,
        )
        remote = subprocess.run(["git", "remote", "-v"], cwd=project_root, text=True, capture_output=True, check=False)
    except (OSError, FileNotFoundError) as exc:
        return status_row("warning", "Git is unavailable", error=str(exc))
    if inside.returncode != 0:
        return status_row("warning", "Project is not inside a Git worktree")
    has_remote = bool(remote.stdout.strip())
    status = "ok" if has_remote else "warning"
    message = "Git repository has a remote" if has_remote else "Git repository has no remote configured yet"
    return status_row(status, message, remote=remote.stdout.strip())


def build_release_report(project_root: Path = PROJECT_ROOT, strict: bool = False) -> dict[str, Any]:
    project_root = project_root.resolve()
    checks = {
        "root_files": check_required_files(project_root, "Root GitHub", ROOT_FILES),
        "skill_package": check_required_files(project_root, "Skill package", SKILL_FILES),
        "github_templates": check_required_files(project_root, "GitHub template", GITHUB_FILES),
        "skill_frontmatter": check_skill_frontmatter(project_root),
        "runtime_artifacts": check_runtime_artifacts(project_root),
        "git_state": check_git_state(project_root),
    }
    statuses = [row["status"] for row in checks.values()]
    if "error" in statuses or (strict and "warning" in statuses):
        status = "error"
    elif "warning" in statuses:
        status = "warning"
    else:
        status = "ok"
    return {
        "status": status,
        "project_root": str(project_root),
        "strict": strict,
        "checks": checks,
    }


def format_report(report: dict[str, Any]) -> str:
    lines = [f"Release readiness: {report['status']}", f"Project root: {report['project_root']}", ""]
    for name, row in report["checks"].items():
        lines.append(f"[{row['status']}] {name}: {row['message']}")
        for key in ("missing", "issues", "unprotected", "not_ignored"):
            if row.get(key):
                lines.append(f"  {key}: {row[key]}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
    parser.add_argument("--json", action="store_true", help="Print JSON.")
    return parser


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()
    report = build_release_report(args.project_root, strict=args.strict)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_report(report))
    return 0 if report["status"] in {"ok", "warning"} and not (args.strict and report["status"] == "warning") else 1


if __name__ == "__main__":
    raise SystemExit(main())

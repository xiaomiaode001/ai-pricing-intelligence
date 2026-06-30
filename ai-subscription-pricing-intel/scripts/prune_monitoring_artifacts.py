#!/usr/bin/env python3
"""Prune generated monitoring artifacts by retention policy."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
CONFIG_PATH = SKILL_ROOT / "config" / "retention.yml"
RAW_ROOT = SKILL_ROOT / "data" / "raw" / "appstoreprice"
NORMALIZED_ROOT = SKILL_ROOT / "data" / "normalized"
SNAPSHOTS_ROOT = SKILL_ROOT / "data" / "snapshots"
OUTPUTS_ROOT = SKILL_ROOT / "outputs"

APP_ID_TO_PRODUCT_KEY = {
    "6448311069": "chatgpt",
    "6473753684": "claude",
    "6477489729": "gemini",
    "6670324846": "grok",
}


@dataclass
class Artifact:
    path: Path
    kind: str


@dataclass
class SnapshotGroup:
    snapshot_id: str
    product_key: str = "unknown"
    observed_date: date | None = None
    artifacts: list[Artifact] = field(default_factory=list)
    metadata_sources: list[str] = field(default_factory=list)
    skip_reasons: list[str] = field(default_factory=list)


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def unquote_yaml_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value in {"null", "Null", "~"}:
        return None
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        return value


def read_simple_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload: dict[str, Any] = {}
    current_list: str | None = None
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if indent == 0 and ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value:
                payload[key] = unquote_yaml_scalar(value)
                current_list = None
            else:
                payload[key] = []
                current_list = key
            continue
        if indent >= 2 and current_list and line.startswith("- "):
            payload.setdefault(current_list, []).append(str(unquote_yaml_scalar(line[2:])))
    return payload


def load_config() -> dict[str, Any]:
    config = {
        "retention_days": 14,
        "retain_minimum_per_product": 2,
        "auto_cleanup_on_today": True,
        "protected_files": [".gitkeep", "data/fx/latest_fx_cny.json"],
    }
    config.update(read_simple_yaml(CONFIG_PATH))
    return config


def parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    text = str(value)
    if len(text) >= 10:
        text = text[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def mtime_date(paths: list[Artifact]) -> date | None:
    timestamps: list[float] = []
    for artifact in paths:
        try:
            timestamps.append(artifact.path.stat().st_mtime)
        except FileNotFoundError:
            continue
    if not timestamps:
        return None
    return datetime.fromtimestamp(max(timestamps), timezone.utc).date()


def ensure_group(groups: dict[str, SnapshotGroup], snapshot_id: str) -> SnapshotGroup:
    if snapshot_id not in groups:
        groups[snapshot_id] = SnapshotGroup(snapshot_id=snapshot_id)
    return groups[snapshot_id]


def add_artifact(groups: dict[str, SnapshotGroup], snapshot_id: str, path: Path, kind: str) -> None:
    ensure_group(groups, snapshot_id).artifacts.append(Artifact(path=path, kind=kind))


def normalized_snapshot_id(path: Path) -> str:
    return path.stem


def enriched_snapshot_id(path: Path) -> str:
    name = path.name
    if name.endswith(".enriched.json"):
        return name[: -len(".enriched.json")]
    return path.stem


def output_snapshot_id(path: Path) -> str | None:
    name = path.name
    for suffix in (".collect_summary.json", ".apple_spotcheck.json", ".daily.md", ".report.md"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return None


def product_from_snapshot_id(snapshot_id: str) -> str:
    prefix = snapshot_id.split("-", 1)[0].lower()
    return prefix or "unknown"


def apply_metadata(group: SnapshotGroup) -> None:
    group.product_key = product_from_snapshot_id(group.snapshot_id)
    dates: list[date] = []
    for artifact in group.artifacts:
        if artifact.kind == "summary":
            summary = read_json(artifact.path, {})
            if isinstance(summary, dict):
                if summary.get("product_key"):
                    group.product_key = str(summary["product_key"])
                monitor_date = parse_date(summary.get("monitor_date"))
                if monitor_date:
                    dates.append(monitor_date)
                    group.metadata_sources.append("summary.monitor_date")
        elif artifact.kind == "raw_dir":
            manifest = read_json(artifact.path / "manifest.json", {})
            if isinstance(manifest, dict):
                app_store_id = str(manifest.get("app_store_id") or "")
                if app_store_id in APP_ID_TO_PRODUCT_KEY:
                    group.product_key = APP_ID_TO_PRODUCT_KEY[app_store_id]
                captured_at = parse_date(manifest.get("captured_at"))
                if captured_at:
                    dates.append(captured_at)
                    group.metadata_sources.append("manifest.captured_at")
    if dates:
        group.observed_date = max(dates)
    else:
        group.observed_date = mtime_date(group.artifacts)
        if group.observed_date:
            group.metadata_sources.append("artifact.mtime")


def scan_groups() -> dict[str, SnapshotGroup]:
    groups: dict[str, SnapshotGroup] = {}
    if RAW_ROOT.exists():
        for path in RAW_ROOT.iterdir():
            if path.is_dir() and path.name != ".git":
                add_artifact(groups, path.name, path, "raw_dir")
    if NORMALIZED_ROOT.exists():
        for path in NORMALIZED_ROOT.iterdir():
            if path.is_file() and path.suffix in {".json", ".csv"} and path.name != ".gitkeep":
                add_artifact(groups, normalized_snapshot_id(path), path, "normalized")
    if SNAPSHOTS_ROOT.exists():
        for path in SNAPSHOTS_ROOT.iterdir():
            if path.is_file() and path.suffix == ".json" and path.name != ".gitkeep":
                add_artifact(groups, enriched_snapshot_id(path), path, "snapshot")
    if OUTPUTS_ROOT.exists():
        for path in OUTPUTS_ROOT.iterdir():
            if not path.is_file() or path.name == ".gitkeep":
                continue
            snapshot_id = output_snapshot_id(path)
            if not snapshot_id:
                continue
            kind = "output"
            if path.name.endswith(".collect_summary.json"):
                kind = "summary"
            elif path.name.endswith(".apple_spotcheck.json"):
                kind = "spotcheck"
            elif path.name.endswith(".daily.md") or path.name.endswith(".report.md"):
                kind = "report"
            add_artifact(groups, snapshot_id, path, kind)
    for group in groups.values():
        apply_metadata(group)
    return groups


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(SKILL_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def is_protected(path: Path, protected_files: list[str]) -> bool:
    rel = relative_path(path)
    return path.name in protected_files or rel in protected_files


def is_within_skill(path: Path) -> bool:
    try:
        path.resolve().relative_to(SKILL_ROOT.resolve())
        return True
    except ValueError:
        return False


def decide_prune(
    groups: dict[str, SnapshotGroup],
    retention_days: int,
    retain_minimum: int,
    product_key: str | None,
    today: date,
) -> tuple[list[SnapshotGroup], list[SnapshotGroup]]:
    candidates = [group for group in groups.values() if not product_key or group.product_key == product_key]
    by_product: dict[str, list[SnapshotGroup]] = {}
    for group in candidates:
        by_product.setdefault(group.product_key, []).append(group)
    for product_groups in by_product.values():
        product_groups.sort(
            key=lambda item: (
                item.observed_date or date.min,
                item.snapshot_id,
            ),
            reverse=True,
        )
        for index, group in enumerate(product_groups):
            if index < retain_minimum:
                group.skip_reasons.append("retain_minimum_per_product")
    delete_groups: list[SnapshotGroup] = []
    keep_groups: list[SnapshotGroup] = []
    for group in candidates:
        if not group.observed_date:
            group.skip_reasons.append("missing_observed_date")
        age_days = (today - group.observed_date).days if group.observed_date else None
        if age_days is not None and age_days <= retention_days:
            group.skip_reasons.append("within_retention_days")
        if age_days is not None and age_days > retention_days and not group.skip_reasons:
            delete_groups.append(group)
        else:
            keep_groups.append(group)
    return delete_groups, keep_groups


def delete_artifact(artifact: Artifact, protected_files: list[str], dry_run: bool) -> tuple[bool, str]:
    if not is_within_skill(artifact.path):
        return False, "outside_skill_root"
    if is_protected(artifact.path, protected_files):
        return False, "protected_file"
    if dry_run:
        return True, "dry_run"
    try:
        if artifact.path.is_dir():
            shutil.rmtree(artifact.path)
        else:
            artifact.path.unlink()
        return True, "deleted"
    except FileNotFoundError:
        return False, "already_missing"


def build_summary(
    groups: dict[str, SnapshotGroup],
    delete_groups: list[SnapshotGroup],
    keep_groups: list[SnapshotGroup],
    retention_days: int,
    retain_minimum: int,
    dry_run: bool,
    product_key: str | None,
    protected_files: list[str],
) -> dict[str, Any]:
    deleted_artifacts: list[str] = []
    skipped_artifacts: list[dict[str, str]] = []
    for group in delete_groups:
        for artifact in group.artifacts:
            ok, status = delete_artifact(artifact, protected_files, dry_run)
            if ok:
                deleted_artifacts.append(relative_path(artifact.path))
            else:
                skipped_artifacts.append({"path": relative_path(artifact.path), "reason": status})
    return {
        "status": "dry_run" if dry_run else "complete",
        "retention_days": retention_days,
        "retain_minimum_per_product": retain_minimum,
        "product_key": product_key or "all",
        "scanned_snapshot_count": len(groups),
        "expired_snapshot_count": len(delete_groups),
        "kept_snapshot_count": len(keep_groups),
        "deleted_artifact_count": 0 if dry_run else len(deleted_artifacts),
        "planned_delete_artifact_count": len(deleted_artifacts),
        "deleted_artifacts": deleted_artifacts,
        "skipped_artifacts": skipped_artifacts,
        "kept_snapshots": [
            {
                "snapshot_id": group.snapshot_id,
                "product_key": group.product_key,
                "observed_date": group.observed_date.isoformat() if group.observed_date else "",
                "reasons": group.skip_reasons,
            }
            for group in sorted(keep_groups, key=lambda item: item.snapshot_id)
        ],
        "expired_snapshots": [
            {
                "snapshot_id": group.snapshot_id,
                "product_key": group.product_key,
                "observed_date": group.observed_date.isoformat() if group.observed_date else "",
                "artifact_count": len(group.artifacts),
            }
            for group in sorted(delete_groups, key=lambda item: item.snapshot_id)
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--retention-days", type=int)
    parser.add_argument("--retain-minimum", type=int)
    parser.add_argument("--product-key", choices=["chatgpt", "claude", "gemini", "grok"])
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    config = load_config()
    retention_days = int(args.retention_days if args.retention_days is not None else config.get("retention_days", 14))
    retain_minimum = int(args.retain_minimum if args.retain_minimum is not None else config.get("retain_minimum_per_product", 2))
    protected_files = [str(item) for item in config.get("protected_files", [".gitkeep", "data/fx/latest_fx_cny.json"])]
    groups = scan_groups()
    delete_groups, keep_groups = decide_prune(groups, retention_days, retain_minimum, args.product_key, date.today())
    summary = build_summary(
        groups,
        delete_groups,
        keep_groups,
        retention_days,
        retain_minimum,
        args.dry_run,
        args.product_key,
        protected_files,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

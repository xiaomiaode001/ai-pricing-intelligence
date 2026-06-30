#!/usr/bin/env python3
"""Compare normalized/enriched App Store Price snapshots and write reports."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any


PRICE_CHANGE_THRESHOLD_PCT = 2.0
REGION_COUNT_DROP_THRESHOLD_PCT = 20.0


def read_rows(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def row_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (str(row.get("region", "")), str(row.get("iap_plan_label", "")), str(row.get("currency", "")))


def by_key(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    return {row_key(row): row for row in rows}


def plans(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("iap_plan_label", "")) for row in rows if row.get("iap_plan_label")}


def rows_for_plan(rows: list[dict[str, Any]], plan: str) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("iap_plan_label") == plan]


def boundary(rows: list[dict[str, Any]], status: str) -> dict[str, Any] | None:
    for row in rows:
        if row.get("price_status") == status:
            return row
    priced = [row for row in rows if isinstance(row.get("source_cny_price"), (int, float))]
    if not priced:
        return None
    return min(priced, key=lambda row: row["source_cny_price"]) if status == "lowest" else max(priced, key=lambda row: row["source_cny_price"])


def fmt_price(row: dict[str, Any] | None) -> str:
    if not row:
        return "missing"
    return f"{row.get('region', '')} {row.get('source_local_price', '')} / ¥{row.get('source_cny_price', '')}"


def detect_plan_changes(previous: list[dict[str, Any]], current: list[dict[str, Any]]) -> list[str]:
    old_plans = plans(previous)
    new_plans = plans(current)
    findings = []
    for plan in sorted(new_plans - old_plans):
        findings.append(f"- 新增套餐：{plan}")
    for plan in sorted(old_plans - new_plans):
        findings.append(f"- 消失套餐：{plan}")
    return findings


def detect_boundary_changes(previous: list[dict[str, Any]], current: list[dict[str, Any]]) -> list[str]:
    findings = []
    for plan in sorted(plans(previous) | plans(current)):
        old_rows = rows_for_plan(previous, plan)
        new_rows = rows_for_plan(current, plan)
        for status, label in (("lowest", "最低价地区"), ("highest", "最高价地区")):
            old = boundary(old_rows, status)
            new = boundary(new_rows, status)
            if row_key(old or {}) != row_key(new or {}):
                findings.append(f"- {plan} {label}变化：{fmt_price(old)} -> {fmt_price(new)}")
    return findings


def detect_price_changes(previous: list[dict[str, Any]], current: list[dict[str, Any]], threshold_pct: float = PRICE_CHANGE_THRESHOLD_PCT) -> list[str]:
    findings = []
    old_rows = by_key(previous)
    for row in current:
        old = old_rows.get(row_key(row))
        if not old:
            continue
        old_cny = old.get("source_cny_price")
        new_cny = row.get("source_cny_price")
        if not isinstance(old_cny, (int, float)) or not isinstance(new_cny, (int, float)) or old_cny == 0:
            continue
        delta_pct = round((new_cny - old_cny) / old_cny * 100, 4)
        if abs(delta_pct) > threshold_pct:
            findings.append(f"- {row.get('iap_plan_label')} / {row.get('region')}：¥{old_cny} -> ¥{new_cny} ({delta_pct:+.2f}%)")
    return findings


def detect_region_count_drop(previous: list[dict[str, Any]], current: list[dict[str, Any]]) -> list[str]:
    findings = []
    for plan in sorted(plans(previous) | plans(current)):
        old_count = len({row.get("region") for row in rows_for_plan(previous, plan)})
        new_count = len({row.get("region") for row in rows_for_plan(current, plan)})
        if old_count and new_count < old_count:
            drop_pct = round((old_count - new_count) / old_count * 100, 2)
            if drop_pct >= REGION_COUNT_DROP_THRESHOLD_PCT:
                findings.append(f"- {plan} 地区数量异常减少：{old_count} -> {new_count} ({drop_pct:.2f}%)")
    return findings


def detect_fx_mismatches(current: list[dict[str, Any]]) -> list[str]:
    return [
        f"- {row.get('iap_plan_label')} / {row.get('region')}：聚合价 ¥{row.get('source_cny_price')}，复算 ¥{row.get('computed_cny_price')}，偏差 {row.get('cny_delta_pct')}%"
        for row in current
        if row.get("fx_verification_status") == "fx_mismatch"
    ]


def detect_apple_conflicts(current: list[dict[str, Any]]) -> list[str]:
    return [
        f"- {row.get('iap_plan_label')} / {row.get('region')}：Apple storefront 抽样价与 App Store Price 聚合价冲突"
        for row in current
        if row.get("verification_status") == "conflict"
    ]


def anomaly_code_rows(
    boundary_changes: list[str],
    price_changes_2pct: list[str],
    price_changes_5pct: list[str],
    region_drops: list[str],
    plan_changes: list[str],
    apple_conflicts: list[str],
    fx_mismatches: list[str],
) -> list[str]:
    lowest_changed = [item for item in boundary_changes if "最低价地区" in item]
    highest_changed = [item for item in boundary_changes if "最高价地区" in item]
    plan_added = [item for item in plan_changes if "新增套餐" in item]
    plan_removed = [item for item in plan_changes if "消失套餐" in item]
    rows = [
        ("lowest_region_changed", lowest_changed),
        ("highest_region_changed", highest_changed),
        ("price_change_over_2pct", price_changes_2pct),
        ("price_change_over_5pct", price_changes_5pct),
        ("region_count_drop", region_drops),
        ("plan_added", plan_added),
        ("plan_removed", plan_removed),
        ("apple_spotcheck_conflict", apple_conflicts),
        ("fx_mismatch_over_threshold", fx_mismatches),
    ]
    return [f"- {code}: {'detected' if findings else 'none'}" for code, findings in rows]


def write_markdown(path: Path, title: str, sections: list[tuple[str, list[str]]], previous: Path, current: Path) -> None:
    lines = [
        f"# {title}",
        "",
        f"Generated: {date.today().isoformat()}",
        f"Previous snapshot: `{previous}`",
        f"Current snapshot: `{current}`",
        "",
    ]
    for heading, findings in sections:
        lines.extend([f"## {heading}", *(findings or ["- None detected."]), ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, help="Directory for change_log.md and anomaly_report.md")
    parser.add_argument("--change-log", type=Path)
    parser.add_argument("--anomaly-report", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    output_dir = args.output_dir or Path("outputs")
    change_log_path = args.change_log or output_dir / "change_log.md"
    anomaly_report_path = args.anomaly_report or output_dir / "anomaly_report.md"
    previous = read_rows(args.previous)
    current = read_rows(args.current)
    plan_changes = detect_plan_changes(previous, current)
    boundary_changes = detect_boundary_changes(previous, current)
    price_changes = detect_price_changes(previous, current, PRICE_CHANGE_THRESHOLD_PCT)
    price_changes_5pct = detect_price_changes(previous, current, 5.0)
    region_drops = detect_region_count_drop(previous, current)
    fx_mismatches = detect_fx_mismatches(current)
    apple_conflicts = detect_apple_conflicts(current)
    anomaly_codes = anomaly_code_rows(
        boundary_changes,
        price_changes,
        price_changes_5pct,
        region_drops,
        plan_changes,
        apple_conflicts,
        fx_mismatches,
    )
    write_markdown(
        change_log_path,
        "Snapshot Change Log",
        [
            ("Plan Changes", plan_changes),
            ("Boundary Changes", boundary_changes),
            ("Regional Price Changes > 2%", price_changes),
            ("Regional Price Changes > 5%", price_changes_5pct),
        ],
        args.previous,
        args.current,
    )
    write_markdown(
        anomaly_report_path,
        "Anomaly Report",
        [
            ("Anomaly Codes", anomaly_codes),
            ("Region Count Drops", region_drops),
            ("Apple Spotcheck Conflicts", apple_conflicts),
            ("FX Mismatches", fx_mismatches),
            ("Boundary Changes", boundary_changes),
        ],
        args.previous,
        args.current,
    )
    print(json.dumps({"change_log": str(change_log_path), "anomaly_report": str(anomaly_report_path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

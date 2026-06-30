#!/usr/bin/env python3
"""Generate a reader-friendly Markdown price-gap intelligence report."""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from datetime import date
from pathlib import Path
from typing import Any


def read_json(path: Path | None, default: Any) -> Any:
    if not path:
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return default


def read_text(path: Path | None) -> str:
    if not path:
        return ""
    try:
        return path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return ""


def display_text(value: Any, currency: str | None = None) -> str:
    text = "" if value is None else str(value)
    if not text:
        return ""
    replacements = {
        "楼": "¥",
        "拢": "£",
        "锛?": "，",
        "銆?": "。",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    if currency == "EUR":
        text = re.sub(r"鈧\S*", "€", text, count=1)
    elif currency == "KRW":
        text = re.sub(r"鈧\S*", "₩", text, count=1)
    elif currency == "INR":
        text = re.sub(r"鈧\S*", "₹", text, count=1)
    return text


def markdown_cell(value: Any) -> str:
    text = display_text(value).replace("\n", "<br>")
    return text.replace("|", r"\|") if text else "-"


def append_table(lines: list[str], headers: list[str], rows: list[list[Any]]) -> None:
    lines.append("| " + " | ".join(markdown_cell(header) for header in headers) + " |")
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for row in rows:
        lines.append("| " + " | ".join(markdown_cell(cell) for cell in row) + " |")
    lines.append("")


def row_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (str(row.get("region", "")), str(row.get("iap_plan_label", "")), str(row.get("currency", "")))


def fmt_cny(value: Any) -> str:
    try:
        return f"¥{float(value):,.2f}"
    except (TypeError, ValueError):
        return "-"


def fmt_number(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return "-"


def fmt_pct(value: Any) -> str:
    try:
        return f"{float(value):.2f}%"
    except (TypeError, ValueError):
        return "-"


def fmt_delta_pct(value: Any) -> str:
    try:
        return f"{float(value):+.2f}%"
    except (TypeError, ValueError):
        return "-"


def local_price(row: dict[str, Any] | None) -> str:
    if not row:
        return "-"
    return display_text(row.get("source_local_price") or "-", str(row.get("currency") or ""))


def priced_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if isinstance(row.get("source_cny_price"), (int, float))]


def filter_plan(rows: list[dict[str, Any]], plan: str) -> list[dict[str, Any]]:
    if not plan:
        return rows
    return [row for row in rows if row.get("iap_plan_label") == plan]


def pick_plan(rows: list[dict[str, Any]], plan: str | None) -> str:
    if plan:
        return plan
    counts: dict[str, int] = {}
    for row in rows:
        label = str(row.get("iap_plan_label", ""))
        if label:
            counts[label] = counts.get(label, 0) + 1
    if not counts:
        return ""
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def boundary(rows: list[dict[str, Any]], status: str) -> dict[str, Any] | None:
    for row in rows:
        if row.get("price_status") == status:
            return row
    priced = priced_rows(rows)
    if not priced:
        return None
    return min(priced, key=lambda row: row["source_cny_price"]) if status == "lowest" else max(priced, key=lambda row: row["source_cny_price"])


def us_baseline(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((row for row in rows if row.get("iso2") == "US" or row.get("region") in {"美国", "United States"}), None)


def median_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    priced = sorted(priced_rows(rows), key=lambda row: row["source_cny_price"])
    if not priced:
        return None
    median_value = statistics.median([row["source_cny_price"] for row in priced])
    return min(priced, key=lambda row: abs(row["source_cny_price"] - median_value))


def price_bar(value: Any, lowest: float | None, highest: float | None, width: int = 16) -> str:
    try:
        current = float(value)
    except (TypeError, ValueError):
        return "-"
    if lowest is None or highest is None or highest <= lowest:
        filled = width
    else:
        filled = 1 + round((current - lowest) / (highest - lowest) * (width - 1))
    filled = max(1, min(width, filled))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def spotcheck_lookup(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    return {row_key(row): row for row in rows}


def spot_status(row: dict[str, Any], spots: dict[tuple[str, str, str], dict[str, Any]]) -> str:
    spot = spots.get(row_key(row))
    if not spot:
        return "待复核"
    status = spot.get("spotcheck_status", "")
    verification = spot.get("verification_status", "")
    if verification == "conflict":
        return "冲突"
    if status == "ok":
        return "已复核"
    if status == "failed":
        return "复核失败"
    return str(verification or status or "待复核")


def fx_summary(rows: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    mismatches = [row for row in rows if row.get("fx_verification_status") == "fx_mismatch"]
    missing = [row for row in rows if row.get("fx_verification_status") == "fx_missing"]
    checked = [row for row in rows if row.get("fx_verification_status") == "fx_checked"]
    if mismatches:
        return f"{len(mismatches)} 个地区超过 1.5% 阈值", mismatches
    if missing:
        return f"{len(missing)} 个地区缺少汇率", mismatches
    if checked:
        return "复算一致", mismatches
    return "未复算", mismatches


def spotcheck_summary(spots: list[dict[str, Any]]) -> str:
    if not spots:
        return "未抽样"
    conflicts = sum(1 for row in spots if row.get("verification_status") == "conflict")
    failed = sum(1 for row in spots if row.get("spotcheck_status") == "failed")
    ok = sum(1 for row in spots if row.get("spotcheck_status") == "ok")
    if conflicts:
        return f"{ok} 个抽样完成，其中 {conflicts} 个冲突价"
    if failed:
        return f"{ok} 个抽样完成，{failed} 个复核失败"
    return f"{ok} 个抽样完成"


def discount_pct(price: float | None, baseline: float | None) -> float | None:
    if price is None or baseline in (None, 0):
        return None
    return round((baseline - price) / baseline * 100, 4)


def intelligence_level(discount_vs_baseline_pct: float | None, discount_vs_highest_pct: float | None) -> str:
    if discount_vs_baseline_pct is not None and discount_vs_baseline_pct > 15:
        return "high"
    if discount_vs_highest_pct is not None and discount_vs_highest_pct > 35:
        return "high"
    if discount_vs_baseline_pct is not None and 5 <= discount_vs_baseline_pct <= 15:
        return "medium"
    if discount_vs_baseline_pct is not None and 0 < discount_vs_baseline_pct < 5:
        return "low"
    return "none"


def intelligence_reason(level: str) -> str:
    return {
        "high": "最低价相比美国低 15% 以上，或相比最高价低 35% 以上。",
        "medium": "最低价相比美国低 5% 到 15%。",
        "low": "最低价相比美国低于 5%。",
        "none": "最低价接近或高于美国基准价，未形成明显价差信号。",
    }.get(level, "未形成明确价差信号。")


def unique_values(rows: list[dict[str, Any]], field: str) -> str:
    values: list[Any] = []
    for row in rows:
        value = row.get(field)
        if isinstance(value, list):
            for item in value:
                if item not in values:
                    values.append(item)
        elif value not in (None, "") and value not in values:
            values.append(value)
    return ", ".join(display_text(value) for value in values) or "-"


def plan_labels(rows: list[dict[str, Any]]) -> list[str]:
    labels: list[str] = []
    for row in rows:
        detected = row.get("plans_detected")
        if isinstance(detected, list):
            for item in detected:
                label = str(item)
                if label and label not in labels:
                    labels.append(label)
    for row in rows:
        label = str(row.get("iap_plan_label", ""))
        if label and label not in labels:
            labels.append(label)
    return labels


def top_low_rows(rows: list[dict[str, Any]], count: int = 3) -> list[dict[str, Any]]:
    return sorted(priced_rows(rows), key=lambda row: row["source_cny_price"])[:count]


def brief_price(row: dict[str, Any] | None) -> str:
    if not row:
        return "-"
    return f"{display_text(row.get('region', '-'))} / {local_price(row)} / {fmt_cny(row.get('source_cny_price'))}"


def brief_low3(rows: list[dict[str, Any]]) -> str:
    parts = []
    for idx, row in enumerate(top_low_rows(rows, 3), 1):
        fx_rate = row.get("fx_rate_to_cny")
        fx_text = f"FX {fmt_number(fx_rate, 6)}" if fx_rate is not None else "FX -"
        parts.append(
            f"{idx}. {display_text(row.get('region', '-'))} {local_price(row)} / "
            f"{fmt_cny(row.get('source_cny_price'))} / {fx_text} / "
            f"复算 {fmt_cny(row.get('computed_cny_price'))}"
        )
    return "<br>".join(parts) if parts else "-"


def infer_cycle_from_label(label: str) -> str:
    if re.search(r"\b1Y\b|1年|annual|yearly|year", label, re.I):
        return "1Y"
    if re.search(r"\b1M\b|1月|monthly|month", label, re.I):
        return "1M"
    if re.search(r"\b(credits?|tokens?|usage|points?|coins?)\b", label, re.I):
        return "usage"
    return "unknown"


def plan_spotcheck_state(label: str, spotchecks: list[dict[str, Any]]) -> str:
    plan_spots = [row for row in spotchecks if row.get("iap_plan_label") == label]
    if not plan_spots:
        return "pending_spotcheck"
    if any(row.get("verification_status") == "conflict" for row in plan_spots):
        return "conflict"
    if any(row.get("spotcheck_status") == "failed" for row in plan_spots):
        return "spotcheck_failed"
    if any(row.get("spotcheck_status") == "ok" for row in plan_spots):
        return "apple_spot_checked"
    return "pending_spotcheck"


def plan_matrix_rows(all_rows: list[dict[str, Any]], spotchecks: list[dict[str, Any]] | None = None) -> list[list[Any]]:
    matrix: list[list[Any]] = []
    spotchecks = spotchecks or []
    for label in plan_labels(all_rows):
        plan_rows = [row for row in all_rows if row.get("iap_plan_label") == label]
        priced = priced_rows(plan_rows)
        if not priced:
            matrix.append([label, infer_cycle_from_label(label), "0", "needs_snapshot", "-", "-", "-", "-", "needs_snapshot", "needs_snapshot"])
            continue
        low = boundary(plan_rows, "lowest") or min(priced, key=lambda row: row["source_cny_price"])
        high = boundary(plan_rows, "highest") or max(priced, key=lambda row: row["source_cny_price"])
        baseline = us_baseline(plan_rows)
        low_cny = float(low["source_cny_price"]) if isinstance(low.get("source_cny_price"), (int, float)) else None
        high_cny = float(high["source_cny_price"]) if isinstance(high.get("source_cny_price"), (int, float)) else None
        baseline_cny = float(baseline["source_cny_price"]) if baseline and isinstance(baseline.get("source_cny_price"), (int, float)) else None
        level = intelligence_level(discount_pct(low_cny, baseline_cny), discount_pct(low_cny, high_cny))
        matrix.append(
            [
                label,
                str(plan_rows[0].get("billing_cycle") or infer_cycle_from_label(label)),
                str(len({row.get("region") for row in plan_rows})),
                brief_low3(plan_rows),
                brief_price(baseline),
                brief_price(high),
                fmt_pct(discount_pct(low_cny, baseline_cny)),
                fmt_pct(discount_pct(low_cny, high_cny)),
                level,
                plan_spotcheck_state(label, spotchecks),
            ]
        )
    return matrix


def anomaly_flags(change_log: str, anomaly_report: str, rows: list[dict[str, Any]], spotchecks: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    combined = f"{change_log}\n{anomaly_report}"
    checks = [
        ("lowest_region_changed", "最低价地区变化", "最低价地区变化" in combined or "Lowest region changed" in combined),
        ("highest_region_changed", "最高价地区变化", "最高价地区变化" in combined or "Highest region changed" in combined),
        ("price_change_over_2pct", "单地区价格变化超过 2%", "Regional Price Changes > 2%" in combined or "价格变化" in combined),
        ("price_change_over_5pct", "单地区价格变化超过 5%", any(token in combined for token in ["+5.", "+6.", "+7.", "+8.", "+9.", "+10.", "-5.", "-6.", "-7.", "-8.", "-9.", "-10."])),
        ("region_count_drop", "地区数量异常减少", "地区数量异常减少" in combined or "Region Count Drops" in combined),
        ("plan_added", "套餐新增", "新增套餐" in combined or "Plans added" in combined),
        ("plan_removed", "套餐消失", "消失套餐" in combined or "Plans removed" in combined),
        ("apple_spotcheck_conflict", "Apple 抽样冲突", any(row.get("verification_status") == "conflict" for row in spotchecks)),
        ("fx_mismatch_over_threshold", "FX 偏差超过阈值", any(row.get("fx_verification_status") == "fx_mismatch" for row in rows)),
    ]
    return [(code, label, "detected" if active else "none") for code, label, active in checks]


def compact_markdown(text: str, heading: str, max_items: int = 5) -> list[str]:
    if not text:
        return []
    lines = [line for line in text.splitlines() if line.startswith("- ")]
    if not lines:
        return []
    return [heading, *lines[:max_items]]


def build_daily_report(
    rows: list[dict[str, Any]],
    spotchecks: list[dict[str, Any]],
    plan: str,
) -> str:
    all_rows = rows
    rows = filter_plan(rows, plan)
    priced = sorted(priced_rows(rows), key=lambda row: row["source_cny_price"])
    if not rows:
        raise SystemExit("No rows matched the selected plan")

    product = display_text(rows[0].get("product") or "")
    provider = display_text(rows[0].get("provider") or "")
    snapshot_id = str(rows[0].get("snapshot_id") or "")
    observed_at = str(rows[0].get("observed_at") or date.today().isoformat())
    source_url = str(rows[0].get("source_url") or "")
    official_url = str(rows[0].get("official_pricing_url") or "")
    selected_spotchecks = [row for row in spotchecks if not row.get("iap_plan_label") or row.get("iap_plan_label") == plan]

    lowest = boundary(rows, "lowest") or (priced[0] if priced else None)
    highest = boundary(rows, "highest") or (priced[-1] if priced else None)
    baseline = us_baseline(rows)
    lowest_cny = float(lowest["source_cny_price"]) if lowest and isinstance(lowest.get("source_cny_price"), (int, float)) else None
    highest_cny = float(highest["source_cny_price"]) if highest and isinstance(highest.get("source_cny_price"), (int, float)) else None
    baseline_cny = float(baseline["source_cny_price"]) if baseline and isinstance(baseline.get("source_cny_price"), (int, float)) else None
    spread = highest_cny - lowest_cny if lowest_cny is not None and highest_cny is not None else None
    saving = lowest.get("saving_pct") if lowest else None
    if saving is None and spread is not None and highest_cny:
        saving = spread / highest_cny * 100
    discount_vs_baseline = discount_pct(lowest_cny, baseline_cny)
    discount_vs_highest = discount_pct(lowest_cny, highest_cny)
    intel_level = intelligence_level(discount_vs_baseline, discount_vs_highest)
    fx_text, fx_mismatches = fx_summary(rows)
    spots = spotcheck_lookup(selected_spotchecks)
    apple_text = spotcheck_summary(selected_spotchecks)
    conflicts = [row for row in selected_spotchecks if row.get("verification_status") == "conflict"]
    failed_spots = [row for row in selected_spotchecks if row.get("spotcheck_status") == "failed"]
    pending_count = sum(1 for row in top_low_rows(rows, 3) if row_key(row) not in spots)
    region_count = rows[0].get("region_count") or len({row.get("region") for row in rows})
    fx_sources = unique_values(rows, "fx_source")
    fx_dates = unique_values(rows, "fx_rate_date")
    detected_plans = plan_labels(all_rows)
    detected_plan_text = "、".join(display_text(label) for label in detected_plans) or "-"

    lines: list[str] = [
        f"# {product or provider} iOS 全球套餐价格日常短报",
        "",
        f"检查时间：{observed_at}",
        f"套餐发现：{len(detected_plans)} 个（{detected_plan_text}）",
        f"重点套餐：{display_text(plan)}",
        f"snapshot_id：`{snapshot_id}`",
        "",
        "## 结论卡片",
        "",
        (
            f"{display_text(plan)} 当前最低为 **{display_text((lowest or {}).get('region', '-'))} {local_price(lowest)} / {fmt_cny(lowest_cny)}**，"
            f"美国基准为 **{display_text((baseline or {}).get('region', '-'))} {local_price(baseline)} / {fmt_cny(baseline_cny)}**，"
            f"最高为 **{display_text((highest or {}).get('region', '-'))} {local_price(highest)} / {fmt_cny(highest_cny)}**。"
            f"价差 **{fmt_cny(spread)}**，相对最高价省幅 **{fmt_pct(discount_vs_highest or saving)}**，"
            f"信息差等级：**{intel_level}**。"
        ),
        "",
    ]
    append_table(
        lines,
        ["指标", "结果"],
        [
            ["最低地区", f"{display_text((lowest or {}).get('region', '-'))} / {local_price(lowest)} / {fmt_cny(lowest_cny)}"],
            ["美国基准", f"{display_text((baseline or {}).get('region', '-'))} / {local_price(baseline)} / {fmt_cny(baseline_cny)}"],
            ["最高地区", f"{display_text((highest or {}).get('region', '-'))} / {local_price(highest)} / {fmt_cny(highest_cny)}"],
            ["价差空间", f"{fmt_cny(spread)} / {fmt_pct(saving)}"],
            ["相对美国折扣", fmt_pct(discount_vs_baseline)],
            ["相对最高价折扣", fmt_pct(discount_vs_highest)],
            ["信息差等级", f"{intel_level}：{intelligence_reason(intel_level)}"],
        ],
    )

    lines.extend(["## 全套餐价格矩阵", ""])
    append_table(
        lines,
        ["套餐", "周期", "地区数", "最低 3 地区 / 价格 / 汇率", "美国基准", "最高地区", "相对美国折扣", "相对最高折扣", "信息差等级", "Apple 复核状态"],
        plan_matrix_rows(all_rows, selected_spotchecks),
    )

    lines.extend(["## 重点套餐详情", ""])
    append_table(
        lines,
        ["产品", "iOS 套餐", "地区数", "最低地区", "最低 CNY", "美国基准 CNY", "最高地区", "最高 CNY", "差额 CNY", "信息差等级"],
        [
            [
                product or provider or "-",
                display_text(plan) or "-",
                str(region_count),
                display_text((lowest or {}).get("region", "-")),
                fmt_cny(lowest_cny),
                fmt_cny(baseline_cny),
                display_text((highest or {}).get("region", "-")),
                fmt_cny(highest_cny),
                fmt_cny(spread),
                intel_level,
            ]
        ],
    )

    lines.extend(["## 最低 3 地区", ""])
    append_table(
        lines,
        ["排名", "地区", "ISO2", "原币价格", "source_cny_price", "FX", "computed_cny_price", "FX 状态", "Apple 复核"],
        [
            [
                str(idx),
                display_text(row.get("region", "")),
                str(row.get("iso2", "")),
                local_price(row),
                fmt_cny(row.get("source_cny_price")),
                fmt_number(row.get("fx_rate_to_cny"), 6),
                fmt_cny(row.get("computed_cny_price")),
                str(row.get("fx_verification_status", "")),
                spot_status(row, spots),
            ]
            for idx, row in enumerate(top_low_rows(rows, 3), 1)
        ],
    )

    lines.extend(["## 准确性复核", ""])
    review_notes = []
    if conflicts:
        review_notes.append(f"{len(conflicts)} 个 Apple 抽样冲突")
    if failed_spots:
        review_notes.append(f"{len(failed_spots)} 个 Apple 抽样失败")
    if fx_mismatches:
        review_notes.append(f"{len(fx_mismatches)} 个 FX 偏差超过阈值")
    if pending_count:
        review_notes.append(f"{pending_count} 个最低 3 地区待 Apple 复核")
    append_table(
        lines,
        ["项目", "结果", "说明"],
        [
            ["App Store Price 聚合价", "主价格口径", "保留为 `source_cny_price`，不被覆盖"],
            ["汇率复算", f"{fx_text}；来源 {fx_sources}；日期 {fx_dates}", "`computed_cny_price` 只做 CNY 对照"],
            ["Apple 抽样", apple_text, "只抽样复核，不覆盖聚合价"],
            ["冲突/待复核项", "；".join(review_notes) if review_notes else "无明显冲突", "冲突时并列展示并标记 `conflict`"],
        ],
    )
    if selected_spotchecks:
        append_table(
            lines,
            ["地区", "App Store Price 聚合价", "Apple 抽样价", "spotcheck_status", "verification_status"],
            [
                [
                    display_text(row.get("region", "")),
                    display_text(row.get("appstoreprice_local_price", "")),
                    display_text(row.get("apple_price_raw", "")) or "-",
                    str(row.get("spotcheck_status", "")),
                    str(row.get("verification_status", "")),
                ]
                for row in selected_spotchecks
            ],
        )

    lines.extend(
        [
            "## Sources",
            "",
            f"- App Store Price: {source_url or '-'}",
            "- Apple storefront: see 准确性复核 table",
            "- FX source: see 准确性复核 table and row fields",
            f"- Official context: {official_url or '-'}",
            "",
            "限制：本报告只覆盖 iOS IAP 地区价；不提供跨区购买教程，不判断跨区订阅可行性。",
            "",
        ]
    )
    return "\n".join(lines)


def build_report(
    rows: list[dict[str, Any]],
    spotchecks: list[dict[str, Any]],
    plan: str,
    change_log: str,
    anomaly_report: str,
) -> str:
    all_rows = rows
    rows = filter_plan(rows, plan)
    priced = sorted(priced_rows(rows), key=lambda row: row["source_cny_price"])
    if not rows:
        raise SystemExit("No rows matched the selected plan")

    product = display_text(rows[0].get("product") or "")
    provider = display_text(rows[0].get("provider") or "")
    snapshot_id = str(rows[0].get("snapshot_id") or "")
    captured_at = str(rows[0].get("captured_at") or "")
    observed_at = str(rows[0].get("observed_at") or date.today().isoformat())
    source_url = str(rows[0].get("source_url") or "")
    official_url = str(rows[0].get("official_pricing_url") or "")
    capture_method = str(rows[0].get("capture_method") or "")
    parser_version = str(rows[0].get("parser_version") or "")
    raw_snapshot_path = str(rows[0].get("raw_snapshot_path") or "")

    selected_spotchecks = [row for row in spotchecks if not row.get("iap_plan_label") or row.get("iap_plan_label") == plan]
    lowest = boundary(rows, "lowest") or (priced[0] if priced else None)
    highest = boundary(rows, "highest") or (priced[-1] if priced else None)
    baseline = us_baseline(rows)
    median = median_row(rows)
    lowest_cny = float(lowest["source_cny_price"]) if lowest and isinstance(lowest.get("source_cny_price"), (int, float)) else None
    highest_cny = float(highest["source_cny_price"]) if highest and isinstance(highest.get("source_cny_price"), (int, float)) else None
    baseline_cny = float(baseline["source_cny_price"]) if baseline and isinstance(baseline.get("source_cny_price"), (int, float)) else None
    spread = highest_cny - lowest_cny if lowest_cny is not None and highest_cny is not None else None
    saving = lowest.get("saving_pct") if lowest else None
    if saving is None and spread is not None and highest_cny:
        saving = spread / highest_cny * 100
    discount_vs_baseline = discount_pct(lowest_cny, baseline_cny)
    discount_vs_highest = discount_pct(lowest_cny, highest_cny)
    intel_level = intelligence_level(discount_vs_baseline, discount_vs_highest)
    fx_text, fx_mismatches = fx_summary(rows)
    spots = spotcheck_lookup(selected_spotchecks)
    apple_text = spotcheck_summary(selected_spotchecks)
    anomalies = anomaly_flags(change_log, anomaly_report, rows, selected_spotchecks)
    plans_detected = unique_values(all_rows, "plans_detected")
    region_count = rows[0].get("region_count") or len({row.get("region") for row in rows})
    fx_sources = unique_values(rows, "fx_source")
    fx_dates = unique_values(rows, "fx_rate_date")

    lines: list[str] = [
        f"# {product or provider} iOS 全球订阅价差信息差报告",
        "",
        f"检查时间：{observed_at}",
        f"产品/套餐：{product or provider} / {display_text(plan)}",
        f"snapshot_id：`{snapshot_id}`",
        "",
        "## 结论卡片",
        "",
        (
            f"{display_text(plan)} 当前最低为 **{display_text((lowest or {}).get('region', '-'))} {local_price(lowest)} / {fmt_cny(lowest_cny)}**，"
            f"最高为 **{display_text((highest or {}).get('region', '-'))} {local_price(highest)} / {fmt_cny(highest_cny)}**，"
            f"价差 **{fmt_cny(spread)}**，低价区相对高价区约低 **{fmt_pct(discount_vs_highest or saving)}**，"
            f"信息差等级：**{intel_level}**。"
        ),
        "",
    ]

    append_table(
        lines,
        ["指标", "结果", "判断"],
        [
            ["最低地区", f"{display_text((lowest or {}).get('region', '-'))} / {local_price(lowest)} / {fmt_cny(lowest_cny)}", "信息差入口"],
            ["最高地区", f"{display_text((highest or {}).get('region', '-'))} / {local_price(highest)} / {fmt_cny(highest_cny)}", "高价锚点"],
            ["美国基准", f"{display_text((baseline or {}).get('region', '-'))} / {local_price(baseline)} / {fmt_cny((baseline or {}).get('source_cny_price'))}", "对照区"],
            ["价差空间", f"{fmt_cny(spread)} / {fmt_pct(saving)}", "越高越值得监测"],
            ["相对美国折扣", fmt_pct(discount_vs_baseline), "信息差等级输入"],
            ["相对最高价折扣", fmt_pct(discount_vs_highest), "信息差等级输入"],
            ["信息差等级", intel_level, intelligence_reason(intel_level)],
            ["汇率复算", fx_text, "只校验 CNY，不覆盖聚合价"],
            ["Apple 抽样", apple_text, "冲突并列展示"],
        ],
    )

    lines.extend(["## 套餐发现结果", ""])
    append_table(
        lines,
        ["字段", "结果"],
        [
            ["plans_detected", plans_detected],
            ["plan_count", str(len(plan_labels(all_rows)))],
            ["selected_plan", display_text(plan) or "-"],
            ["snapshot_id", snapshot_id or "-"],
            ["captured_at", captured_at or "-"],
            ["capture_method", capture_method or "-"],
            ["parser_version", parser_version or "-"],
            ["region_count", str(region_count)],
            ["raw_snapshot_path", raw_snapshot_path or "-"],
        ],
    )
    append_table(
        lines,
        ["套餐", "周期", "地区数", "最低 3 地区 / 价格 / 汇率", "美国基准", "最高地区", "相对美国折扣", "相对最高折扣", "信息差等级", "Apple 复核状态"],
        plan_matrix_rows(all_rows, selected_spotchecks),
    )

    lines.extend(["## 单套餐全球概览", ""])
    append_table(
        lines,
        ["产品", "iOS 套餐", "地区数", "最低地区", "最低 CNY", "美国基准 CNY", "最高地区", "最高 CNY", "差额 CNY", "信息差等级"],
        [
            [
                product or provider or "-",
                display_text(plan) or "-",
                str(region_count),
                display_text((lowest or {}).get("region", "-")),
                fmt_cny(lowest_cny),
                fmt_cny(baseline_cny),
                display_text((highest or {}).get("region", "-")),
                fmt_cny(highest_cny),
                fmt_cny(spread),
                intel_level,
            ]
        ],
    )
    lines.extend(["当前套餐最低 3 个地区：", ""])
    append_table(
        lines,
        ["低价排名", "地区", "ISO2", "原币价格", "source_cny_price", "fx_rate_to_cny", "computed_cny_price", "FX 状态"],
        [
            [
                str(idx),
                display_text(row.get("region", "")),
                str(row.get("iso2", "")),
                local_price(row),
                fmt_cny(row.get("source_cny_price")),
                fmt_number(row.get("fx_rate_to_cny"), 6),
                fmt_cny(row.get("computed_cny_price")),
                str(row.get("fx_verification_status", "")),
            ]
            for idx, row in enumerate(top_low_rows(rows, 3), 1)
        ],
    )
    lines.extend(["全球价格矩阵：", ""])
    radar_rows: list[list[Any]] = []
    for label, row in [("最低", lowest), ("美国基准", baseline), ("中位附近", median), ("最高", highest)]:
        if not row:
            continue
        cny = row.get("source_cny_price")
        vs_lowest = float(cny) - lowest_cny if lowest_cny is not None and isinstance(cny, (int, float)) else None
        radar_rows.append(
            [
                label,
                display_text(row.get("region", "-")),
                str(row.get("iso2", "-")),
                local_price(row),
                fmt_cny(cny),
                fmt_cny(vs_lowest),
                price_bar(cny, lowest_cny, highest_cny),
            ]
        )
    append_table(lines, ["位置", "地区", "ISO2", "聚合价", "CNY", "比最低贵", "价格条"], radar_rows)

    lines.extend(["## Top 10 低价区", ""])
    append_table(
        lines,
        ["排名", "地区", "ISO2", "聚合价", "source_cny_price", "computed_cny_price", "偏差", "Apple 抽样"],
        [
            [
                str(row.get("appstoreprice_rank", "")),
                display_text(row.get("region", "")),
                str(row.get("iso2", "")),
                local_price(row),
                fmt_cny(row.get("source_cny_price")),
                fmt_cny(row.get("computed_cny_price")),
                fmt_delta_pct(row.get("cny_delta_pct")),
                spot_status(row, spots),
            ]
            for row in priced[:10]
        ],
    )

    lines.extend(["## Top 5 高价区", ""])
    append_table(
        lines,
        ["排名", "地区", "ISO2", "聚合价", "source_cny_price", "computed_cny_price", "偏差", "Apple 抽样"],
        [
            [
                str(row.get("appstoreprice_rank", "")),
                display_text(row.get("region", "")),
                str(row.get("iso2", "")),
                local_price(row),
                fmt_cny(row.get("source_cny_price")),
                fmt_cny(row.get("computed_cny_price")),
                fmt_delta_pct(row.get("cny_delta_pct")),
                spot_status(row, spots),
            ]
            for row in list(reversed(priced[-5:]))
        ],
    )

    lines.extend(["## 汇率复算摘要", ""])
    append_table(
        lines,
        ["项目", "值"],
        [
            ["使用汇率源", fx_sources],
            ["汇率日期", fx_dates],
            ["FX 检查阈值", "1.5%"],
            ["复算结论", fx_text],
            ["是否覆盖 source_cny_price", "否，computed_cny_price 只作校验"],
        ],
    )
    append_table(
        lines,
        ["地区", "原币价格", "source_cny_price", "computed_cny_price", "偏差", "fx_verification_status"],
        [
            [
                display_text(row.get("region", "")),
                local_price(row),
                fmt_cny(row.get("source_cny_price")),
                fmt_cny(row.get("computed_cny_price")),
                fmt_delta_pct(row.get("cny_delta_pct")),
                str(row.get("fx_verification_status", "")),
            ]
            for row in (fx_mismatches[:10] if fx_mismatches else priced[:5])
        ],
    )

    lines.extend(["## Apple storefront 抽样复核", ""])
    if selected_spotchecks:
        append_table(
            lines,
            ["地区", "App Store Price 聚合价", "Apple 抽样价", "spotcheck_status", "verification_status"],
            [
                [
                    display_text(row.get("region", "")),
                    display_text(row.get("appstoreprice_local_price", "")),
                    display_text(row.get("apple_price_raw", "")) or "-",
                    str(row.get("spotcheck_status", "")),
                    str(row.get("verification_status", "")),
                ]
                for row in selected_spotchecks
            ],
        )
    else:
        lines.extend(["未提供 Apple 抽样复核结果。", ""])

    lines.extend(["## 与上一快照对比", ""])
    append_table(lines, ["异常代码", "含义", "状态"], [[code, label, status] for code, label, status in anomalies])
    anomaly_items = compact_markdown(change_log, "快照变化明细") + compact_markdown(anomaly_report, "异常检测明细")
    if anomaly_items:
        lines.extend(anomaly_items + [""])

    lines.extend(["## 信息差判断", ""])
    if baseline and lowest and baseline_cny is not None and lowest_cny is not None:
        baseline_delta = baseline_cny - lowest_cny
        lines.append(f"- 美国基准差：最低区比美国低 {fmt_cny(baseline_delta)}，折扣 {fmt_pct(discount_vs_baseline)}。")
    lines.append(f"- 最高价折扣：最低区相比最高价低 {fmt_pct(discount_vs_highest)}。")
    lines.append(f"- 信息差等级：{intel_level}。{intelligence_reason(intel_level)}")
    lines.append(
        f"- 低价区信号：{display_text((lowest or {}).get('region', '-'))} 是当前最低聚合价地区，应保留原币、CNY、FX、Apple 抽样状态。"
    )
    conflicts = [row for row in selected_spotchecks if row.get("verification_status") == "conflict"]
    if conflicts:
        lines.append(f"- 冲突处理：{len(conflicts)} 个 Apple 抽样冲突价必须与 App Store Price 聚合价并列表达，不自动覆盖。")
    if fx_mismatches:
        lines.append(f"- 汇率处理：{len(fx_mismatches)} 个地区标记 fx_mismatch，进入待复核。")
    lines.append("")

    lines.extend(
        [
            "## 准确性与限制",
            "",
            "- App Store Price 是全地区 iOS IAP 聚合价来源；Apple storefront 只做抽样复核。",
            "- App Store Price 的 CNY 字段保留为 `source_cny_price`。",
            "- Skill 汇率复算的 CNY 字段命名为 `computed_cny_price`，只用于检查折算偏差。",
            "- 当 `source_cny_price` 与 `computed_cny_price` 偏差超过 1.5% 时，标记 `fx_mismatch`。",
            "- 不使用 `computed_cny_price` 覆盖 `source_cny_price`。",
            "- 不使用 Apple 抽样价覆盖 App Store Price 聚合价。",
            "- 冲突数据必须并列表达并标记 `conflict`，不自动合并。",
            "- 本报告不提供跨区购买教程，不判断跨区订阅可行性。",
            "",
            "## Sources",
            "",
            f"- App Store Price: {source_url or '-'}",
            "- Apple storefront spot checks: see Apple storefront 抽样复核 table",
            "- FX source: see 汇率复算摘要 table and row fields",
            f"- Official context: {official_url or '-'}",
            "",
        ]
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Enriched snapshot JSON")
    parser.add_argument("--spotcheck", type=Path, help="Apple spotcheck JSON")
    parser.add_argument("--change-log", type=Path, help="Optional change_log.md")
    parser.add_argument("--anomaly-report", type=Path, help="Optional anomaly_report.md")
    parser.add_argument("--plan", help="Plan label to report")
    parser.add_argument("--mode", choices=["daily", "full"], default="daily", help="Report depth: daily short report or full 11-module report.")
    parser.add_argument("--output", type=Path, help="Markdown output path")
    return parser


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()
    rows = read_json(args.input, [])
    if not isinstance(rows, list):
        raise SystemExit("input JSON must be a list of rows")
    plan = pick_plan(rows, args.plan)
    spotchecks = read_json(args.spotcheck, [])
    if not isinstance(spotchecks, list):
        spotchecks = []
    if args.mode == "full":
        report = build_report(rows, spotchecks, plan, read_text(args.change_log), read_text(args.anomaly_report))
    else:
        report = build_daily_report(rows, spotchecks, plan)
    snapshot_id = str(rows[0].get("snapshot_id") or "snapshot") if rows else "snapshot"
    output = args.output or Path("outputs") / f"{snapshot_id}.{'report' if args.mode == 'full' else 'daily'}.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print(json.dumps({"output": str(output), "mode": args.mode, "plan": plan, "row_count": len(filter_plan(rows, plan))}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

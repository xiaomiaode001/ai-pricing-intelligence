#!/usr/bin/env python3
"""Parse an App Store Price raw snapshot into normalized JSON and CSV."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any


PARSER_VERSION = "appstoreprice-parser-v2"
APP_DEFAULTS = {
    "6448311069": {"provider": "OpenAI", "product": "ChatGPT", "official_pricing_url": "https://chatgpt.com/pricing/"},
    "6473753684": {"provider": "Anthropic", "product": "Claude", "official_pricing_url": "https://claude.com/pricing"},
    "6477489729": {"provider": "Google", "product": "Google Gemini", "official_pricing_url": "https://gemini.google/subscriptions/"},
    "6670324846": {"provider": "xAI", "product": "Grok", "official_pricing_url": "https://x.ai/grok"},
}

CNY_RE = re.compile(r"¥\s*([0-9][0-9,]*(?:\.[0-9]+)?)")
RANK_ONLY_RE = re.compile(r"^\s*(\d{1,3})\s*$")
PLAN_HEADER_RE = re.compile(r"(.+?)\s+(?:Global Price|全球价格)")
SAVING_RE = re.compile(r"(?:比最高价省|save(?:s)?(?: vs highest)?|saving)\s*([0-9]+(?:\.[0-9]+)?)\s*%", re.I)
STATUS_MAP = {"lowest": "lowest", "最低": "lowest", "highest": "highest", "最高": "highest"}
LOCAL_PRICE_RE = re.compile(
    r"((?:[$€£₺₩¥]\s*)?[0-9][0-9,]*(?:\.[0-9]+)?\s*[A-Z]{3}|[A-Z]{3}\s*[0-9][0-9,]*(?:\.[0-9]+)?\s*[A-Z]{3})\s*$"
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_manifest(snapshot: Path) -> dict[str, Any]:
    manifest_path = snapshot / "manifest.json" if snapshot.is_dir() else snapshot
    return read_json(manifest_path)


def resolve_raw_path(manifest: dict[str, Any]) -> Path:
    raw_path = Path(manifest["raw_path"])
    if raw_path.exists():
        return raw_path
    manifest_dir = Path(manifest.get("_manifest_path", ".")).parent
    candidate = manifest_dir / raw_path.name
    if candidate.exists():
        return candidate
    raise FileNotFoundError(raw_path)


def clean_line(line: str) -> str:
    line = line.lstrip("\ufeff")
    line = re.sub(r"^L\d+:\s*", "", line.strip())
    return re.sub(r"\s+", " ", line).strip()


def text_lines(raw: str) -> list[str]:
    return [line for line in (clean_line(x) for x in raw.splitlines()) if line]


def strip_citations(text: str) -> str:
    text = re.sub(r"cite[^†]+†([^†]+)†apps\.apple\.com", r" \1 apps.apple.com ", text)
    text = re.sub(r"cite[^†]+†Image:\s*([^†]+)†[^]*", r" \1 ", text)
    text = re.sub(r"cite[^]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def detect_plan_headers(lines: list[str]) -> list[tuple[int, str]]:
    headers = []
    for idx, line in enumerate(lines):
        match = PLAN_HEADER_RE.search(strip_citations(line))
        if match:
            plan = re.sub(r"\s+", " ", match.group(1)).strip()
            if plan and (not headers or headers[-1][1] != plan):
                headers.append((idx, plan))
    return headers


def plan_for_index(index: int, headers: list[tuple[int, str]], explicit_plan: str | None) -> str:
    if explicit_plan and not headers:
        return explicit_plan
    active = "unknown"
    for header_idx, plan in headers:
        if header_idx <= index:
            active = plan
        else:
            break
    return active


def normalize_plan_name(iap_plan_label: str) -> str:
    plan = re.sub(r"\b1M\b|\b1Y\b|1月|1年|monthly|annual|yearly", "", iap_plan_label, flags=re.I)
    return re.sub(r"\s+", " ", plan).strip() or iap_plan_label


def infer_billing_cycle(iap_plan_label: str) -> str:
    if re.search(r"\b1Y\b|1年|annual|yearly|year", iap_plan_label, re.I):
        return "1Y"
    if re.search(r"\b1M\b|1月|monthly|month", iap_plan_label, re.I):
        return "1M"
    if re.search(r"credits?", iap_plan_label, re.I):
        return "usage"
    return "unknown"


def parse_currency(local_price: str) -> str:
    tokens = re.findall(r"\b[A-Z]{3}\b", local_price)
    return tokens[-1] if tokens else "unknown"


def parse_local_amount(local_price: str) -> float | None:
    without_currency = re.sub(r"\b[A-Z]{3}\b", " ", local_price)
    match = re.search(r"[-+]?[0-9][0-9,]*(?:\.[0-9]+)?", without_currency)
    return float(match.group(0).replace(",", "")) if match else None


def format_amount(value: Any) -> str:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return ""
    if abs(amount - round(amount)) < 0.000001:
        return f"{int(round(amount)):,}"
    text = f"{amount:,.2f}".rstrip("0").rstrip(".")
    return text


def format_local_price(amount: Any, currency: str) -> str:
    currency = currency.upper()
    formatted = format_amount(amount)
    symbols = {
        "USD": "$",
        "EUR": "€",
        "GBP": "£",
        "JPY": "¥",
        "KRW": "₩",
        "TRY": "₺",
    }
    symbol = symbols.get(currency)
    if symbol:
        return f"{symbol}{formatted} {currency}"
    return f"{currency}{formatted} {currency}"


def parse_cny(text: str) -> float | None:
    matches = list(CNY_RE.finditer(text))
    if not matches:
        return None
    return float(matches[-1].group(1).replace(",", ""))


def extract_saving_pct(lines: list[str], start: int, end: int) -> float | None:
    joined = " ".join(strip_citations(line) for line in lines[start:end])
    match = SAVING_RE.search(joined)
    return float(match.group(1)) if match else None


def extract_region(text: str) -> str:
    cleaned = strip_citations(text)
    cleaned = re.sub(r"https?://\S+", " ", cleaned)
    cleaned = cleaned.replace("apps.apple.com", " ")
    cleaned = re.sub(r"Image:\s*", " ", cleaned)
    cleaned = re.sub(r"[†\[\]（）()|]", " ", cleaned)
    cleaned = re.sub(r"[^A-Za-z\u4e00-\u9fff ]", " ", cleaned)
    tokens = re.sub(r"\s+", " ", cleaned).strip().split()
    if len(tokens) >= 2 and tokens[0] == tokens[1]:
        return tokens[0]
    if len(tokens) % 2 == 0:
        midpoint = len(tokens) // 2
        if tokens[:midpoint] == tokens[midpoint:]:
            return " ".join(tokens[:midpoint])
    return " ".join(tokens) or "unknown"


def extract_storefront_url(text: str) -> str:
    match = re.search(r"https?://apps\.apple\.com/\S+", text)
    if match:
        return match.group(0).rstrip(").,]")
    return "apps.apple.com" if "apps.apple.com" in text else ""


def looks_like_local_price(text: str) -> bool:
    if re.search(r"\b[A-Z]{3}\b", text) and re.search(r"[0-9]", text):
        return True
    if CNY_RE.search(text):
        return False
    return bool(re.search(r"[$€£₺₩]\s*[0-9]|¥\s*[0-9].*\bJPY\b", text))


def parse_compact_row(line: str) -> dict[str, Any] | None:
    cleaned = strip_citations(line)
    cny_matches = list(CNY_RE.finditer(cleaned))
    if not cny_matches:
        return None
    rank_match = re.match(r"^\s*(\d{1,3})\s*(.+)$", cleaned)
    if not rank_match:
        return None
    local_area = cleaned[rank_match.start(2) : cny_matches[-1].start()].strip()
    local_match = LOCAL_PRICE_RE.search(local_area)
    if not local_match:
        return None
    local_price = local_match.group(1).strip()
    region = extract_region(local_area[: local_match.start()].strip())
    return {
        "appstoreprice_rank": int(rank_match.group(1)),
        "region": region,
        "storefront_country": region,
        "apple_storefront_url": extract_storefront_url(line),
        "source_local_price": local_price,
        "local_price_amount": parse_local_amount(local_price),
        "source_cny_price": float(cny_matches[-1].group(1).replace(",", "")),
        "currency": parse_currency(local_price),
        "price_status": "normal",
    }


def parse_expanded_row(lines: list[str], index: int) -> dict[str, Any] | None:
    rank_match = RANK_ONLY_RE.match(lines[index])
    if not rank_match:
        return None
    window = lines[index + 1 : index + 8]
    region = "unknown"
    url = ""
    local_price = ""
    cny = None
    status = "normal"
    for item in window:
        stripped = strip_citations(item)
        lower = stripped.lower()
        if lower in STATUS_MAP:
            status = STATUS_MAP[lower]
        elif stripped in STATUS_MAP:
            status = STATUS_MAP[stripped]
        if region == "unknown" and ("apps.apple.com" in item or "Image:" in stripped):
            region = extract_region(item)
            url = extract_storefront_url(item)
        if not local_price and looks_like_local_price(stripped):
            local_price = stripped
        if cny is None and not looks_like_local_price(stripped):
            cny = parse_cny(stripped)
    if region == "unknown" or not local_price or cny is None:
        return None
    return {
        "appstoreprice_rank": int(rank_match.group(1)),
        "region": region,
        "storefront_country": region,
        "apple_storefront_url": url,
        "source_local_price": local_price,
        "local_price_amount": parse_local_amount(local_price),
        "source_cny_price": cny,
        "currency": parse_currency(local_price),
        "price_status": status,
    }


def strip_html_tags(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(text))).strip()


def decode_next_f_chunks(raw: str) -> str:
    chunks = []
    for match in re.finditer(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', raw, re.S):
        try:
            chunks.append(json.loads(f'"{match.group(1)}"'))
        except json.JSONDecodeError:
            continue
    return "\n".join(chunks)


def extract_json_object(text: str, start: int) -> str:
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return ""


def extract_catalog_app(raw: str) -> dict[str, Any] | None:
    decoded = decode_next_f_chunks(raw)
    marker = '"app":{'
    marker_index = decoded.find(marker)
    if marker_index == -1:
        return None
    start = decoded.find("{", marker_index + len('"app":'))
    if start == -1:
        return None
    object_text = extract_json_object(decoded, start)
    if not object_text:
        return None
    try:
        app = json.loads(object_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(app, dict) or not isinstance(app.get("subscriptions"), list):
        return None
    return app


def plan_label_from_subscription(subscription: dict[str, Any]) -> str:
    name = str(subscription.get("nameZh") or subscription.get("name") or "").strip()
    duration = str(subscription.get("duration") or "").lower()
    if duration == "monthly":
        return f"{name} 1月"
    if duration in {"yearly", "annual"}:
        return f"{name} 1年"
    return name


def catalog_rows(raw: str, manifest: dict[str, Any], plan: str | None) -> list[dict[str, Any]]:
    app = extract_catalog_app(raw)
    if not app:
        return []
    app_store_id = str(app.get("appStoreId") or manifest.get("app_store_id") or "")
    rows: list[dict[str, Any]] = []
    seen_plan_labels: set[str] = set()
    for subscription in app.get("subscriptions", []):
        plan_label = plan_label_from_subscription(subscription)
        if plan_label in seen_plan_labels:
            continue
        if plan and plan_label != plan:
            continue
        seen_plan_labels.add(plan_label)
        prices = subscription.get("prices", [])
        if not isinstance(prices, list):
            continue
        for rank, price in enumerate(prices, 1):
            if not isinstance(price, dict):
                continue
            region_code = str(price.get("region") or "").lower()
            currency = str(price.get("currency") or "").upper()
            amount = price.get("price")
            region_name = str(price.get("regionName") or price.get("region") or "").strip()
            rows.append(
                {
                    "appstoreprice_rank": rank,
                    "region": region_name,
                    "storefront_country": region_name,
                    "apple_storefront_url": f"https://apps.apple.com/{region_code}/app/id{app_store_id}"
                    if region_code and app_store_id
                    else "",
                    "source_local_price": format_local_price(amount, currency),
                    "local_price_amount": float(amount) if amount is not None else None,
                    "source_cny_price": float(price["priceCny"]) if price.get("priceCny") is not None else None,
                    "currency": currency,
                    "price_status": "normal",
                    "iap_plan_label": plan_label,
                }
            )
    return rows


def determine_extraction_mode(raw: str, rows: list[dict[str, Any]], catalog_available: bool) -> str:
    if not rows:
        return "missing"
    if catalog_available:
        return "catalog"
    if "<tr" in raw and "apps.apple.com" in raw and "<html" in raw.lower():
        return "html_table"
    return "copied_text"


def detect_html_plan(raw: str) -> str:
    text = strip_html_tags(raw)
    match = re.search(
        r"(ChatGPT\s+(?:Plus|Go|Pro(?:\s+\d+x)?)(?:\s+1月|\s+1年)?|\d+\s+Credits)\s+(?:Global Price|全球价格)",
        text,
    )
    if match:
        return re.sub(r"\s+", " ", match.group(1)).strip()
    return ""


def extract_html_saving_pct(raw: str) -> float | None:
    match = SAVING_RE.search(strip_html_tags(raw))
    return float(match.group(1)) if match else None


def parse_html_table_rows(raw: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for match in re.finditer(r"<tr\b[^>]*>.*?</tr>", raw, re.S | re.I):
        row_html = match.group(0)
        rank_match = re.search(r"<td\b[^>]*>\s*(\d{1,3})\s*</td>", row_html, re.S | re.I)
        if not rank_match:
            continue
        url_match = re.search(r'href="(https://apps\.apple\.com/[^"]+)"', row_html)
        region_match = re.search(r'<span class="hover:underline">([^<]+)</span>', row_html)
        if not region_match:
            region_match = re.search(r'<img\b[^>]*\balt="([^"]+)"', row_html)
        if not region_match:
            continue
        text = strip_html_tags(row_html)
        button_values = [
            strip_html_tags(button_html)
            for button_html in re.findall(r"<button\b[^>]*>(.*?)</button>", row_html, re.S | re.I)
        ]
        local_price = next((value for value in button_values if looks_like_local_price(value)), "")
        cny = None
        for value in button_values:
            if looks_like_local_price(value):
                continue
            cny = parse_cny(value)
            if cny is not None:
                break
        if cny is None:
            cny = parse_cny(text)
        if not local_price or cny is None:
            continue
        status = "normal"
        if "最低" in text or "bg-green" in row_html:
            status = "lowest"
        elif "最高" in text or "bg-red" in row_html:
            status = "highest"
        rows.append(
            {
                "appstoreprice_rank": int(rank_match.group(1)),
                "region": html.unescape(region_match.group(1)).strip(),
                "storefront_country": html.unescape(region_match.group(1)).strip(),
                "apple_storefront_url": html.unescape(url_match.group(1)) if url_match else "",
                "source_local_price": local_price,
                "local_price_amount": parse_local_amount(local_price),
                "source_cny_price": cny,
                "currency": parse_currency(local_price),
                "price_status": status,
            }
        )
    return rows


def dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    unique = []
    for row in sorted(rows, key=lambda item: (item["iap_plan_label"], item["appstoreprice_rank"])):
        key = (
            row["iap_plan_label"],
            row["appstoreprice_rank"],
            row["region"],
            row["source_local_price"],
            row["source_cny_price"],
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def apply_metrics(rows: list[dict[str, Any]], saving_by_plan: dict[str, float | None]) -> None:
    by_plan: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_plan.setdefault(row["iap_plan_label"], []).append(row)
    for plan, plan_rows in by_plan.items():
        priced = [row for row in plan_rows if row["source_cny_price"] is not None]
        if not priced:
            continue
        lowest = min(priced, key=lambda row: row["source_cny_price"])
        highest = max(priced, key=lambda row: row["source_cny_price"])
        spread = round(highest["source_cny_price"] - lowest["source_cny_price"], 2)
        saving = saving_by_plan.get(plan)
        if saving is None and highest["source_cny_price"]:
            saving = round(spread / highest["source_cny_price"] * 100, 2)
        for row in plan_rows:
            row["lowest_region"] = lowest["region"]
            row["lowest_cny"] = lowest["source_cny_price"]
            row["highest_region"] = highest["region"]
            row["highest_cny"] = highest["source_cny_price"]
            row["spread_cny"] = spread
            row["saving_pct"] = saving
            if row["region"] == lowest["region"] and row["source_cny_price"] == lowest["source_cny_price"]:
                row["price_status"] = "lowest"
            elif row["region"] == highest["region"] and row["source_cny_price"] == highest["source_cny_price"]:
                row["price_status"] = "highest"


def parse_rows(raw: str, manifest: dict[str, Any], plan: str | None, expected_row_count: int | None) -> list[dict[str, Any]]:
    catalog_available = extract_catalog_app(raw) is not None
    rows: list[dict[str, Any]] = catalog_rows(raw, manifest, plan)
    saving_by_plan: dict[str, float | None] = {}
    if rows:
        for plan_label in {row["iap_plan_label"] for row in rows}:
            saving_by_plan[plan_label] = None
    is_html_raw = "<tr" in raw and "apps.apple.com" in raw and "<html" in raw.lower()
    if not rows and not catalog_available and is_html_raw:
        html_plan = plan or detect_html_plan(raw) or "unknown"
        saving_by_plan[html_plan] = extract_html_saving_pct(raw)
        for row in parse_html_table_rows(raw):
            row["iap_plan_label"] = html_plan
            rows.append(row)
    elif not rows and not catalog_available:
        lines = text_lines(raw)
        headers = detect_plan_headers(lines)
        if plan and plan not in [p for _, p in headers]:
            headers = [(0, plan)] if not headers else headers
        if not headers:
            headers = [(0, plan or "unknown")]
        header_positions = headers + [(len(lines), "")]
        for hidx, (start, plan_label) in enumerate(headers):
            end = header_positions[hidx + 1][0]
            saving_by_plan[plan_label] = extract_saving_pct(lines, start, end)
        for idx, line in enumerate(lines):
            plan_label = plan_for_index(idx, headers, plan)
            if plan and plan_label != plan:
                continue
            compact = parse_compact_row(line)
            row = compact or parse_expanded_row(lines, idx)
            if not row:
                continue
            row["iap_plan_label"] = plan_label
            rows.append(row)

    rows = dedupe_rows(rows)
    actual_count = len(rows)
    expected = expected_row_count
    if expected is None and not (plan and (catalog_available or manifest.get("extraction_mode") == "catalog")):
        expected = manifest.get("row_count") or 0
    warnings = []
    if expected and actual_count < int(expected):
        warnings.append(f"row_count_below_expected: parsed {actual_count}, expected {expected}")
    apply_metrics(rows, saving_by_plan)
    region_count_by_plan: dict[str, int] = {}
    for plan_label in {row["iap_plan_label"] for row in rows}:
        region_count_by_plan[plan_label] = len({row["region"] for row in rows if row["iap_plan_label"] == plan_label})
    parsed_plans = {row["iap_plan_label"] for row in rows}
    detected_plans = [str(item) for item in manifest.get("plans_detected", []) if item]
    if plan and catalog_available and plan not in parsed_plans:
        warnings.append(f"plan_not_found_in_catalog: {plan}")
    elif not plan:
        missing_plans = [item for item in detected_plans if item not in parsed_plans]
        if missing_plans:
            warnings.append(f"detected_plans_without_rows: {', '.join(missing_plans)}")
    extraction_mode = determine_extraction_mode(raw, rows, catalog_available)
    warning = "; ".join(warnings)

    app_defaults = APP_DEFAULTS.get(str(manifest.get("app_store_id", "")), {})
    normalized = []
    for row in rows:
        plan_label = row["iap_plan_label"]
        normalized.append(
            {
                "snapshot_id": manifest["snapshot_id"],
                "captured_at": manifest.get("captured_at", ""),
                "capture_method": manifest.get("capture_method", ""),
                "parser_version": manifest.get("parser_version") or PARSER_VERSION,
                "plans_detected": manifest.get("plans_detected", []),
                "region_count": region_count_by_plan.get(plan_label, 0),
                "extraction_mode": extraction_mode,
                "quality_status": manifest.get("quality_status", ""),
                "raw_snapshot_path": manifest.get("raw_path", ""),
                "provider": manifest.get("provider") or app_defaults.get("provider", ""),
                "product": manifest.get("product") or app_defaults.get("product", ""),
                "app_store_id": manifest.get("app_store_id", ""),
                "source_url": manifest.get("source_url", ""),
                "official_pricing_url": app_defaults.get("official_pricing_url", ""),
                "iap_plan_label": plan_label,
                "plan_name": normalize_plan_name(plan_label),
                "billing_cycle": infer_billing_cycle(plan_label),
                "platform_scope": "iOS IAP",
                "observed_at": (manifest.get("captured_at") or date.today().isoformat())[:10],
                "verification_status": "appstoreprice_only",
                "parse_warning": warning,
                "notes": "App Store Price aggregated row; Apple storefront not spot-checked by parser.",
                **row,
            }
        )
    return normalized


def write_outputs(rows: list[dict[str, Any]], json_output: Path, csv_output: Path) -> None:
    json_output.parent.mkdir(parents=True, exist_ok=True)
    csv_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with csv_output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def default_output_paths(snapshot_id: str, output_dir: Path) -> tuple[Path, Path]:
    return output_dir / f"{snapshot_id}.json", output_dir / f"{snapshot_id}.csv"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path, help="Snapshot directory or manifest.json")
    parser.add_argument("--plan")
    parser.add_argument("--expected-row-count", type=int)
    parser.add_argument("--output-dir", type=Path, default=Path("data/normalized"))
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--csv-output", type=Path)
    return parser


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()
    manifest_path = args.snapshot / "manifest.json" if args.snapshot.is_dir() else args.snapshot
    manifest = read_json(manifest_path)
    manifest["_manifest_path"] = str(manifest_path)
    raw = resolve_raw_path(manifest).read_text(encoding="utf-8-sig")
    rows = parse_rows(raw, manifest, args.plan, args.expected_row_count)
    json_output, csv_output = default_output_paths(manifest["snapshot_id"], args.output_dir)
    if args.json_output:
        json_output = args.json_output
    if args.csv_output:
        csv_output = args.csv_output
    write_outputs(rows, json_output, csv_output)
    warnings = sorted({row.get("parse_warning", "") for row in rows if row.get("parse_warning")})
    modes = sorted({row.get("extraction_mode", "") for row in rows if row.get("extraction_mode")})
    print(json.dumps({
        "json_output": str(json_output),
        "csv_output": str(csv_output),
        "row_count": len(rows),
        "plan_count": len({row.get("iap_plan_label") for row in rows}),
        "extraction_mode": modes[0] if len(modes) == 1 else modes,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))
    return 0 if rows else 2


if __name__ == "__main__":
    raise SystemExit(main())

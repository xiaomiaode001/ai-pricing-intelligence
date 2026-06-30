#!/usr/bin/env python3
"""Best-effort Apple storefront spot checks for selected normalized rows."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def row_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (str(row.get("region", "")), str(row.get("iap_plan_label", "")), str(row.get("currency", "")))


def dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped = []
    seen = set()
    for row in rows:
        key = row_key(row)
        if key not in seen:
            deduped.append(row)
            seen.add(key)
    return deduped


def select_rows(rows: list[dict[str, Any]], mode: str, regions: list[str]) -> list[dict[str, Any]]:
    if regions:
        wanted = {region.lower() for region in regions}
        return [row for row in rows if str(row.get("region", "")).lower() in wanted]
    if mode == "top10-low":
        return sorted(rows, key=lambda row: row.get("source_cny_price") or 10**9)[:10]
    if mode == "high":
        low_rows = sorted(rows, key=lambda row: row.get("source_cny_price") or 10**9)[:10]
        high_rows = sorted(rows, key=lambda row: row.get("source_cny_price") or -1, reverse=True)[:5]
        us = next((row for row in rows if row.get("iso2") == "US" or row.get("region") in {"美国", "United States"}), None)
        return dedupe_rows([*low_rows, *([us] if us else []), *high_rows])

    low_rows = sorted(rows, key=lambda row: row.get("source_cny_price") or 10**9)[:3]
    selected: list[dict[str, Any]] = []
    selected.extend(low_rows)
    us = next((row for row in rows if row.get("iso2") == "US" or row.get("region") in {"美国", "United States"}), None)
    if us:
        selected.append(us)
    highest = next((row for row in rows if row.get("price_status") == "highest"), None)
    if not highest:
        priced = [row for row in rows if isinstance(row.get("source_cny_price"), (int, float))]
        highest = max(priced, key=lambda row: row["source_cny_price"]) if priced else None
    if highest:
        selected.append(highest)
    return dedupe_rows(selected)


def storefront_url(row: dict[str, Any]) -> str:
    url = str(row.get("apple_storefront_url") or "")
    if url.startswith("http"):
        return url
    code = str(row.get("apple_storefront_code") or "").lower()
    app_id = str(row.get("app_store_id") or "")
    if code and app_id:
        return f"https://apps.apple.com/{code}/app/id{app_id}"
    return url


def read_fixture(row: dict[str, Any], fixture_dir: Path | None) -> str | None:
    if not fixture_dir:
        return None
    candidates = [
        f"{row.get('iso2', '')}.html",
        f"{row.get('iso2', '')}.txt",
        f"{row.get('region', '')}.html",
        f"{row.get('region', '')}.txt",
    ]
    for name in candidates:
        if not name or name.startswith("."):
            continue
        path = fixture_dir / name
        if path.exists():
            return path.read_text(encoding="utf-8-sig")
    return None


def fetch_url(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "ai-subscription-pricing-intel/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        content_type = response.headers.get("content-type", "")
        charset = "utf-8"
        match = re.search(r"charset=([^;]+)", content_type, re.I)
        if match:
            charset = match.group(1).strip()
        return response.read().decode(charset, errors="replace")


def parse_amount_candidates(token: str, currency: str) -> list[float]:
    compact = re.sub(r"\s+", "", token)
    zero_decimal_like = {"COP", "CLP", "IDR", "JPY", "KRW", "KZT", "NGN", "PKR", "VND"}
    candidates: list[float] = []
    if currency in zero_decimal_like and re.fullmatch(r"\d{1,3}(?:\.\d{3})+", compact):
        candidates.append(float(compact.replace(".", "")))
    if currency in zero_decimal_like and re.fullmatch(r"\d{1,3}(?:,\d{3})+", compact):
        candidates.append(float(compact.replace(",", "")))
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", compact):
        candidates.append(float(compact.replace(".", "")))
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+", compact):
        candidates.append(float(compact.replace(",", "")))
    try:
        candidates.append(float(compact.replace(",", "")))
    except ValueError:
        pass

    deduped: list[float] = []
    for value in candidates:
        if not any(abs(value - existing) < 0.000001 for existing in deduped):
            deduped.append(value)
    return deduped


def parse_price_candidates(text: str, currency: str) -> list[tuple[float, str]]:
    currency = currency.upper()
    patterns = [
        rf"([A-Z]{{3}}\s*)?([0-9][0-9,]*(?:\.[0-9]+)?)\s*{re.escape(currency)}",
        rf"([$€£₺₩¥]\s*[0-9][0-9,]*(?:\.[0-9]+)?)",
    ]
    candidates: list[tuple[float, str]] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            raw = match.group(0)
            num = re.search(r"[0-9][0-9,]*(?:\.[0-9]+)?", raw)
            if not num:
                continue
            for amount in parse_amount_candidates(num.group(0), currency):
                candidates.append((amount, raw.strip()))
    return candidates


def choose_price_candidate(
    candidates: list[tuple[float, str]], expected: float | None
) -> tuple[float | None, str, str, str]:
    if not candidates:
        return None, "", "failed", "price not found"
    if expected is not None:
        tolerance = max(0.01, abs(expected) * 0.01)
        matches = [(amount, raw) for amount, raw in candidates if abs(amount - expected) <= tolerance]
        if matches:
            amount, raw = matches[0]
            return amount, raw, "ok", ""

    unique_amounts: list[tuple[float, str]] = []
    for amount, raw in candidates:
        if not any(abs(amount - existing) < 0.000001 for existing, _ in unique_amounts):
            unique_amounts.append((amount, raw))
    if len(unique_amounts) > 1:
        preview = ", ".join(raw for _, raw in unique_amounts[:5])
        return None, preview, "ambiguous", "multiple Apple prices found; plan-specific price not confirmed"
    amount, raw = unique_amounts[0]
    return amount, raw, "ok", ""


def parse_price(text: str, currency: str, expected: float | None = None) -> tuple[float | None, str, str, str]:
    candidates = parse_price_candidates(text, currency)
    return choose_price_candidate(candidates, expected)


def amounts_match(amount: float, expected: float) -> bool:
    tolerance = max(0.01, abs(expected) * 0.01)
    return abs(amount - expected) <= tolerance


def local_amount(row: dict[str, Any]) -> float | None:
    value = row.get("local_price_amount")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def check_row(row: dict[str, Any], fixture_dir: Path | None) -> dict[str, Any]:
    url = storefront_url(row)
    source = "network"
    try:
        text = read_fixture(row, fixture_dir)
        if text is not None:
            source = "fixture"
        else:
            if not url.startswith("http"):
                raise ValueError("missing Apple storefront URL")
            text = fetch_url(url)
        expected = local_amount(row)
        amount, raw_price, parse_status, parse_error = parse_price(text, str(row.get("currency", "")), expected)
        if amount is None:
            return build_result(row, url, parse_status, "manual_review", source, raw_price, None, parse_error)
        conflict = expected is not None and not amounts_match(amount, expected)
        return build_result(
            row,
            url,
            "ok",
            "conflict" if conflict else "apple_spot_checked",
            source,
            raw_price,
            amount,
            "Apple storefront price differs from App Store Price" if conflict else "",
        )
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        return build_result(row, url, "failed", "manual_review", source, "", None, str(exc))


def build_result(
    row: dict[str, Any],
    url: str,
    status: str,
    verification_status: str,
    source: str,
    apple_price_raw: str,
    apple_local_price_amount: float | None,
    error: str,
) -> dict[str, Any]:
    return {
        "snapshot_id": row.get("snapshot_id", ""),
        "region": row.get("region", ""),
        "iso2": row.get("iso2", ""),
        "iap_plan_label": row.get("iap_plan_label", ""),
        "currency": row.get("currency", ""),
        "appstoreprice_local_price": row.get("source_local_price", ""),
        "appstoreprice_local_price_amount": row.get("local_price_amount"),
        "apple_storefront_url": url,
        "apple_spotcheck_price": apple_price_raw,
        "apple_price_raw": apple_price_raw,
        "apple_local_price_amount": apple_local_price_amount,
        "spotcheck_status": status,
        "verification_status": verification_status,
        "spotcheck_source": source,
        "checked_at": now_utc(),
        "error": error,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Enriched or normalized JSON")
    parser.add_argument("--mode", choices=["default", "balanced", "high", "top10-low"], default="balanced")
    parser.add_argument("--plan", help="Limit spot checks to one iOS plan label")
    parser.add_argument("--regions", help="Comma-separated region names to spot-check")
    parser.add_argument("--fixture-dir", type=Path, help="Optional local Apple storefront fixtures")
    parser.add_argument("--output", type=Path, default=Path("outputs/apple_spotcheck.json"))
    return parser


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()
    rows = read_json(args.input)
    if args.plan:
        rows = [row for row in rows if row.get("iap_plan_label") == args.plan]
    regions = [item.strip() for item in (args.regions or "").split(",") if item.strip()]
    mode = "balanced" if args.mode == "default" else args.mode
    selected = select_rows(rows, mode, regions)
    results = [check_row(row, args.fixture_dir) for row in selected]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "row_count": len(results)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Enrich normalized App Store Price rows with country metadata and FX checks."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


MISMATCH_THRESHOLD_PCT = 1.5


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def parse_simple_country_map(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#") or line.strip() == "countries:":
            continue
        stripped = line.strip()
        if stripped.startswith("- "):
            if current:
                rows.append(current)
            current = {}
            stripped = stripped[2:].strip()
            if stripped:
                key, value = parse_yaml_scalar(stripped)
                current[key] = value
        elif current is not None and ":" in stripped:
            key, value = parse_yaml_scalar(stripped)
            current[key] = value
    if current:
        rows.append(current)
    return rows


def parse_yaml_scalar(line: str) -> tuple[str, str]:
    key, value = line.split(":", 1)
    value = value.strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1]
    return key.strip(), value


def build_country_lookup(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    lookup = {}
    for row in rows:
        keys = {
            row.get("region_name_zh", ""),
            row.get("region_name_en", ""),
            row.get("iso2", ""),
            row.get("iso3", ""),
            row.get("apple_storefront_code", ""),
        }
        for key in keys:
            if key:
                lookup[key.lower()] = row
    return lookup


def parse_local_amount(local_price: str) -> float | None:
    without_currency = re.sub(r"\b[A-Z]{3}\b", " ", local_price)
    match = re.search(r"[-+]?[0-9][0-9,]*(?:\.[0-9]+)?", without_currency)
    if not match:
        return None
    return float(match.group(0).replace(",", ""))


def rate_row_for(currency: str, fx_payload: dict[str, Any]) -> dict[str, Any] | None:
    return fx_payload.get("rates", {}).get(currency)


def storefront_code_from_url(url: str) -> str:
    match = re.search(r"apps\.apple\.com/([a-z]{2})/", url, re.I)
    return match.group(1).lower() if match else ""


def round_or_none(value: float | None, digits: int = 2) -> float | None:
    return round(value, digits) if value is not None else None


def enrich_row(row: dict[str, Any], country_lookup: dict[str, dict[str, str]], fx_payload: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(row)
    storefront_code = str(row.get("apple_storefront_code") or "").lower()
    if not storefront_code:
        storefront_code = storefront_code_from_url(str(row.get("apple_storefront_url", "")))
    country = (
        country_lookup.get(str(row.get("region", "")).lower())
        or country_lookup.get(storefront_code)
        or country_lookup.get(str(row.get("iso2", "")).lower())
        or {}
    )
    enriched["iso2"] = country.get("iso2", "")
    enriched["iso3"] = country.get("iso3", "")
    enriched["apple_storefront_code"] = country.get("apple_storefront_code", "") or storefront_code
    if not enriched.get("currency") and country.get("currency"):
        enriched["currency"] = country["currency"]

    currency = str(enriched.get("currency", "")).upper()
    fx_row = rate_row_for(currency, fx_payload) if currency else None
    source_cny = enriched.get("source_cny_price")
    try:
        source_cny_float = float(source_cny)
    except (TypeError, ValueError):
        source_cny_float = None
    amount = enriched.get("local_price_amount")
    try:
        amount = float(amount) if amount is not None else None
    except (TypeError, ValueError):
        amount = None
    if amount is None:
        amount = parse_local_amount(str(enriched.get("source_local_price", "")))
    enriched["local_price_amount"] = amount

    if not fx_row or fx_row.get("fx_status") != "ok" or amount is None or source_cny_float in (None, 0):
        enriched.update(
            {
                "fx_source": fx_row.get("fx_source", "") if fx_row else "",
                "fx_rate_date": fx_row.get("fx_rate_date", "") if fx_row else "",
                "fx_rate_to_cny": fx_row.get("fx_rate_to_cny") if fx_row else None,
                "computed_cny_price": None,
                "cny_delta": None,
                "cny_delta_pct": None,
                "fx_verification_status": "fx_missing",
                "rate_is_latest_business_day": fx_row.get("rate_is_latest_business_day", False) if fx_row else False,
            }
        )
        return enriched

    computed = round(amount * float(fx_row["fx_rate_to_cny"]), 2)
    delta = round(computed - source_cny_float, 2)
    delta_pct = round(delta / source_cny_float * 100, 4)
    enriched.update(
        {
            "fx_source": fx_row.get("fx_source", ""),
            "fx_rate_date": fx_row.get("fx_rate_date", ""),
            "fx_rate_to_cny": fx_row.get("fx_rate_to_cny"),
            "computed_cny_price": computed,
            "cny_delta": delta,
            "cny_delta_pct": delta_pct,
            "fx_verification_status": "fx_mismatch" if abs(delta_pct) > MISMATCH_THRESHOLD_PCT else "fx_checked",
            "rate_is_latest_business_day": bool(fx_row.get("rate_is_latest_business_day", False)),
        }
    )
    return enriched


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Normalized JSON from normalize_appstoreprice.py")
    parser.add_argument("--fx", type=Path, required=True, help="FX JSON from fetch_fx_rates.py")
    parser.add_argument("--country-map", type=Path, required=True, help="references/country-storefront-map.yml")
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()
    rows = read_json(args.input)
    if not isinstance(rows, list):
        raise SystemExit("input JSON must be a list of rows")
    country_lookup = build_country_lookup(parse_simple_country_map(args.country_map))
    fx_payload = read_json(args.fx)
    enriched = [enrich_row(row, country_lookup, fx_payload) for row in rows]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(enriched, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(enriched, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Fetch FX rates to CNY with 24-hour caching.

Primary source: Frankfurter API. Fallbacks: ECB-compatible Frankfurter provider
filter, ExchangeRate-API open access, then optional manual snapshot.
"""

from __future__ import annotations

import argparse
import http.client
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT = Path("data/fx/latest_fx_cny.json")
CACHE_SECONDS = 24 * 60 * 60
FRANKFURTER_API = "https://api.frankfurter.dev/v2"
FRANKFURTER_LEGACY_API = "https://api.frankfurter.app"
EXCHANGE_RATE_API = "https://open.er-api.com/v6/latest"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_currency_list(value: str) -> list[str]:
    currencies = []
    for item in value.replace(";", ",").split(","):
        code = item.strip().upper()
        if code and code not in currencies:
            currencies.append(code)
    return currencies


def currencies_from_normalized(path: Path) -> list[str]:
    payload = read_json(path)
    if not isinstance(payload, list):
        raise SystemExit("--normalized-json must point to a JSON list of rows")
    currencies = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        code = str(row.get("currency", "")).strip().upper()
        if code and code not in currencies:
            currencies.append(code)
    return currencies


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def cache_is_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    return time.time() - path.stat().st_mtime < CACHE_SECONDS


def cache_covers(payload: dict[str, Any], currencies: list[str], target: str) -> bool:
    if payload.get("target_currency") != target:
        return False
    rates = payload.get("rates", {})
    return all(code in rates and usable_cached_rate(rates.get(code)) for code in currencies)


def usable_cached_rate(row: Any) -> bool:
    return isinstance(row, dict) and row.get("fx_status") == "ok" and row.get("fx_rate_to_cny") is not None


def request_json(url: str, timeout: int = 20) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "ai-subscription-pricing-intel/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def is_latest_business_day(rate_date: str, request_date: str) -> bool:
    return bool(rate_date and request_date and rate_date < request_date)


def missing_rate(code: str, target: str, source: str, message: str) -> dict[str, Any]:
    return {
        "currency": code,
        "fx_source": source,
        "fx_rate_date": "",
        "fx_base_currency": code,
        "fx_target_currency": target,
        "fx_rate_to_cny": None,
        "fx_status": "missing",
        "rate_is_latest_business_day": False,
        "error": message,
    }


def parse_frankfurter_rate(data: dict[str, Any], target: str) -> float:
    rate = data.get("rate")
    if rate is None:
        rate = data.get("rates", {}).get(target)
    if rate is None:
        raise ValueError(f"{target} missing from Frankfurter response")
    return float(rate)


def direct_rate_from_frankfurter(code: str, target: str, provider: str | None = None) -> dict[str, Any]:
    query = {}
    if provider:
        query["providers"] = provider
    suffix = f"?{urllib.parse.urlencode(query)}" if query else ""
    urls = [
        f"{FRANKFURTER_API}/rate/{urllib.parse.quote(code)}/{urllib.parse.quote(target)}{suffix}",
        (
            f"{FRANKFURTER_LEGACY_API}/latest?"
            f"{urllib.parse.urlencode({'from': code, 'to': target})}"
        ),
    ]
    errors = []
    data: dict[str, Any] | None = None
    for url in urls:
        try:
            data = request_json(url)
            rate = parse_frankfurter_rate(data, target)
            break
        except (
            urllib.error.URLError,
            TimeoutError,
            ValueError,
            KeyError,
            AttributeError,
            json.JSONDecodeError,
            http.client.HTTPException,
            OSError,
        ) as exc:
            errors.append(f"{url}: {exc}")
    else:
        raise ValueError("; ".join(errors) or "Frankfurter returned no rate")
    source = "ecb_reference_rates" if provider == "ECB" else "frankfurter"
    rate_date = data.get("date", "") if data else ""
    return {
        "currency": code,
        "fx_source": source,
        "fx_rate_date": rate_date,
        "fx_base_currency": code,
        "fx_target_currency": target,
        "fx_rate_to_cny": rate,
        "fx_status": "ok",
        "rate_is_latest_business_day": is_latest_business_day(rate_date, date.today().isoformat()),
    }


def cross_rate_from_exchange_rate_api(code: str, target: str) -> dict[str, Any]:
    data = request_json(f"{EXCHANGE_RATE_API}/{urllib.parse.quote(code)}")
    if data.get("result") != "success":
        raise ValueError(data.get("error-type", "ExchangeRate-API error"))
    rate = data.get("rates", {}).get(target)
    if rate is None:
        raise ValueError(f"{target} missing from ExchangeRate-API response")
    raw_time = data.get("time_last_update_utc", "")
    rate_date = ""
    if raw_time:
        try:
            rate_date = datetime.strptime(raw_time, "%a, %d %b %Y %H:%M:%S %z").date().isoformat()
        except ValueError:
            rate_date = raw_time
    return {
        "currency": code,
        "fx_source": "exchangerate_api_open",
        "fx_rate_date": rate_date,
        "fx_base_currency": code,
        "fx_target_currency": target,
        "fx_rate_to_cny": float(rate),
        "fx_status": "ok",
        "rate_is_latest_business_day": is_latest_business_day(rate_date, date.today().isoformat()),
    }


def manual_rate(code: str, target: str, manual_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not manual_payload:
        return None
    rates = manual_payload.get("rates", {})
    row = rates.get(code)
    if row is None:
        return None
    if isinstance(row, dict):
        value = row.get("fx_rate_to_cny") or row.get("rate") or row.get(target)
        rate_date = row.get("fx_rate_date") or manual_payload.get("fx_rate_date", "")
    else:
        value = row
        rate_date = manual_payload.get("fx_rate_date", "")
    if value is None:
        return None
    return {
        "currency": code,
        "fx_source": "manual_fx_snapshot",
        "fx_rate_date": rate_date,
        "fx_base_currency": code,
        "fx_target_currency": target,
        "fx_rate_to_cny": float(value),
        "fx_status": "ok",
        "rate_is_latest_business_day": is_latest_business_day(rate_date, date.today().isoformat()),
    }


def fetch_one(code: str, target: str, manual_payload: dict[str, Any] | None) -> dict[str, Any]:
    if code == target:
        return {
            "currency": code,
            "fx_source": "identity",
            "fx_rate_date": date.today().isoformat(),
            "fx_base_currency": code,
            "fx_target_currency": target,
            "fx_rate_to_cny": 1.0,
            "fx_status": "ok",
            "rate_is_latest_business_day": False,
        }
    errors = []
    for label, fetcher in (
        ("frankfurter", lambda: direct_rate_from_frankfurter(code, target)),
        ("ecb_reference_rates", lambda: direct_rate_from_frankfurter(code, target, provider="ECB")),
        ("exchangerate_api_open", lambda: cross_rate_from_exchange_rate_api(code, target)),
    ):
        try:
            return fetcher()
        except (
            urllib.error.URLError,
            TimeoutError,
            ValueError,
            KeyError,
            AttributeError,
            json.JSONDecodeError,
            http.client.HTTPException,
            OSError,
        ) as exc:
            errors.append(f"{label}: {exc}")
    manual = manual_rate(code, target, manual_payload)
    if manual:
        return manual
    return missing_rate(code, target, "manual_fx_snapshot", "; ".join(errors) or "no source returned a rate")


def merge_with_cache(
    cached: dict[str, Any] | None,
    currencies: list[str],
    target: str,
    manual_payload: dict[str, Any] | None,
    use_cached_first: bool,
) -> dict[str, dict[str, Any]]:
    cached_rates = (cached or {}).get("rates", {}) if (cached or {}).get("target_currency") == target else {}
    output = {}
    for code in currencies:
        cached_row = cached_rates.get(code)
        if use_cached_first and usable_cached_rate(cached_row):
            row = dict(cached_rates[code])
            row["cache_status"] = "hit"
            output[code] = row
        else:
            row = fetch_one(code, target, manual_payload)
            if row.get("fx_status") == "missing" and usable_cached_rate(cached_row):
                row = dict(cached_row)
                row["cache_status"] = "stale_fallback"
                output[code] = row
                continue
            row["cache_status"] = "miss"
            output[code] = row
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--currencies", help="Comma-separated currency codes, e.g. PHP,USD,COP")
    parser.add_argument("--normalized-json", type=Path, help="Extract currencies from normalized App Store Price JSON")
    parser.add_argument("--target", default="CNY", help="Target currency. Defaults to CNY.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manual-fx-snapshot", type=Path, help="Optional JSON fallback with manual rates")
    parser.add_argument("--force", action="store_true", help="Ignore 24-hour cache and fetch again")
    return parser


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()
    currencies = parse_currency_list(args.currencies or "")
    if args.normalized_json:
        for code in currencies_from_normalized(args.normalized_json):
            if code not in currencies:
                currencies.append(code)
    if not currencies:
        raise SystemExit("Provide --currencies or --normalized-json")
    target = args.target.upper()
    cached = read_json(args.output)
    if not args.force and cached and cache_is_fresh(args.output) and cache_covers(cached, currencies, target):
        cached["cache_status"] = "fresh"
        print(json.dumps(cached, ensure_ascii=False, indent=2))
        return 0

    manual_payload = read_json(args.manual_fx_snapshot) if args.manual_fx_snapshot else None
    rates = merge_with_cache(cached, currencies, target, manual_payload, use_cached_first=not args.force)
    payload = {
        "generated_at": now_iso(),
        "target_currency": target,
        "cache_ttl_seconds": CACHE_SECONDS,
        "rates": rates,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

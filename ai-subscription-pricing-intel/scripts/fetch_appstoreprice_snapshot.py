#!/usr/bin/env python3
"""Create a raw App Store Price snapshot and manifest.

Manual snapshot is the default design. URL capture only happens when --url is
explicitly provided by the user.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


PARSER_VERSION = "appstoreprice-parser-v2"
DEFAULT_OUTPUT_ROOT = Path("data/raw/appstoreprice")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slugify(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip())
    return re.sub(r"-+", "-", value).strip("-").lower() or "snapshot"


def make_snapshot_id(product: str, app_store_id: str, captured_at: str, raw: str) -> str:
    stamp = captured_at.replace(":", "").replace("+", "z")
    digest = hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:8]
    return f"{slugify(product)}-{app_store_id}-{stamp}-{digest}"


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def fetch_url(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "ai-subscription-pricing-intel/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        content_type = response.headers.get("content-type", "")
        charset = "utf-8"
        match = re.search(r"charset=([^;]+)", content_type, re.I)
        if match:
            charset = match.group(1).strip()
        return response.read().decode(charset, errors="replace")


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


def extract_catalog_app(raw: str) -> dict | None:
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


def plan_label_from_subscription(subscription: dict) -> str:
    name = str(subscription.get("nameZh") or subscription.get("name") or "").strip()
    duration = str(subscription.get("duration") or "").lower()
    if duration == "monthly":
        return f"{name} 1月"
    if duration in {"yearly", "annual"}:
        return f"{name} 1年"
    return name


def catalog_stats(raw: str) -> dict:
    app = extract_catalog_app(raw)
    if not app:
        return {
            "catalog_detected": False,
            "catalog_plan_count": 0,
            "catalog_row_count": 0,
            "plans": [],
        }
    plans = []
    row_count = 0
    seen_labels = set()
    for subscription in app.get("subscriptions", []):
        if not isinstance(subscription, dict):
            continue
        label = plan_label_from_subscription(subscription)
        if not label or label in seen_labels:
            continue
        seen_labels.add(label)
        prices = subscription.get("prices", [])
        plans.append(label)
        if isinstance(prices, list):
            row_count += len([price for price in prices if isinstance(price, dict)])
    return {
        "catalog_detected": True,
        "catalog_plan_count": len(plans),
        "catalog_row_count": row_count,
        "plans": plans,
    }


def visible_text(raw: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def detect_plans(raw: str) -> list[str]:
    stats = catalog_stats(raw)
    if stats["catalog_detected"]:
        return stats["plans"][:50]
    plans = []
    text = visible_text(raw)
    patterns = [
        r"\b(ChatGPT\s+(?:Plus|Go|Pro(?:\s+\d+x)?)(?:\s+1月|\s+1年)?)\b",
        r"\b(\d+\s+Credits)\b",
        r"\b(Claude\s+(?:Pro|Max\s+\d+x)(?:\s+1月|\s+1年)?)\b",
        r"\b(Google AI\s+(?:Plus|Pro|Ultra)(?:\s*\([^)]+\))?(?:\s+1月|\s+1年)?)\b",
        r"\b([0-9]+\s*(?:GB|TB)(?:\s+1月|\s+1年)?)\b",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            plan = re.sub(r"\s+", " ", match.group(1)).strip()
            if len(plan) > 3 and plan not in plans:
                plans.append(plan)
    filtered = []
    for plan in plans:
        is_truncated_prefix = re.search(r"\d$", plan) and any(
            other != plan and other.startswith(plan) for other in plans
        )
        has_cycle_variant = not re.search(r"1月|1年", plan) and any(
            other != plan and other.startswith(f"{plan} ") and re.search(r"1月|1年", other)
            for other in plans
        )
        if not is_truncated_prefix and not has_cycle_variant:
            filtered.append(plan)
    return filtered[:50]


def estimate_row_count(raw: str) -> int:
    stats = catalog_stats(raw)
    if stats["catalog_detected"]:
        return int(stats["catalog_row_count"])
    html_rows = 0
    for match in re.finditer(r"<tr\b[^>]*>.*?</tr>", raw, re.S | re.I):
        row_html = match.group(0)
        if re.search(r"<td\b[^>]*>\s*\d{1,3}\s*</td>", row_html, re.S | re.I) and "apps.apple.com" in row_html:
            html_rows += 1
    if html_rows:
        return html_rows
    compact = 0
    for line in raw.splitlines():
        if re.search(r"^\s*\d{1,3}\s+.+?[A-Z]{3}\s*¥\s*[0-9]", line):
            compact += 1
    if compact:
        return compact
    return sum(1 for line in raw.splitlines() if re.match(r"^\s*\d{1,3}\s*$", line))


def extraction_mode(raw: str, status: str) -> str:
    if status == "failed":
        return "failed"
    if catalog_stats(raw)["catalog_detected"]:
        return "catalog"
    if estimate_row_count(raw):
        return "html_table" if "<tr" in raw and "<html" in raw.lower() else "copied_text"
    return "unknown"


def quality_status(status: str, plans: list[str], row_count: int) -> str:
    if status == "failed":
        return "failed"
    if row_count > 0:
        return "complete"
    if plans:
        return "partial"
    return "missing"


def choose_input(args: argparse.Namespace) -> tuple[str, str, str]:
    provided = [bool(args.html_file), bool(args.text_file), bool(args.text), bool(args.url)]
    if sum(provided) != 1:
        raise SystemExit("Provide exactly one of --html-file, --text-file, --text, or --url")
    if args.html_file:
        return read_text_file(args.html_file), "html_file", "raw.html"
    if args.text_file:
        return read_text_file(args.text_file), "text_file", "raw.txt"
    if args.text:
        return args.text, "text_inline", "raw.txt"
    try:
        return fetch_url(args.url), "url_authorized", "raw.html"
    except Exception as exc:  # keep failed URL captures auditable
        return f"URL capture failed: {exc}", "url_authorized", "raw.txt"


def write_snapshot(args: argparse.Namespace) -> Path:
    raw, capture_method, raw_name = choose_input(args)
    captured_at = now_utc()
    snapshot_id = args.snapshot_id or make_snapshot_id(args.product, args.app_store_id, captured_at, raw)
    snapshot_dir = args.output_root / snapshot_id
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    raw_path = snapshot_dir / raw_name
    raw_path.write_text(raw, encoding="utf-8")
    raw_bytes = raw.encode("utf-8")
    status = "failed" if raw.startswith("URL capture failed:") else "captured"
    stats = catalog_stats(raw) if status != "failed" else {
        "catalog_detected": False,
        "catalog_plan_count": 0,
        "catalog_row_count": 0,
        "plans": [],
    }
    plans_detected = [] if status == "failed" else detect_plans(raw)
    row_count = 0 if status == "failed" else estimate_row_count(raw)
    manifest = {
        "snapshot_id": snapshot_id,
        "provider": args.provider,
        "product": args.product,
        "app_store_id": args.app_store_id,
        "source_url": args.source_url or args.url or "",
        "captured_at": captured_at,
        "capture_method": capture_method,
        "parser_version": PARSER_VERSION,
        "raw_path": str(raw_path),
        "source_hash": f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}",
        "raw_size_bytes": len(raw_bytes),
        "row_count": row_count,
        "plans_detected": plans_detected,
        "extraction_mode": extraction_mode(raw, status),
        "catalog_detected": stats["catalog_detected"],
        "catalog_plan_count": stats["catalog_plan_count"],
        "catalog_row_count": stats["catalog_row_count"],
        "expected_plan_count": stats["catalog_plan_count"] or len(plans_detected),
        "quality_status": quality_status(status, plans_detected, row_count),
        "status": status,
    }
    (snapshot_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return snapshot_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html-file", type=Path)
    parser.add_argument("--text-file", type=Path)
    parser.add_argument("--text")
    parser.add_argument("--url")
    parser.add_argument("--provider", default="OpenAI")
    parser.add_argument("--product", default="ChatGPT")
    parser.add_argument("--app-store-id", default="6448311069")
    parser.add_argument("--source-url", default="")
    parser.add_argument("--snapshot-id")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    return parser


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()
    write_snapshot(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

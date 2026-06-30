#!/usr/bin/env python3
"""Run the App Store Price intelligence pipeline end to end."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
DATA_DIR = SKILL_ROOT / "data"
OUTPUTS_DIR = SKILL_ROOT / "outputs"
CONFIG_PATH = SKILL_ROOT / "config" / "product-monitoring.yml"
RETENTION_CONFIG_PATH = SKILL_ROOT / "config" / "retention.yml"

DEFAULT_PRODUCTS = {
    "chatgpt": {
        "provider": "OpenAI",
        "product": "ChatGPT",
        "app_store_id": "6448311069",
        "source_url": "https://appstoreprice.org/zh/apps/6448311069",
        "official_pricing_url": "https://chatgpt.com/pricing/",
        "default_report_plan": "ChatGPT Plus 1月",
        "aliases": ["GPT", "ChatGPT", "GPT套餐监测", "ChatGPT套餐监测"],
    },
    "claude": {
        "provider": "Anthropic",
        "product": "Claude",
        "app_store_id": "6473753684",
        "source_url": "https://appstoreprice.org/en/apps/6473753684",
        "official_pricing_url": "https://claude.com/pricing",
        "default_report_plan": "Claude Pro 1月",
        "aliases": ["Claude", "Claude套餐监测", "Anthropic套餐监测"],
    },
    "gemini": {
        "provider": "Google",
        "product": "Google Gemini",
        "app_store_id": "6477489729",
        "source_url": "https://appstoreprice.org/en/apps/6477489729",
        "official_pricing_url": "https://gemini.google/subscriptions/",
        "default_report_plan": "Google AI Pro (5 TB) 1月",
        "aliases": ["Gemini", "Google Gemini", "Gemini套餐监测", "Google AI套餐监测"],
    },
    "grok": {
        "provider": "xAI",
        "product": "Grok",
        "app_store_id": "6670324846",
        "source_url": "https://appstoreprice.org/en/apps/6670324846",
        "official_pricing_url": "https://x.ai/grok",
        "default_report_plan": "SuperGrok 1月",
        "aliases": ["Grok", "Gork", "xAI", "Grok套餐监测", "Gork套餐监测", "xAI套餐监测"],
    },
}


class PipelineError(RuntimeError):
    def __init__(self, step: str, result: subprocess.CompletedProcess[str]) -> None:
        self.step = step
        self.result = result
        detail = (result.stderr or result.stdout or "").strip()
        super().__init__(f"{step} failed with exit code {result.returncode}: {detail}")


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
    return value


def load_product_config(path: Path = CONFIG_PATH) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return DEFAULT_PRODUCTS
    text = path.read_text(encoding="utf-8-sig")
    stripped = text.lstrip()
    if stripped.startswith("{"):
        payload = json.loads(text)
        products = payload.get("products", payload)
        return products if isinstance(products, dict) else DEFAULT_PRODUCTS

    products: dict[str, dict[str, Any]] = {}
    current_key: str | None = None
    current_list_field: str | None = None
    in_products = False
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if indent == 0 and line == "products:":
            in_products = True
            continue
        if not in_products:
            continue
        if indent == 2 and line.endswith(":"):
            current_key = line[:-1].strip()
            products[current_key] = {}
            current_list_field = None
            continue
        if current_key is None:
            continue
        if indent == 4 and ":" in line:
            field, value = line.split(":", 1)
            field = field.strip()
            value = value.strip()
            if value == "":
                products[current_key][field] = []
                current_list_field = field
            else:
                products[current_key][field] = unquote_yaml_scalar(value)
                current_list_field = None
            continue
        if indent >= 6 and line.startswith("- ") and current_list_field:
            products[current_key].setdefault(current_list_field, []).append(unquote_yaml_scalar(line[2:]))

    return products or DEFAULT_PRODUCTS


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
            payload.setdefault(current_list, []).append(unquote_yaml_scalar(line[2:]))
    return payload


def load_retention_config(path: Path = RETENTION_CONFIG_PATH) -> dict[str, Any]:
    config = {
        "retention_days": 14,
        "retain_minimum_per_product": 2,
        "auto_cleanup_on_today": True,
    }
    config.update(read_simple_yaml(path))
    return config


def normalize_lookup(value: str) -> str:
    return re.sub(r"[\s_\-:：/]+", "", value.casefold())


def resolve_product_key(args: argparse.Namespace, products: dict[str, dict[str, Any]]) -> str:
    explicit = args.product_key or args.app
    if args.product_key:
        key = normalize_lookup(args.product_key)
        for product_key in products:
            if normalize_lookup(product_key) == key:
                return product_key
        raise SystemExit(f"Unknown product key: {args.product_key}")

    if args.intent_text:
        intent = normalize_lookup(args.intent_text)
        for product_key, config in products.items():
            candidates = [product_key, str(config.get("product", "")), str(config.get("provider", ""))]
            aliases = config.get("aliases", [])
            if isinstance(aliases, list):
                candidates.extend(str(alias) for alias in aliases)
            for candidate in candidates:
                normalized = normalize_lookup(candidate)
                if normalized and (normalized in intent or intent in normalized):
                    return product_key
        raise SystemExit(f"Could not map --intent-text to a configured product: {args.intent_text}")

    if explicit in products:
        return explicit
    normalized_explicit = normalize_lookup(explicit)
    for product_key in products:
        if normalize_lookup(product_key) == normalized_explicit:
            return product_key
    raise SystemExit(f"Unknown app/product key: {explicit}")


def run_step(step: str, cmd: list[str], allow_failure: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, cwd=SKILL_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0 and not allow_failure:
        raise PipelineError(step, result)
    return result


def parse_stdout_json(result: subprocess.CompletedProcess[str], default: Any) -> Any:
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return default


def run_cleanup(args: argparse.Namespace, product_key: str) -> tuple[str, int, dict[str, Any], str]:
    retention_config = load_retention_config()
    if not args.today:
        return "skipped_not_today", 0, {}, ""
    if args.skip_cleanup:
        return "skipped_by_flag", 0, {}, ""
    if not bool(retention_config.get("auto_cleanup_on_today", True)) and not args.cleanup_dry_run:
        return "disabled_by_config", 0, {}, ""

    cleanup_cmd = [
        sys.executable,
        str(SCRIPT_DIR / "prune_monitoring_artifacts.py"),
        "--product-key",
        product_key,
    ]
    if args.cleanup_dry_run:
        cleanup_cmd.append("--dry-run")
    result = run_step("cleanup", cleanup_cmd, allow_failure=True)
    summary = parse_stdout_json(result, {})
    if result.returncode != 0:
        return "failed", 0, summary if isinstance(summary, dict) else {}, (result.stderr or result.stdout).strip()
    deleted_count = int((summary or {}).get("deleted_artifact_count", 0)) if isinstance(summary, dict) else 0
    return str((summary or {}).get("status") or "complete"), deleted_count, summary if isinstance(summary, dict) else {}, ""


def slugify(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip())
    return re.sub(r"-+", "-", value).strip("-").lower() or "snapshot"


def today_snapshot_id(product_key: str, app_store_id: str) -> str:
    return f"{slugify(product_key)}-{app_store_id}-{date.today().strftime('%Y%m%d')}"


def ensure_one_input(args: argparse.Namespace) -> None:
    provided = [bool(args.url), bool(args.html_file), bool(args.text_file), bool(args.text)]
    if args.today and sum(provided) == 0:
        return
    if sum(provided) != 1:
        raise SystemExit("Provide exactly one of --url, --html-file, --text-file, or --text; or use --today with a configured product.")


def input_args(args: argparse.Namespace, default_url: str) -> list[str]:
    if args.url:
        return ["--url", args.url]
    if args.html_file:
        return ["--html-file", str(args.html_file)]
    if args.text_file:
        return ["--text-file", str(args.text_file)]
    if args.text:
        return ["--text", args.text]
    if args.today:
        return ["--url", default_url]
    raise SystemExit("No capture input provided")


def latest_valid_snapshot(raw_root: Path, app_store_id: str, current_snapshot_id: str) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for manifest_path in raw_root.glob("*/manifest.json"):
        manifest = read_json(manifest_path, {})
        if not isinstance(manifest, dict):
            continue
        if manifest.get("snapshot_id") == current_snapshot_id:
            continue
        if manifest.get("status") != "captured":
            continue
        if str(manifest.get("app_store_id") or "") != str(app_store_id):
            continue
        candidates.append(
            {
                "snapshot_id": manifest.get("snapshot_id", ""),
                "captured_at": manifest.get("captured_at", ""),
                "manifest_path": str(manifest_path),
            }
        )
    return sorted(candidates, key=lambda item: str(item.get("captured_at") or ""), reverse=True)[0] if candidates else {}


def write_capture_failed_report(
    path: Path,
    product: str,
    source_url: str,
    snapshot_id: str,
    manifest: dict[str, Any],
    previous_valid: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    previous_text = (
        f"{previous_valid.get('snapshot_id')} / {previous_valid.get('captured_at')}"
        if previous_valid
        else "未找到上一有效快照"
    )
    lines = [
        f"# {product} iOS 全球订阅价差信息差报告",
        "",
        "## 结论卡片",
        "",
        "当天 App Store Price 快照采集失败，未生成价格矩阵。",
        "",
        "| 字段 | 结果 |",
        "|---|---|",
        f"| snapshot_id | `{snapshot_id}` |",
        f"| source_url | {source_url or '-'} |",
        f"| capture_method | {manifest.get('capture_method', '-')} |",
        f"| captured_at | {manifest.get('captured_at', '-')} |",
        "| 状态 | capture_failed |",
        f"| 上一有效快照参考 | {previous_text} |",
        "",
        "未使用上一快照替代当天数据；如需报告，请重新采集当天快照或改用授权本地 HTML/复制文本输入。",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def effective_spotcheck_mode(args: argparse.Namespace) -> str:
    if args.spotcheck_mode:
        return args.spotcheck_mode
    if args.accuracy_mode == "high":
        return "high"
    return "balanced"


def should_run_spotcheck(args: argparse.Namespace) -> bool:
    if args.spotcheck or args.spotcheck_mode or args.spotcheck_regions:
        return True
    return args.accuracy_mode in {"balanced", "high"}


def selected_report_modes(report_mode: str) -> list[str]:
    if report_mode == "both":
        return ["daily", "full"]
    return [report_mode]


def row_plan_labels(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> list[str]:
    labels: list[str] = []
    for item in manifest.get("plans_detected", []):
        label = str(item)
        if label and label not in labels:
            labels.append(label)
    for row in rows:
        label = str(row.get("iap_plan_label", ""))
        if label and label not in labels:
            labels.append(label)
    return labels


def first_report_plan(
    args: argparse.Namespace,
    manifest: dict[str, Any],
    rows: list[dict[str, Any]],
    product_config: dict[str, Any],
    pipeline_warnings: list[str],
) -> str:
    if args.report_plan:
        return args.report_plan
    if args.plan:
        return args.plan
    labels = row_plan_labels(manifest, rows)
    default_plan = str(product_config.get("default_report_plan") or "")
    if default_plan:
        for label in labels:
            if label == default_plan:
                return label
        normalized_default = normalize_lookup(default_plan)
        for label in labels:
            if normalize_lookup(label) == normalized_default:
                return label
        if labels:
            pipeline_warnings.append(f"default_report_plan_missing: {default_plan}")
            return labels[0]

    for row in rows:
        label = str(row.get("iap_plan_label", ""))
        if label:
            return label
    return labels[0] if labels else ""


def is_usage_plan(plan_label: str, billing_cycle: str) -> bool:
    if billing_cycle == "usage":
        return True
    return bool(re.search(r"\b(credits?|tokens?|usage|points?|coins?)\b", plan_label, re.I))


def quality_warnings(
    manifest: dict[str, Any],
    rows: list[dict[str, Any]],
    spotchecks: list[dict[str, Any]],
    parse_warnings: list[str],
    extra_warnings: list[str] | None = None,
) -> list[str]:
    warnings: list[str] = []
    warnings.extend(extra_warnings or [])
    if manifest.get("status") == "failed":
        warnings.append("capture_failed")
    if manifest.get("quality_status") in {"partial", "missing"}:
        warnings.append(f"capture_quality_{manifest.get('quality_status')}")
    warnings.extend(parse_warnings)
    detected = [str(item) for item in manifest.get("plans_detected", []) if item]
    parsed = {str(row.get("iap_plan_label", "")) for row in rows if row.get("iap_plan_label")}
    missing_plans = [item for item in detected if item not in parsed]
    if missing_plans:
        warnings.append("plans_without_rows: " + ", ".join(missing_plans))
    if rows and any(row.get("fx_verification_status") == "fx_missing" for row in rows):
        warnings.append("fx_missing")
    mismatch_count = sum(1 for row in rows if row.get("fx_verification_status") == "fx_mismatch")
    if mismatch_count:
        warnings.append(f"fx_mismatch_over_threshold: {mismatch_count}")
    missing_iso = sum(1 for row in rows if not row.get("iso2"))
    if missing_iso:
        warnings.append(f"missing_iso: {missing_iso}")
    low_region_plans = []
    for plan in sorted(parsed):
        plan_rows = [row for row in rows if row.get("iap_plan_label") == plan]
        cycle = str((plan_rows[0] or {}).get("billing_cycle", ""))
        region_count = len({row.get("region") for row in plan_rows})
        if not is_usage_plan(plan, cycle) and region_count < 10:
            low_region_plans.append(f"{plan}={region_count}")
    if low_region_plans:
        warnings.append("low_region_count: " + ", ".join(low_region_plans))
    failed_spots = [row for row in spotchecks if row.get("spotcheck_status") == "failed"]
    conflicts = [row for row in spotchecks if row.get("verification_status") == "conflict"]
    if failed_spots:
        warnings.append(f"apple_spotcheck_failed: {len(failed_spots)}")
    if conflicts:
        warnings.append(f"apple_spotcheck_conflict: {len(conflicts)}")
    return sorted({warning for warning in warnings if warning})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url")
    parser.add_argument("--html-file", type=Path)
    parser.add_argument("--text-file", type=Path)
    parser.add_argument("--text")
    parser.add_argument("--today", action="store_true", help="Capture the configured App Store Price URL as today's monitoring snapshot.")
    parser.add_argument("--app", default="chatgpt", help="Configured product key. Built-ins: chatgpt, claude, gemini, grok.")
    parser.add_argument("--product-key", help="Configured product key. Overrides --app when provided.")
    parser.add_argument("--intent-text", help="Natural-language product request, e.g. GPT套餐监测, Gemini套餐监测.")
    parser.add_argument("--provider")
    parser.add_argument("--product")
    parser.add_argument("--app-store-id")
    parser.add_argument("--source-url")
    parser.add_argument("--snapshot-id")
    parser.add_argument("--plan", help="Parse a single plan. Omit for full product matrix.")
    parser.add_argument("--report-plan", help="Selected plan for the detailed report section.")
    parser.add_argument("--report-mode", choices=["daily", "full", "both"], default="daily", help="Report output mode. daily is the default short report; full keeps the 11-module report; both writes both files.")
    parser.add_argument("--expected-row-count", type=int)
    parser.add_argument("--target", default="CNY")
    parser.add_argument("--force-fx", action="store_true")
    parser.add_argument(
        "--accuracy-mode",
        choices=["light", "balanced", "high"],
        default="balanced",
        help="Accuracy strategy: light=App Store Price+FX, balanced=lowest 3+US+highest Apple spot checks, high=Top10 low+US+Top5 high.",
    )
    parser.add_argument("--spotcheck", action="store_true", help="Run Apple storefront spot checks; defaults to at least balanced scope.")
    parser.add_argument("--spotcheck-mode", choices=["default", "balanced", "high", "top10-low"])
    parser.add_argument("--spotcheck-regions")
    parser.add_argument("--previous", type=Path, help="Previous enriched snapshot for comparison.")
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument("--skip-cleanup", action="store_true", help="Skip retention cleanup after --today monitoring.")
    parser.add_argument("--cleanup-dry-run", action="store_true", help="Preview retention cleanup after --today without deleting artifacts.")
    return parser


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()
    ensure_one_input(args)

    products = load_product_config()
    product_key = resolve_product_key(args, products)
    preset = products[product_key]
    provider = args.provider or preset["provider"]
    product = args.product or preset["product"]
    app_store_id = args.app_store_id or preset["app_store_id"]
    source_url = args.source_url or args.url or preset["source_url"]
    pipeline_warnings: list[str] = []

    summary: dict[str, Any] = {
        "status": "started",
        "product_key": product_key,
        "monitor_date": date.today().isoformat(),
        "provider": provider,
        "product": product,
        "app_store_id": app_store_id,
        "source_url": source_url,
        "default_report_plan": preset.get("default_report_plan", ""),
        "accuracy_mode": args.accuracy_mode,
        "report_mode": args.report_mode,
        "warnings": [],
    }

    raw_root = DATA_DIR / "raw" / "appstoreprice"
    fetch_cmd = [
        sys.executable,
        str(SCRIPT_DIR / "fetch_appstoreprice_snapshot.py"),
        *input_args(args, source_url),
        "--provider",
        provider,
        "--product",
        product,
        "--app-store-id",
        app_store_id,
        "--source-url",
        source_url,
        "--output-root",
        str(raw_root),
    ]
    snapshot_id_arg = args.snapshot_id or (today_snapshot_id(product_key, app_store_id) if args.today else "")
    if snapshot_id_arg:
        fetch_cmd.extend(["--snapshot-id", snapshot_id_arg])
    fetch_result = run_step("capture", fetch_cmd)
    manifest = parse_stdout_json(fetch_result, {})
    snapshot_id = str(manifest.get("snapshot_id") or args.snapshot_id or slugify(product))
    snapshot_dir = raw_root / snapshot_id
    manifest_path = snapshot_dir / "manifest.json"
    summary.update(
        {
            "snapshot_id": snapshot_id,
            "manifest_path": str(manifest_path),
            "raw_snapshot_path": manifest.get("raw_path", ""),
            "source_hash": manifest.get("source_hash", ""),
            "raw_size_bytes": manifest.get("raw_size_bytes", 0),
            "capture_status": manifest.get("status", ""),
            "extraction_mode": manifest.get("extraction_mode", ""),
            "quality_status": manifest.get("quality_status", ""),
            "plans_detected": manifest.get("plans_detected", []),
        }
    )
    if manifest.get("status") == "failed":
        previous_valid = latest_valid_snapshot(raw_root, app_store_id, snapshot_id)
        daily_report_path = OUTPUTS_DIR / f"{snapshot_id}.daily.md"
        full_report_path = OUTPUTS_DIR / f"{snapshot_id}.report.md"
        written_paths = []
        for mode in selected_report_modes(args.report_mode):
            path = daily_report_path if mode == "daily" else full_report_path
            write_capture_failed_report(path, product, source_url, snapshot_id, manifest, previous_valid)
            written_paths.append(path)
        report_path = written_paths[0] if written_paths else daily_report_path
        summary["status"] = "failed"
        summary["report_path"] = str(report_path)
        summary["daily_report_path"] = str(daily_report_path) if daily_report_path in written_paths else ""
        summary["full_report_path"] = str(full_report_path) if full_report_path in written_paths else ""
        summary["previous_valid_snapshot"] = previous_valid
        summary["warnings"] = quality_warnings(manifest, [], [], [], pipeline_warnings)
        output = args.summary_output or OUTPUTS_DIR / f"{snapshot_id}.collect_summary.json"
        write_json(output, summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 2

    normalized_json = DATA_DIR / "normalized" / f"{snapshot_id}.json"
    normalized_csv = DATA_DIR / "normalized" / f"{snapshot_id}.csv"
    parse_cmd = [
        sys.executable,
        str(SCRIPT_DIR / "parse_appstoreprice_snapshot.py"),
        str(snapshot_dir),
        "--json-output",
        str(normalized_json),
        "--csv-output",
        str(normalized_csv),
    ]
    if args.plan:
        parse_cmd.extend(["--plan", args.plan])
    if args.expected_row_count:
        parse_cmd.extend(["--expected-row-count", str(args.expected_row_count)])
    parse_result = run_step("parse", parse_cmd, allow_failure=True)
    parse_summary = parse_stdout_json(parse_result, {})
    if parse_result.returncode != 0:
        summary["status"] = "failed"
        summary["normalized_json"] = str(normalized_json)
        summary["normalized_csv"] = str(normalized_csv)
        summary["warnings"] = quality_warnings(
            manifest,
            [],
            [],
            [f"parse_failed: {(parse_result.stderr or parse_result.stdout).strip()}"],
            pipeline_warnings,
        )
        output = args.summary_output or OUTPUTS_DIR / f"{snapshot_id}.collect_summary.json"
        write_json(output, summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 2

    rows = read_json(normalized_json, [])
    fx_json = DATA_DIR / "fx" / "latest_fx_cny.json"
    fx_cmd = [
        sys.executable,
        str(SCRIPT_DIR / "fetch_fx_rates.py"),
        "--normalized-json",
        str(normalized_json),
        "--target",
        args.target,
        "--output",
        str(fx_json),
    ]
    if args.force_fx:
        fx_cmd.append("--force")
    run_step("fetch_fx", fx_cmd)

    enriched_json = DATA_DIR / "snapshots" / f"{snapshot_id}.enriched.json"
    run_step(
        "enrich",
        [
            sys.executable,
            str(SCRIPT_DIR / "enrich_with_fx.py"),
            str(normalized_json),
            "--fx",
            str(fx_json),
            "--country-map",
            str(SKILL_ROOT / "references" / "country-storefront-map.yml"),
            "--output",
            str(enriched_json),
        ],
    )
    enriched_rows = read_json(enriched_json, [])
    report_plan = first_report_plan(args, manifest, enriched_rows, preset, pipeline_warnings)

    spotcheck_json = None
    spotchecks: list[dict[str, Any]] = []
    spotcheck_mode_effective = ""
    if should_run_spotcheck(args):
        spotcheck_mode_effective = effective_spotcheck_mode(args)
        spotcheck_json = OUTPUTS_DIR / f"{snapshot_id}.apple_spotcheck.json"
        spot_cmd = [
            sys.executable,
            str(SCRIPT_DIR / "fetch_apple_storefront_spotcheck.py"),
            str(enriched_json),
            "--mode",
            spotcheck_mode_effective,
            "--plan",
            report_plan,
            "--output",
            str(spotcheck_json),
        ]
        if args.spotcheck_regions:
            spot_cmd.extend(["--regions", args.spotcheck_regions])
        run_step("apple_spotcheck", spot_cmd)
        spotchecks = read_json(spotcheck_json, [])

    change_log = None
    anomaly_report = None
    if args.previous:
        run_step(
            "compare",
            [
                sys.executable,
                str(SCRIPT_DIR / "compare_snapshots.py"),
                "--current",
                str(enriched_json),
                "--previous",
                str(args.previous),
                "--output-dir",
                str(OUTPUTS_DIR),
            ],
        )
        change_log = OUTPUTS_DIR / "change_log.md"
        anomaly_report = OUTPUTS_DIR / "anomaly_report.md"

    daily_report_path = OUTPUTS_DIR / f"{snapshot_id}.daily.md"
    full_report_path = OUTPUTS_DIR / f"{snapshot_id}.report.md"
    written_report_paths: dict[str, Path] = {}
    for mode in selected_report_modes(args.report_mode):
        output_path = daily_report_path if mode == "daily" else full_report_path
        report_cmd = [
            sys.executable,
            str(SCRIPT_DIR / "generate_intel_report.py"),
            str(enriched_json),
            "--plan",
            report_plan,
            "--mode",
            mode,
            "--output",
            str(output_path),
        ]
        if spotcheck_json:
            report_cmd.extend(["--spotcheck", str(spotcheck_json)])
        if change_log:
            report_cmd.extend(["--change-log", str(change_log)])
        if anomaly_report:
            report_cmd.extend(["--anomaly-report", str(anomaly_report)])
        run_step(f"report_{mode}", report_cmd)
        written_report_paths[mode] = output_path
    report_path = written_report_paths.get("daily") or written_report_paths.get("full") or daily_report_path

    parse_warnings = parse_summary.get("warnings", [])
    warnings = quality_warnings(manifest, enriched_rows, spotchecks, parse_warnings, pipeline_warnings)
    cleanup_status, cleanup_deleted_count, cleanup_summary, cleanup_error = run_cleanup(args, product_key)
    if cleanup_status == "failed":
        warnings.append("cleanup_failed")
        if cleanup_error:
            cleanup_summary = {"error": cleanup_error}
    summary.update(
        {
            "status": "complete" if not warnings else "complete_with_warnings",
            "normalized_json": str(normalized_json),
            "normalized_csv": str(normalized_csv),
            "fx_json": str(fx_json),
            "enriched_json": str(enriched_json),
            "spotcheck_json": str(spotcheck_json) if spotcheck_json else "",
            "spotcheck_mode": spotcheck_mode_effective,
            "change_log": str(change_log) if change_log else "",
            "anomaly_report": str(anomaly_report) if anomaly_report else "",
            "report_path": str(report_path),
            "daily_report_path": str(written_report_paths.get("daily", "")),
            "full_report_path": str(written_report_paths.get("full", "")),
            "report_mode": args.report_mode,
            "report_plan": report_plan,
            "plan_count": len({row.get("iap_plan_label") for row in enriched_rows}),
            "row_count": len(enriched_rows),
            "fx_mismatch_count": sum(1 for row in enriched_rows if row.get("fx_verification_status") == "fx_mismatch"),
            "missing_iso_count": sum(1 for row in enriched_rows if not row.get("iso2")),
            "cleanup_status": cleanup_status,
            "cleanup_deleted_count": cleanup_deleted_count,
            "cleanup_summary": cleanup_summary,
            "warnings": warnings,
        }
    )
    output = args.summary_output or OUTPUTS_DIR / f"{snapshot_id}.collect_summary.json"
    summary["summary_output"] = str(output)
    write_json(output, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

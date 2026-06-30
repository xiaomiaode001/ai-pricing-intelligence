#!/usr/bin/env python3
"""Check the local environment for AI subscription pricing monitoring."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SKILL_ROOT = SCRIPT_DIR.parent
MIN_PYTHON = (3, 10)

REQUIRED_DIRS = [
    "config",
    "references",
    "scripts",
    "data",
    "data/raw/appstoreprice",
    "data/normalized",
    "data/snapshots",
    "data/fx",
    "outputs",
]

WRITABLE_DIRS = [
    "data/raw/appstoreprice",
    "data/normalized",
    "data/snapshots",
    "data/fx",
    "outputs",
]

REQUIRED_FILES = [
    "SKILL.md",
    "config/product-monitoring.yml",
    "config/retention.yml",
    "references/country-storefront-map.yml",
    "references/field-schema.md",
    "references/fx-source-policy.md",
    "references/report-template.md",
    "references/source-policy.md",
    "scripts/collect_appstoreprice_intel.py",
    "scripts/fetch_appstoreprice_snapshot.py",
    "scripts/parse_appstoreprice_snapshot.py",
    "scripts/fetch_fx_rates.py",
    "scripts/enrich_with_fx.py",
    "scripts/fetch_apple_storefront_spotcheck.py",
    "scripts/generate_intel_report.py",
    "scripts/prune_monitoring_artifacts.py",
]

REQUIRED_PRODUCT_FIELDS = [
    "provider",
    "product",
    "app_store_id",
    "source_url",
    "default_report_plan",
]

RECOMMENDED_PRODUCTS = ["chatgpt", "claude", "gemini", "grok"]


def status_row(status: str, message: str, **extra: Any) -> dict[str, Any]:
    row = {"status": status, "message": message}
    row.update(extra)
    return row


def normalize_path(path: Path) -> str:
    return str(path.resolve())


def unquote_yaml_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value in {"null", "Null", "~"}:
        return None
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


def read_product_config(path: Path) -> dict[str, dict[str, Any]]:
    text = path.read_text(encoding="utf-8-sig")
    stripped = text.lstrip()
    if stripped.startswith("{"):
        payload = json.loads(text)
        products = payload.get("products", payload)
        return products if isinstance(products, dict) else {}

    products: dict[str, dict[str, Any]] = {}
    in_products = False
    current_key: str | None = None
    current_list_field: str | None = None
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
            if value:
                products[current_key][field] = unquote_yaml_scalar(value)
                current_list_field = None
            else:
                products[current_key][field] = []
                current_list_field = field
            continue
        if indent >= 6 and current_list_field and line.startswith("- "):
            products[current_key].setdefault(current_list_field, []).append(unquote_yaml_scalar(line[2:]))
    return products


def check_python() -> dict[str, Any]:
    version_ok = sys.version_info >= MIN_PYTHON
    utf8_ok = bool(sys.flags.utf8_mode) or str(sys.getfilesystemencoding()).lower().startswith("utf")
    if not version_ok:
        return status_row(
            "error",
            f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required",
            version=platform.python_version(),
            executable=sys.executable,
            utf8_mode=bool(sys.flags.utf8_mode),
            filesystem_encoding=sys.getfilesystemencoding(),
        )
    if not utf8_ok:
        return status_row(
            "warning",
            "UTF-8 mode is recommended; run with python -X utf8 or set PYTHONUTF8=1",
            version=platform.python_version(),
            executable=sys.executable,
            utf8_mode=bool(sys.flags.utf8_mode),
            filesystem_encoding=sys.getfilesystemencoding(),
        )
    return status_row(
        "ok",
        "Python runtime is usable",
        version=platform.python_version(),
        executable=sys.executable,
        utf8_mode=bool(sys.flags.utf8_mode),
        filesystem_encoding=sys.getfilesystemencoding(),
    )


def check_project_shape(skill_root: Path) -> dict[str, Any]:
    missing_dirs = [item for item in REQUIRED_DIRS if not (skill_root / item).is_dir()]
    missing_files = [item for item in REQUIRED_FILES if not (skill_root / item).is_file()]
    if missing_dirs or missing_files:
        return status_row("error", "Required project files or directories are missing", missing_dirs=missing_dirs, missing_files=missing_files)
    return status_row("ok", "Required project files and directories exist", required_dirs=REQUIRED_DIRS, required_files=REQUIRED_FILES)


def check_runtime_dirs(skill_root: Path) -> dict[str, Any]:
    failures = []
    for item in WRITABLE_DIRS:
        directory = skill_root / item
        try:
            directory.mkdir(parents=True, exist_ok=True)
            probe = directory / ".env-check.tmp"
            probe.write_bytes(b"ok")
            probe.unlink(missing_ok=True)
        except OSError as exc:
            failures.append({"dir": item, "error": str(exc)})
    if failures:
        return status_row("error", "Runtime directories are not writable", failures=failures)
    return status_row("ok", "Runtime directories are writable", writable_dirs=WRITABLE_DIRS)


def check_dependencies() -> dict[str, Any]:
    pyyaml = importlib.util.find_spec("yaml")
    if pyyaml is None:
        return status_row(
            "warning",
            "PyYAML is missing; runtime scripts work, but official quick_validate.py requires it",
            install_command="python -m pip install -r requirements.txt",
            pyyaml="missing",
        )
    return status_row("ok", "Python dependencies are installed", pyyaml="ok")


def check_product_config(skill_root: Path) -> dict[str, Any]:
    path = skill_root / "config" / "product-monitoring.yml"
    try:
        products = read_product_config(path)
    except (OSError, json.JSONDecodeError) as exc:
        return status_row("error", "Product monitoring config cannot be read", error=str(exc))
    missing_products = [key for key in RECOMMENDED_PRODUCTS if key not in products]
    missing_fields: dict[str, list[str]] = {}
    for key, product in products.items():
        missing = [field for field in REQUIRED_PRODUCT_FIELDS if not product.get(field)]
        if missing:
            missing_fields[key] = missing
    if missing_products or missing_fields:
        return status_row(
            "warning",
            "Product config is readable but incomplete for some monitoring routes",
            product_count=len(products),
            products=sorted(products),
            missing_products=missing_products,
            missing_fields=missing_fields,
        )
    return status_row(
        "ok",
        "Product monitoring config is complete",
        product_count=len(products),
        products=sorted(products),
    )


def check_network(skill_root: Path, timeout: int = 10) -> dict[str, Any]:
    urls = [
        "https://api.frankfurter.dev/v2/rates",
        "https://open.er-api.com/v6/latest/USD",
    ]
    products = read_product_config(skill_root / "config" / "product-monitoring.yml")
    urls.extend(str(product.get("source_url")) for product in products.values() if product.get("source_url"))
    results = []
    for url in urls:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "ai-subscription-pricing-intel/1.0"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                results.append({"url": url, "status": "ok", "http_status": getattr(response, "status", None)})
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            results.append({"url": url, "status": "warning", "error": str(exc)})
    failures = [row for row in results if row["status"] != "ok"]
    if failures:
        return status_row("warning", "Some network sources are unreachable from this environment", results=results)
    return status_row("ok", "Network sources are reachable", results=results)


def build_environment_report(skill_root: Path = DEFAULT_SKILL_ROOT, check_network: bool = False, strict: bool = False) -> dict[str, Any]:
    skill_root = skill_root.resolve()
    checks: dict[str, Any] = {
        "python": check_python(),
        "project_shape": check_project_shape(skill_root),
        "runtime_dirs": check_runtime_dirs(skill_root),
        "dependencies": check_dependencies(),
        "product_config": check_product_config(skill_root),
    }
    if check_network:
        checks["network"] = check_network_sources(skill_root)
    statuses = [row.get("status") for row in checks.values()]
    if "error" in statuses or (strict and "warning" in statuses):
        status = "error"
    elif "warning" in statuses:
        status = "warning"
    else:
        status = "ok"
    return {
        "status": status,
        "skill_root": normalize_path(skill_root),
        "strict": strict,
        "network_checked": check_network,
        "checks": checks,
    }


def check_network_sources(skill_root: Path) -> dict[str, Any]:
    try:
        return check_network(skill_root)
    except Exception as exc:  # Keep environment checks diagnostic, not crashy.
        return status_row("warning", "Network check could not complete", error=str(exc))


def format_report(report: dict[str, Any]) -> str:
    lines = [
        f"Environment status: {report['status']}",
        f"Skill root: {report['skill_root']}",
        "",
    ]
    for name, row in report["checks"].items():
        lines.append(f"[{row.get('status', 'unknown')}] {name}: {row.get('message', '')}")
        if row.get("install_command"):
            lines.append(f"  install: {row['install_command']}")
        if row.get("missing_dirs"):
            lines.append(f"  missing_dirs: {', '.join(row['missing_dirs'])}")
        if row.get("missing_files"):
            lines.append(f"  missing_files: {', '.join(row['missing_files'])}")
        if row.get("missing_products"):
            lines.append(f"  missing_products: {', '.join(row['missing_products'])}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-root", type=Path, default=DEFAULT_SKILL_ROOT)
    parser.add_argument("--network", action="store_true", help="Check App Store Price and FX network endpoints.")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
    parser.add_argument("--json", action="store_true", help="Write machine-readable JSON.")
    return parser


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()
    report = build_environment_report(args.skill_root, check_network=args.network, strict=args.strict)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_report(report))
    return 0 if report["status"] in {"ok", "warning"} and not (args.strict and report["status"] == "warning") else 1


if __name__ == "__main__":
    raise SystemExit(main())

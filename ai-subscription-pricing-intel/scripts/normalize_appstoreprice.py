#!/usr/bin/env python3
"""Compatibility wrapper for parse_appstoreprice_snapshot.py.

Prefer scripts/parse_appstoreprice_snapshot.py for new workflows.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


APP_META = {
    "chatgpt": ("OpenAI", "ChatGPT", "6448311069"),
    "claude": ("Anthropic", "Claude", "6473753684"),
    "gemini": ("Google", "Google Gemini", "6477489729"),
    "grok": ("xAI", "Grok", "6670324846"),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Saved App Store Price page text or HTML")
    parser.add_argument("--app", choices=sorted(APP_META), required=True)
    parser.add_argument("--plan")
    parser.add_argument("--source-url", default="")
    parser.add_argument("--observed-at", default="")
    parser.add_argument("--format", choices=["json", "csv"], default="json")
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()
    print("normalize_appstoreprice.py is deprecated; use parse_appstoreprice_snapshot.py", file=sys.stderr)
    provider, product, app_store_id = APP_META[args.app]
    script_dir = Path(__file__).resolve().parent
    fetcher = script_dir / "fetch_appstoreprice_snapshot.py"
    parser = script_dir / "parse_appstoreprice_snapshot.py"
    with tempfile.TemporaryDirectory(prefix="appstoreprice-normalize-") as tmp:
        tmp_path = Path(tmp)
        snapshot_root = tmp_path / "raw"
        normalized_root = tmp_path / "normalized"
        fetch_cmd = [
            sys.executable,
            str(fetcher),
            "--text-file",
            str(args.input),
            "--provider",
            provider,
            "--product",
            product,
            "--app-store-id",
            app_store_id,
            "--source-url",
            args.source_url,
            "--output-root",
            str(snapshot_root),
        ]
        captured = subprocess.run(fetch_cmd, check=True, capture_output=True, text=True, encoding="utf-8")
        manifest = json.loads(captured.stdout)
        parse_cmd = [
            sys.executable,
            str(parser),
            str(snapshot_root / manifest["snapshot_id"]),
            "--output-dir",
            str(normalized_root),
        ]
        if args.plan:
            parse_cmd.extend(["--plan", args.plan])
        subprocess.run(parse_cmd, check=True, capture_output=True, text=True, encoding="utf-8")
        source = normalized_root / f"{manifest['snapshot_id']}.{args.format}"
        data = source.read_text(encoding="utf-8-sig" if args.format == "csv" else "utf-8")
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(data, encoding="utf-8-sig" if args.format == "csv" else "utf-8")
        else:
            print(data, end="" if data.endswith("\n") else "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

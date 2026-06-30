#!/usr/bin/env python3
"""Compatibility wrapper for compare_snapshots.py."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("outputs/change_log.md"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    script = Path(__file__).resolve().parent / "compare_snapshots.py"
    anomaly_report = args.output.parent / "anomaly_report.md"
    cmd = [
        sys.executable,
        str(script),
        "--current",
        str(args.current),
        "--previous",
        str(args.previous),
        "--change-log",
        str(args.output),
        "--anomaly-report",
        str(anomaly_report),
    ]
    return subprocess.run(cmd).returncode


if __name__ == "__main__":
    raise SystemExit(main())

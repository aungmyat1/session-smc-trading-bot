#!/usr/bin/env python3
"""Validate required runtime configuration for the hardened execution path."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def validate_runtime(root: Path) -> list[str]:
    issues: list[str] = []
    env = {
        "TRADING_MODE": os.getenv("TRADING_MODE", "shadow").strip().lower(),
        "DEMO_ONLY": os.getenv("DEMO_ONLY", "true").strip().lower(),
        "LIVE_TRADING": os.getenv("LIVE_TRADING", "false").strip().lower(),
    }
    if env["TRADING_MODE"] == "live":
        issues.append("TRADING_MODE=live is blocked by policy")
    if env["LIVE_TRADING"] in {"true", "1", "yes"}:
        issues.append("LIVE_TRADING must remain false")
    if env["TRADING_MODE"] == "demo" and env["DEMO_ONLY"] not in {"false", "0", "no"}:
        issues.append("demo mode requires DEMO_ONLY=false")

    required_paths = [
        root / "config" / "strategy_catalog.yaml",
        root / "deploy" / "gcp-vm1" / "systemd" / "smc-demo-runner.service",
        root / "scripts" / "reconcile_positions.py",
    ]
    for path in required_paths:
        if not path.exists():
            issues.append(f"missing required path: {path.relative_to(root)}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    issues = validate_runtime(root)
    if issues:
        for issue in issues:
            print(f"FAIL: {issue}")
        return 1
    print("PASS: runtime configuration is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

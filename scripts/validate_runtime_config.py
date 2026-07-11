#!/usr/bin/env python3
"""Validate required runtime configuration for the hardened execution path."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.strategy_registry import can_deploy_strategy, get_strategy_manifest
from shared.configuration import load_yaml_mapping


def _portfolio_governance_issues(root: Path) -> list[str]:
    issues: list[str] = []
    portfolio_path = root / "config" / "strategy_portfolio.yaml"
    catalog_path = root / "config" / "strategy_catalog.yaml"
    if not portfolio_path.exists() or not catalog_path.exists():
        return issues

    portfolio = load_yaml_mapping(portfolio_path, default={})
    strategies = portfolio.get("strategies", {})
    if not isinstance(strategies, dict):
        issues.append("strategy_portfolio.yaml strategies must be a mapping")
        return issues

    for name, entry in strategies.items():
        if not isinstance(entry, dict):
            issues.append(f"portfolio strategy {name} must be a mapping")
            continue
        enabled = bool(entry.get("enabled", True))
        mode = str(entry.get("execution_mode", "shadow")).strip().lower()
        manifest = get_strategy_manifest(str(name), catalog_path)
        if manifest is None:
            issues.append(f"portfolio strategy {name} is missing from strategy_catalog.yaml")
            continue
        if enabled and mode in {"demo", "demo_validation", "live"}:
            target_stage = "demo" if mode == "demo_validation" else mode
            if not can_deploy_strategy(str(name), target_stage=target_stage, path=catalog_path):
                issues.append(
                    f"portfolio strategy {name} is enabled for {mode} but is not approved "
                    "for deployment in strategy_catalog.yaml"
                )
    return issues


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
    issues.extend(_portfolio_governance_issues(root))
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

#!/usr/bin/env python3
"""Initialise the data/svos/ JSONL registry store.

Calls SVOSPlatform.bootstrap() against the live strategy catalog. This is the
one-shot command to run after P0-1 (migrations) so the governance layer has
real data to work with.

Usage:
    python3 scripts/bootstrap_svos.py
    python3 scripts/bootstrap_svos.py --root /path/to/project
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from svos.orchestration.service import SVOSPlatform


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap SVOS JSONL registry")
    parser.add_argument("--root", default=str(ROOT), help="Project root (default: repo root)")
    args = parser.parse_args()

    root = Path(args.root)
    catalog = root / "config" / "strategy_catalog.yaml"
    if not catalog.exists():
        print(f"ERROR: catalog not found at {catalog}", file=sys.stderr)
        sys.exit(1)

    platform = SVOSPlatform(root=root, catalog_path=catalog)
    result = platform.bootstrap()

    print(f"Bootstrapped {result['strategy_count']} strategies:")
    for s in result["strategies"]:
        name = s.get("strategy", s.get("strategy", "?"))
        stage = s.get("current_stage", s.get("stage", "?"))
        print(f"  {name:<25} stage={stage}")

    # Verify state files
    registry_root = root / "data" / "svos" / "registry"
    print()
    print("Verifying data/svos/registry/:")
    all_ok = True
    for s in result["strategies"]:
        name = s.get("strategy", "?")
        state_path = registry_root / name / "state.json"
        versions_path = registry_root / name / "versions.jsonl"
        state_ok = state_path.exists()
        versions_ok = versions_path.exists()
        status = "OK" if (state_ok and versions_ok) else "MISSING"
        if not (state_ok and versions_ok):
            all_ok = False
        print(f"  {name:<25} state.json={'yes' if state_ok else 'NO'} versions.jsonl={'yes' if versions_ok else 'NO'}  [{status}]")

    print()
    if all_ok:
        print("PASS: all JSONL registry files written.")
    else:
        print("FAIL: some registry files missing — check errors above.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

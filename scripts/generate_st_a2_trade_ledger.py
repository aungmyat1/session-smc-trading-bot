#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research.st_a2_freeze import generate_baseline, generate_ledgers, write_registration_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate immutable ST-A2 v1 trade ledgers from the frozen dataset")
    parser.add_argument("--overwrite", action="store_true", help="Regenerate existing frozen ledger files")
    parser.add_argument(
        "--ledger-only",
        action="store_true",
        help="Only generate registration and ledger manifests, without validation/release reports",
    )
    args = parser.parse_args()

    if args.ledger_only:
        registration = write_registration_manifest()
        ledger = generate_ledgers(overwrite=args.overwrite)
        result = {
            "registration_manifest": "artifacts/ST-A2_registration_manifest.json",
            "ledger_manifest": "artifacts/ST-A2_trade_ledger_manifest.json",
            "strategy_hash": registration["strategy_hash"],
            "trade_count": ledger["trade_count"],
            "ledger_hash": ledger["ledger_hash"],
        }
    else:
        result = generate_baseline(overwrite=args.overwrite)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

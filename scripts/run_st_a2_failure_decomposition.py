#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research.failure_decomposition import run_failure_decomposition


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ST-A2 failure decomposition over frozen trade ledgers")
    parser.add_argument("--ledger-dir", default="research/trade_ledgers")
    parser.add_argument("--artifact-dir", default="artifacts")
    args = parser.parse_args()

    result = run_failure_decomposition(ROOT / args.ledger_dir, ROOT / args.artifact_dir)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

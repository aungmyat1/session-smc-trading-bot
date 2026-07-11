#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research.research_validation import write_validation_matrix


def main() -> int:
    parser = argparse.ArgumentParser(description="Create strategy validation matrix scaffold")
    parser.add_argument("--out", default="artifacts/strategy_validation_matrix.csv")
    args = parser.parse_args()

    rows = write_validation_matrix(ROOT / args.out)
    print(json.dumps({"rows": len(rows), "out": args.out}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research.experiments.st_a2_candidate_robustness import DEFAULT_CONFIG, run_st_a2_v2_candidate_robustness


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ST-A2_v2_candidate robustness validation")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG.relative_to(ROOT)))
    args = parser.parse_args()

    result = run_st_a2_v2_candidate_robustness(ROOT / args.config)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

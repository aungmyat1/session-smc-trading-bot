#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research.experiments.st_a2 import DEFAULT_CONFIG, DEFAULT_OUTPUT_DIR, run_st_a2_experiments


def main() -> int:
    parser = argparse.ArgumentParser(description="Run isolated ST-A2 hypothesis-driven experiments")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG.relative_to(ROOT)))
    parser.add_argument("--outdir", default=str(DEFAULT_OUTPUT_DIR.relative_to(ROOT)))
    args = parser.parse_args()

    result = run_st_a2_experiments(ROOT / args.config, ROOT / args.outdir)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

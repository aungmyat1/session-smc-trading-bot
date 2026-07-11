#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research.professional_dataset_v2.pipeline import ROOT, load_to_sqlite


def main() -> int:
    parser = argparse.ArgumentParser(description="Load dataset v2 metadata into the research DB contract")
    parser.add_argument("--sqlite-db", default="data/research_dataset_v2.sqlite")
    parser.add_argument("--dataset-dir", default="datasets/professional_3y_4symbol_v2")
    args = parser.parse_args()
    print(json.dumps(load_to_sqlite(ROOT / args.sqlite_db, ROOT / args.dataset_dir), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

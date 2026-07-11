#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research.professional_dataset_v2.pipeline import ROOT, export_package


def main() -> int:
    parser = argparse.ArgumentParser(description="Export professional dataset v2 release package")
    parser.add_argument("--dataset-dir", default="datasets/professional_3y_4symbol_v2")
    parser.add_argument("--output", default="artifacts/professional_dataset_v2.tar.gz")
    args = parser.parse_args()
    out = export_package(ROOT / args.dataset_dir, ROOT / args.output)
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

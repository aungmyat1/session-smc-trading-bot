#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research.professional_dataset_v2.pipeline import ROOT, update_release_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Upgrade the dataset manifest with release metadata")
    parser.add_argument("--dataset-dir", default="datasets/professional_3y_4symbol_v2")
    args = parser.parse_args()
    manifest = update_release_manifest(ROOT / args.dataset_dir)
    print(json.dumps({"release_status": manifest.get("release_status"), "completion_pct": manifest.get("completion_pct")}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

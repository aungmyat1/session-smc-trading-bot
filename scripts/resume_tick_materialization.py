#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research.professional_dataset_v2.pipeline import ROOT, load_config, resume_tick_materialization


def main() -> int:
    parser = argparse.ArgumentParser(description="Resume missing v2 tick materialization from local raw sources")
    parser.add_argument("--config", default="config/tick_dataset.yaml")
    parser.add_argument("--raw-root", default="data/raw")
    parser.add_argument("--output-root", default="data/tick")
    parser.add_argument("--symbol", action="append")
    parser.add_argument("--from-month", default=None, help="Only process raw files at or after YYYY-MM")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--output", default="artifacts/tick_materialization_resume_report.json")
    args = parser.parse_args()
    report = resume_tick_materialization(
        load_config(ROOT / args.config),
        ROOT / args.raw_root,
        ROOT / args.output_root,
        args.symbol,
        args.from_month,
        args.workers,
    )
    out = ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({sym: {"processed_files": info["processed_files"], "skipped_files": info["skipped_files"]} for sym, info in report["symbols"].items()}, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

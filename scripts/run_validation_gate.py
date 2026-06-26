#!/usr/bin/env python3
"""Run the validation gate engine from JSON inputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from research.validation.engine import (
    ValidationRunner,
    load_validation_config,
)


def _load_json(path: str | None) -> dict:
    if not path:
        return {}
    file_path = Path(path)
    if not file_path.exists():
        return {}
    return json.loads(file_path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run validation gates for a strategy")
    parser.add_argument("--strategy", required=True, help="Strategy name")
    parser.add_argument("--mode", choices=["replay", "backtest", "full"], default="full")
    parser.add_argument("--replay-json", help="Replay validation payload JSON")
    parser.add_argument("--backtest-json", help="Backtest validation payload JSON")
    parser.add_argument("--latest-json", help="Latest metrics JSON")
    parser.add_argument("--previous-json", help="Previous metrics JSON")
    parser.add_argument("--stage", default="backtest", help="Current lifecycle stage")
    parser.add_argument("--outdir", default="reports/validation", help="Output directory")
    parser.add_argument("--config", default="config/validation.yaml", help="Validation config")
    parser.add_argument("--registry", help="Strategy registry/catalog path")
    args = parser.parse_args()

    config = load_validation_config(_ROOT / args.config)
    registry_path = None
    if args.registry:
        registry_path = Path(args.registry)
        if not registry_path.is_absolute():
            registry_path = _ROOT / registry_path
    runner = ValidationRunner(
        args.strategy,
        config=config,
        registry_path=registry_path,
        output_dir=_ROOT / args.outdir,
    )
    replay = _load_json(args.replay_json) if args.mode in {"replay", "full"} else None
    backtest = _load_json(args.backtest_json) if args.mode in {"backtest", "full"} else None
    latest = _load_json(args.latest_json) if args.mode in {"backtest", "full"} else None
    previous = _load_json(args.previous_json) or None

    bundle = runner.run(
        replay,
        backtest,
        latest,
        previous_metrics=previous,
        current_stage=args.stage,
    )
    print(bundle.to_json())
    if bundle.overall_status == "PASS":
        return 0
    if bundle.overall_status == "WARNING":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

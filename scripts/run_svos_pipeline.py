#!/usr/bin/env python3
"""Run the Strategy Validation Operating System pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from research.svos.engine import SVOSRunner


def _load_json(path: str | None) -> dict:
    if not path:
        return {}
    file_path = Path(path)
    if not file_path.exists():
        return {}
    return json.loads(file_path.read_text(encoding="utf-8"))


def _load_text(path: str | None, inline: str | None) -> str:
    if inline:
        return inline
    if not path:
        return ""
    file_path = Path(path)
    if not file_path.exists():
        return ""
    return file_path.read_text(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the SVOS pipeline")
    parser.add_argument("--strategy", required=True, help="Strategy name")
    parser.add_argument("--strategy-text", help="Inline strategy description")
    parser.add_argument("--strategy-file", help="Path to strategy description text")
    parser.add_argument("--replay-json", help="Replay validation JSON")
    parser.add_argument("--backtest-json", help="Backtest validation JSON")
    parser.add_argument("--robustness-json", help="Robustness validation JSON")
    parser.add_argument("--demo-json", help="Demo validation JSON")
    parser.add_argument("--registry", help="Strategy catalog path")
    parser.add_argument("--outdir", default="reports/svos", help="Output directory")
    args = parser.parse_args()

    strategy_text = _load_text(args.strategy_file, args.strategy_text)
    runner = SVOSRunner(
        args.strategy,
        registry_path=args.registry,
        output_dir=_ROOT / args.outdir,
    )
    result = runner.run_pipeline(
        strategy_text,
        replay=_load_json(args.replay_json) or None,
        backtest=_load_json(args.backtest_json) or None,
        robustness=_load_json(args.robustness_json) or None,
        demo=_load_json(args.demo_json) or None,
    )
    print(result.to_json())
    return 0 if result.overall_status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())


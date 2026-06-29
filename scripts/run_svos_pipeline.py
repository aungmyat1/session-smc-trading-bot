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


def _supports_color() -> bool:
    return bool(getattr(sys.stderr, "isatty", lambda: False)())


def _status_tag(status: str) -> str:
    if not _supports_color():
        return status
    colors = {
        "PASS": "\033[32mPASS\033[0m",
        "FIX": "\033[33mFIX\033[0m",
        "FAIL": "\033[31mFAIL\033[0m",
    }
    return colors.get(status, status)


def _overall_status(stages) -> str:
    overall = "PASS"
    for stage in stages:
        if stage.status == "FAIL":
            return "FAIL"
        if stage.status == "FIX" and overall != "FAIL":
            overall = "FIX"
    return overall


def _stage_label(stage_name: str) -> str:
    labels = {
        "virtual_demo": "Virtual Demo",
        "production_approval": "Production Approval",
    }
    return labels.get(stage_name, stage_name.replace("_", " ").title())


def _print_stage_update(stage, stages, promoted_stage) -> None:
    next_action = "n/a"
    if stage.status == "PASS" and stage.next_stage:
        next_action = f"proceed to {stage.next_stage}"
    elif stage.status == "PASS" and stage.stage == "production_approval" and stage.can_promote:
        next_action = "live promotion is permitted if explicitly enabled"
    elif stage.fix_instructions:
        next_action = stage.fix_instructions[0]
    elif stage.next_stage:
        next_action = f"rerun {stage.stage} and continue to {stage.next_stage}"

    print(
        f"[SVOS] {_stage_label(stage.stage)} | phase={stage.phase} | status={_status_tag(stage.status)} | "
        f"overall={_overall_status(stages)} | promoted={promoted_stage or 'n/a'}",
        file=sys.stderr,
        flush=True,
    )
    print(f"[SVOS] next action: {next_action}", file=sys.stderr, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the SVOS pipeline")
    parser.add_argument("--strategy", required=True, help="Strategy name")
    parser.add_argument("--strategy-text", help="Inline strategy description")
    parser.add_argument("--strategy-file", help="Path to strategy description text")
    parser.add_argument("--replay-json", help="Replay validation JSON")
    parser.add_argument("--backtest-json", help="Backtest validation JSON")
    parser.add_argument("--robustness-json", help="Robustness validation JSON")
    parser.add_argument("--virtual-demo-json", help="Virtual demo validation JSON")
    parser.add_argument("--demo-json", help="Legacy alias for --virtual-demo-json")
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
        virtual_demo=_load_json(args.virtual_demo_json) or _load_json(args.demo_json) or None,
        stage_observer=_print_stage_update,
    )
    print(result.to_json())
    return 0 if result.overall_status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

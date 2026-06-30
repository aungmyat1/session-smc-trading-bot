#!/usr/bin/env python3
"""Run the replay-to-execution-validation bridge from a JSON payload."""

from __future__ import annotations

import asyncio
import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from execution_validation.replay_bridge import (
    run_replay_validation_from_candles,
)  # noqa: E402


def _load_json(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run replay validation from candle JSON"
    )
    parser.add_argument(
        "--payload", required=True, help="JSON with candles_m15 and candles_h4"
    )
    parser.add_argument("--strategy", default="ST-A2")
    parser.add_argument("--period", default="2023-2026")
    parser.add_argument("--symbol", default="EURUSD")
    parser.add_argument("--report-dir", default="execution_validation/reports")
    args = parser.parse_args()

    payload = _load_json(args.payload)
    report = asyncio.run(
        run_replay_validation_from_candles(
            strategy=args.strategy,
            period=args.period,
            symbol=args.symbol,
            candles_m15=payload.get("candles_m15", []),
            candles_h4=payload.get("candles_h4", []),
            report_dir=args.report_dir,
            backtest_pf=float(payload.get("backtest_pf", 1.0)),
            virtual_pf=float(payload.get("virtual_pf", 1.0)),
        )
    )
    print(report.to_json())
    return 0 if report.status == "READY FOR DEMO" else 1


if __name__ == "__main__":
    raise SystemExit(main())

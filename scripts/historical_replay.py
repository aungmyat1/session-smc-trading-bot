#!/usr/bin/env python3
"""Historical replay audit runner.

This is the deterministic execution check:
    - feed historical candles sequentially
    - inspect the debug timeline per day
    - compare the sequential replay signals to the batch backtest

It does not answer profitability. Use the backtest scripts for that.
"""

from __future__ import annotations

import argparse
import json
from datetime import date as date_cls, datetime, timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.replay_parquet import load_h4, load_m15  # noqa: E402
from simulator.historical_replay import (  # noqa: E402
    render_report,
    report_to_dict,
    run_historical_replay,
)


def _parse_date(value: str | None) -> date_cls | None:
    if value is None:
        return None
    if "T" in value:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    return datetime.strptime(value, "%Y-%m-%d").date()


def main() -> None:
    parser = argparse.ArgumentParser(description="Historical replay execution audit")
    parser.add_argument("--symbol", default="EURUSD", help="Symbol to replay")
    parser.add_argument("--start", default=None, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default=None, help="End date YYYY-MM-DD")
    parser.add_argument(
        "--all-days",
        action="store_true",
        help="Include no-trade days in the report (default: only signal days)",
    )
    parser.add_argument(
        "--warmup-days",
        type=int,
        default=30,
        help="Lookback window added before the replay start to warm ATR/HTF state",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("reports") / "HISTORICAL_REPLAY_AUDIT.md",
        help="Markdown report path",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=Path("reports") / "HISTORICAL_REPLAY_AUDIT.json",
        help="JSON report path",
    )
    args = parser.parse_args()

    start_date = _parse_date(args.start)
    _end_date = _parse_date(args.end)
    warmup_start = (
        (start_date - timedelta(days=args.warmup_days)).isoformat()
        if start_date
        else None
    )

    m15 = load_m15(args.symbol, start=warmup_start, end=args.end)
    h4 = load_h4(args.symbol, start=warmup_start, end=args.end)

    report = run_historical_replay(
        args.symbol,
        m15,
        h4,
        start=args.start,
        end=args.end,
        signal_days_only=not args.all_days,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_report(report), encoding="utf-8")
    args.json_out.write_text(
        json.dumps(report_to_dict(report), indent=2, default=str),
        encoding="utf-8",
    )

    print(render_report(report))
    print(f"\nSaved markdown report: {args.out}")
    print(f"Saved JSON report: {args.json_out}")


if __name__ == "__main__":
    main()

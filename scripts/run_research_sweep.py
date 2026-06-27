#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.analytics.sweep import SweepCandidate, run_parameter_sweep


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a small research parameter sweep")
    parser.add_argument("--symbol", default="EURUSD")
    parser.add_argument("--raw-root", default="data/historical")
    parser.add_argument("--output", default="research_sweep.csv")
    args = parser.parse_args()

    candidates = [
        SweepCandidate(
            name="smc_tight",
            signal={"min_confluence": 2, "max_signals_per_day": 2, "allowed_sessions": ("london", "new_york")},
            breakout={"enabled": False},
            ny={"enabled": True, "rr_multiple": 2.0},
            vwap={"max_signals_per_day": 1},
        ),
        SweepCandidate(
            name="smc_strict",
            signal={"min_confluence": 3, "max_signals_per_day": 2, "allowed_sessions": ("london", "new_york")},
            breakout={"enabled": False},
            ny={"enabled": True, "rr_multiple": 2.0},
            vwap={"max_signals_per_day": 1},
        ),
        SweepCandidate(
            name="breakout_focused",
            signal={"min_confluence": 2, "max_signals_per_day": 1, "allowed_sessions": ("london", "new_york")},
            breakout={"enabled": True, "rr_multiple": 2.0, "max_signals_per_day": 1},
            ny={"enabled": False},
            vwap={"tp_rr": 1.8, "max_signals_per_day": 1},
        ),
        SweepCandidate(
            name="vwap_focus",
            signal={"min_confluence": 1, "max_signals_per_day": 1, "allowed_sessions": ("london", "new_york")},
            breakout={"enabled": False},
            ny={"enabled": False},
            vwap={"min_session_bars": 8, "tp_rr": 1.8, "max_signals_per_day": 1},
        ),
        SweepCandidate(
            name="ny_focus",
            signal={"min_confluence": 2, "max_signals_per_day": 1, "allowed_sessions": ("london", "new_york")},
            breakout={"enabled": False},
            ny={"enabled": True, "rr_multiple": 2.0, "max_signals_per_day": 1},
            vwap={"enabled": False},
        ),
    ]

    report = run_parameter_sweep(args.raw_root, args.symbol, candidates)
    report.to_csv(args.output, index=False)
    print(report)


if __name__ == "__main__":
    main()

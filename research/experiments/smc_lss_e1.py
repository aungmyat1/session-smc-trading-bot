"""
SMC-LSS_v0 — Experiment E1: Gap Fill Reaction.

A confluence-narrowed subset of smc_lss_e3.py's setup universe: a setup
qualifies for E1 only if its FVG-pullback price falls inside the daily
opening-gap zone AND the setup's direction is the direction a genuine gap
fill would take:

    daily_gap > 0 (gap up: daily_open > previous_day_close)
        -> a fill move is DOWN into the gap -> require direction == 'short'
    daily_gap < 0 (gap down: daily_open < previous_day_close)
        -> a fill move is UP into the gap -> require direction == 'long'
    daily_gap == 0 -> no gap to fill -> setup excluded

Gap zone = [min(daily_open, previous_day_close), max(daily_open, previous_day_close)],
reconstructed from SessionContext.daily_open and daily_gap
(previous_day_close = daily_open - daily_gap).

Entry/SL/TP construction is identical to E3 (see smc_lss_common.build_setup_trade).

Output: list[strategies.smc_lss.exits.SMCTrade].
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from research.experiments.smc_lss_common import (
    DEFAULT_MAX_BARS, DEFAULT_RR, DEFAULT_SL_BUFFER_ATR,
    SMCSetup, build_setup_trade, find_setups,
)
from strategies.smc_lss.exits import SMCTrade

BRANCH = "E1"


def qualifies_for_gap_fill(setup: SMCSetup) -> bool:
    ctx = setup.context
    gap = ctx.daily_gap
    if gap == 0:
        return False

    previous_day_close = ctx.daily_open - gap
    gap_low = min(ctx.daily_open, previous_day_close)
    gap_high = max(ctx.daily_open, previous_day_close)
    pullback_price = setup.shift.pullback_price

    if not (gap_low <= pullback_price <= gap_high):
        return False

    if gap > 0:
        return setup.direction == "short"
    return setup.direction == "long"


def run_e1(
    m5_candles: list[dict],
    d1_candles: list[dict],
    h1_candles: list[dict],
    *,
    symbol: str,
    cfg: "dict | None" = None,
    spread_price_units: float = 0.0,
    rr: float = DEFAULT_RR,
    sl_buffer_atr: float = DEFAULT_SL_BUFFER_ATR,
    max_bars: int = DEFAULT_MAX_BARS,
) -> list[SMCTrade]:
    setups = find_setups(m5_candles, d1_candles, h1_candles, symbol=symbol, cfg=cfg)
    trades: list[SMCTrade] = []
    for setup in setups:
        if not qualifies_for_gap_fill(setup):
            continue
        trade = build_setup_trade(
            setup, m5_candles, BRANCH,
            spread_price_units=spread_price_units, rr=rr,
            sl_buffer_atr=sl_buffer_atr, max_bars=max_bars,
        )
        if trade is not None:
            trades.append(trade)
    return trades


if __name__ == "__main__":
    print("smc_lss_e1.run_e1() is a library entry point.")
    print("Use research/experiments/smc_lss_backtest.py to run against real data.")

"""
SMC-LSS_v0 — Experiment E2: POI Reaction.

A confluence-narrowed subset of smc_lss_e3.py's setup universe: a setup
qualifies for E2 only if:

    1. SessionContext.H1_POI is available (a qualifying H1 displacement
       candle was found ahead of the current day — see strategies/smc_lss/
       context.py), and
    2. the setup's FVG-pullback price is within `poi_tolerance_atr` (fixed
       at 1.0) x sweep.atr of that H1_POI level, and
    3. the setup direction agrees with the daily HTF bias
       (SessionContext.daily_bias) — 'bullish' -> 'long', 'bearish' -> 'short'.

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

BRANCH = "E2"
DEFAULT_POI_TOLERANCE_ATR = 1.0

_BIAS_TO_DIRECTION = {"bullish": "long", "bearish": "short"}


def qualifies_for_poi_reaction(setup: SMCSetup, *, poi_tolerance_atr: float = DEFAULT_POI_TOLERANCE_ATR) -> bool:
    ctx = setup.context
    if ctx.H1_POI is None:
        return False
    if _BIAS_TO_DIRECTION.get(ctx.daily_bias) != setup.direction:
        return False

    tolerance = poi_tolerance_atr * setup.sweep.atr
    return abs(setup.shift.pullback_price - ctx.H1_POI) <= tolerance


def run_e2(
    m5_candles: list[dict],
    d1_candles: list[dict],
    h1_candles: list[dict],
    *,
    symbol: str,
    cfg: "dict | None" = None,
    spread_price_units: float = 0.0,
    rr: float = DEFAULT_RR,
    sl_buffer_atr: float = DEFAULT_SL_BUFFER_ATR,
    poi_tolerance_atr: float = DEFAULT_POI_TOLERANCE_ATR,
    max_bars: int = DEFAULT_MAX_BARS,
) -> list[SMCTrade]:
    setups = find_setups(m5_candles, d1_candles, h1_candles, symbol=symbol, cfg=cfg)
    trades: list[SMCTrade] = []
    for setup in setups:
        if not qualifies_for_poi_reaction(setup, poi_tolerance_atr=poi_tolerance_atr):
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
    print("smc_lss_e2.run_e2() is a library entry point.")
    print("Use research/experiments/smc_lss_backtest.py to run against real data.")

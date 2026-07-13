"""
SMC-LSS_v0 — Experiment E3: Liquidity Sweep (direct entry, unfiltered).

The baseline branch: every confirmed sweep -> CHoCH (with inducement) ->
displacement -> supply/demand-shift setup produced by
smc_lss_common.find_setups() is tradeable, with no additional HTF
confluence filter. E1 (gap fill) and E2 (POI reaction) are confluence-
narrowed subsets of this same setup universe — see their module
docstrings. This is why E1 OR E2 OR E3 (smc_lss_combined.py) evaluates to
the same setup universe as E3 alone; that is reported as an observation in
docs/audit/SMC_LSS_V0_BACKTEST_REPORT.md, not hidden.

Entry/SL/TP construction: strategies.smc_lss.exits via
smc_lss_common.build_setup_trade() (entry at FVG-pullback close, SL beyond
the sweep wick + fixed ATR buffer, TP at a fixed 2.0R — no parameter
sweep, per CLAUDE.md §0.2).

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
    build_setup_trade, find_setups,
)
from strategies.smc_lss.exits import SMCTrade

BRANCH = "E3"


def run_e3(
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
        trade = build_setup_trade(
            setup, m5_candles, BRANCH,
            spread_price_units=spread_price_units, rr=rr,
            sl_buffer_atr=sl_buffer_atr, max_bars=max_bars,
        )
        if trade is not None:
            trades.append(trade)
    return trades


if __name__ == "__main__":
    print("smc_lss_e3.run_e3() is a library entry point.")
    print("Use research/experiments/smc_lss_backtest.py to run against real data.")

"""
SMC-LSS_v0 — Combined Strategy: E1 OR E2 OR E3.

Logic: a setup is tradeable if it qualifies for E1 (gap fill reaction),
E2 (POI reaction), OR E3 (unfiltered liquidity sweep). No parameter
optimization is performed here — every threshold is inherited unchanged
from smc_lss_e1.py / smc_lss_e2.py / smc_lss_e3.py.

NOTE (reported, not hidden — see docs/audit/SMC_LSS_V0_BACKTEST_REPORT.md):
E3 has no additional confluence filter (see smc_lss_e3.py docstring), so
E1 and E2's qualifying setups are always a subset of E3's. This means
`E1 OR E2 OR E3` is mathematically equivalent to E3 alone for this trial's
setup universe — the OR is still evaluated explicitly below (not
short-circuited or special-cased) so this observation is falsifiable by
re-running with different confluence parameters, not assumed.

Output: list[strategies.smc_lss.exits.SMCTrade], branch='combined'.
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
from research.experiments.smc_lss_e1 import qualifies_for_gap_fill
from research.experiments.smc_lss_e2 import DEFAULT_POI_TOLERANCE_ATR, qualifies_for_poi_reaction
from strategies.smc_lss.exits import SMCTrade

BRANCH = "combined"


def run_combined(
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
        e1_qualifies = qualifies_for_gap_fill(setup)
        e2_qualifies = qualifies_for_poi_reaction(setup, poi_tolerance_atr=poi_tolerance_atr)
        e3_qualifies = True  # E3 is unfiltered — see module docstring
        if not (e1_qualifies or e2_qualifies or e3_qualifies):
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
    print("smc_lss_combined.run_combined() is a library entry point.")
    print("Use research/experiments/smc_lss_backtest.py to run against real data.")

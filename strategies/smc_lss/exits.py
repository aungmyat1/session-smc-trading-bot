"""
SMC-LSS_v0 — Exit / Trade Simulation Engine.

simulate_trade(entry, sl, tp, direction, future_bars, ...) -> TradeSimResult

Walk-forward, no-lookahead trade simulator. `future_bars` must contain
only candles strictly AFTER the entry bar, in chronological order. SL is
checked before TP within the same bar (matches the convention already
established in scripts/backtest_session_liquidity.py and
strategies/st_b1_backtest.py). Tracks running MAE (max adverse excursion)
and MFE (max favorable excursion), both expressed in R, through the life
of the trade — including the exit bar.
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_MAX_BARS = 96  # 24h at M15-equivalent granularity; callers on
                        # other timeframes should pass an explicit max_bars.


@dataclass
class TradeSimResult:
    outcome: str            # 'win' | 'loss' | 'timeout'
    exit_price: float
    exit_time: object
    exit_index: int          # index into future_bars, -1 if no bars consumed
    bars_held: int
    r_multiple: float
    mae: float                # max adverse excursion, in R (>= 0)
    mfe: float                # max favorable excursion, in R (>= 0)


def simulate_trade(
    entry: float,
    sl: float,
    tp: float,
    direction: str,
    future_bars: list[dict],
    *,
    max_bars: int = DEFAULT_MAX_BARS,
) -> TradeSimResult:
    risk = abs(entry - sl)
    if risk == 0:
        return TradeSimResult("timeout", entry, None, -1, 0, 0.0, 0.0, 0.0)

    bars = future_bars[:max_bars]
    mae = 0.0
    mfe = 0.0

    for i, bar in enumerate(bars):
        high = float(bar["high"])
        low = float(bar["low"])

        if direction == "long":
            adverse = (entry - low) / risk
            favorable = (high - entry) / risk
        else:
            adverse = (high - entry) / risk
            favorable = (entry - low) / risk
        mae = max(mae, adverse)
        mfe = max(mfe, favorable)

        if direction == "long":
            if low <= sl:
                return TradeSimResult("loss", sl, bar.get("timestamp"), i, i + 1, -1.0, mae, mfe)
            if high >= tp:
                r = (tp - entry) / risk
                return TradeSimResult("win", tp, bar.get("timestamp"), i, i + 1, r, mae, mfe)
        else:
            if high >= sl:
                return TradeSimResult("loss", sl, bar.get("timestamp"), i, i + 1, -1.0, mae, mfe)
            if low <= tp:
                r = (entry - tp) / risk
                return TradeSimResult("win", tp, bar.get("timestamp"), i, i + 1, r, mae, mfe)

    if bars:
        last = bars[-1]
        exit_price = float(last["close"])
        r = (exit_price - entry) / risk if direction == "long" else (entry - exit_price) / risk
        return TradeSimResult(
            "timeout", exit_price, last.get("timestamp"), len(bars) - 1, len(bars), r, mae, mfe
        )

    return TradeSimResult("timeout", entry, None, -1, 0, 0.0, 0.0, 0.0)


def spread_cost_r(spread_price_units: float, risk_price_units: float) -> float:
    """Round-trip spread cost expressed as a fraction of 1R."""
    if risk_price_units <= 0:
        return 0.0
    return spread_price_units / risk_price_units


def risk_reward_target(entry: float, sl: float, direction: str, rr: float) -> float:
    """Take-profit price for a given entry/stop/direction/reward-risk ratio."""
    risk = abs(entry - sl)
    return entry + risk * rr if direction == "long" else entry - risk * rr


@dataclass
class SMCTrade:
    """Common trade-record schema emitted by every SMC-LSS_v0 entry model
    (research/experiments/smc_lss_e1.py, e2.py, e3.py, combined.py)."""

    trade_id: str
    symbol: str
    branch: str          # 'E1' | 'E2' | 'E3' | 'combined'
    entry_time: object
    exit_time: object
    entry_price: float
    exit_price: float
    direction: str
    R_multiple: float
    spread: float
    MAE: float
    MFE: float


def build_trade_record(
    *,
    trade_id: str,
    symbol: str,
    branch: str,
    entry_time: object,
    entry_price: float,
    direction: str,
    sim: TradeSimResult,
    spread_price_units: float,
    risk_price_units: float,
) -> SMCTrade:
    """Combine a TradeSimResult with spread cost into the net-of-fees
    SMCTrade record (CLAUDE.md §0.3 — net-of-fees only)."""
    net_r = sim.r_multiple - spread_cost_r(spread_price_units, risk_price_units)
    return SMCTrade(
        trade_id=trade_id,
        symbol=symbol,
        branch=branch,
        entry_time=entry_time,
        exit_time=sim.exit_time,
        entry_price=entry_price,
        exit_price=sim.exit_price,
        direction=direction,
        R_multiple=net_r,
        spread=spread_price_units,
        MAE=sim.mae,
        MFE=sim.mfe,
    )

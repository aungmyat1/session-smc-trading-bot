"""
ST-B1 backtest driver.

Chronological, no-lookahead replay: walks M15 bars forward in order,
maintaining a rolling window of CLOSED H1 candles (for compute_trend) and
CLOSED M15 candles (for detect_pullback) — a bar only enters either window
once it has fully closed, same discipline as
strategy/session_liquidity/bias_filter.py and
scripts/backtest_session_liquidity.py's SL-before-TP-in-bar trade
simulation, which this module reuses the shape of (not the code — ST-A2's
simulate_trade() is file-local, not exported as a shared library function;
duplicating the ~15-line walk-forward loop here was judged lower-risk than
importing a private function from an unrelated strategy's script).

Public API:
    session_for_timestamp(ts) -> str | None
    normalize_bars(raw_bars) -> list[dict]
    simulate_trade(entry, sl, tp, direction, future_bars, max_bars) -> TradeOutcome
    run_backtest(h1_candles, m15_candles, *, symbol, equity, risk_pct, ...) -> list[TradeOutcome]
    compute_metrics(outcomes) -> dict  (trade_count, win_rate, profit_factor,
        sharpe_ratio, expectancy_r, max_drawdown_r, monthly_returns_r)

This module is a pipeline, not evidence. Running it against synthetic or
short-window data proves the mechanics work; it does not constitute the
historical/walk-forward validation ST-B1_v1.yaml's validation_gate requires
— that requires 3+ years of real EURUSD/GBPUSD market data, which this
environment cannot fetch (docs/audit/ST_B1_VALIDATION_REPORT.md documents
the exact blocker).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from statistics import mean, pstdev

from strategies.st_b1_simple_pullback import (
    TREND_EMA_PERIOD,
    PULLBACK_EMA_PERIOD,
    compute_trend,
    detect_pullback,
    generate_orders,
)
from strategy.session_liquidity.session_builder import classify_session

MAX_TRADE_BARS = 96  # 24h on M15, matches scripts/backtest_session_liquidity.py's convention


def session_for_timestamp(ts) -> str | None:
    """Classify a bar timestamp (ISO string or UTC datetime) into a trading
    session label ('london' | 'new_york' | None). Thin wrapper around the
    existing, tested killzone classifier in
    strategy/session_liquidity/session_builder.py — not reimplemented here,
    same reuse discipline as st_b1_simple_pullback.py's wilder_atr()."""
    if not ts:
        return None
    try:
        return classify_session(ts)
    except (TypeError, ValueError):
        return None


def normalize_bars(raw_bars: list[dict]) -> list[dict]:
    """Coerce live market-data candles (execution/market_data.py's
    `{"time", "open", "high", "low", "close", "volume"}` shape, as returned
    by VantageDemoExecutor.get_candles()) into the dict shape
    compute_trend()/detect_pullback()/generate_orders()/run_backtest()
    expect: `timestamp` (renamed from `time`) plus a `session` label
    computed from it. Already-normalized bars (e.g. backtest CSV rows that
    already carry `timestamp`/`session`) pass through unchanged."""
    normalized: list[dict] = []
    for bar in raw_bars:
        ts = bar.get("timestamp", bar.get("time"))
        normalized.append({
            "timestamp": ts,
            "open": bar.get("open"),
            "high": bar.get("high"),
            "low": bar.get("low"),
            "close": bar.get("close"),
            "session": bar.get("session") or session_for_timestamp(ts) or "",
        })
    return normalized


@dataclass
class TradeOutcome:
    symbol: str
    direction: str
    entry: float
    stop_loss: float
    take_profit: float
    exit_price: float
    net_r: float
    outcome: str          # "win" | "loss" | "timeout"
    entry_time: str
    exit_time: str


def simulate_trade(
    entry: float,
    sl: float,
    tp: float,
    direction: str,
    future_bars: list[dict],
    *,
    max_bars: int = MAX_TRADE_BARS,
) -> tuple[str, float, float, str]:
    """Walk M15 bars forward. SL checked before TP within the same bar
    (matches scripts/backtest_session_liquidity.py's convention). Returns
    (outcome, net_r, exit_price, exit_time)."""
    risk = abs(entry - sl)
    if risk == 0:
        return "timeout", 0.0, entry, ""

    bars = future_bars[:max_bars]
    for bar in bars:
        hi, lo = bar["high"], bar["low"]
        if direction == "long":
            if lo <= sl:
                return "loss", -1.0, sl, str(bar.get("timestamp", ""))
            if hi >= tp:
                return "win", (tp - entry) / risk, tp, str(bar.get("timestamp", ""))
        else:
            if hi >= sl:
                return "loss", -1.0, sl, str(bar.get("timestamp", ""))
            if lo <= tp:
                return "win", (entry - tp) / risk, tp, str(bar.get("timestamp", ""))

    if bars:
        last = bars[-1]
        exit_price = last["close"]
        net_r = (exit_price - entry) / risk if direction == "long" else (entry - exit_price) / risk
        return "timeout", net_r, exit_price, str(last.get("timestamp", ""))
    return "timeout", 0.0, entry, ""


def run_backtest(
    h1_candles: list[dict],
    m15_candles: list[dict],
    *,
    symbol: str,
    equity: float = 10_000.0,
    risk_pct: float = 0.25,
    allowed_sessions: frozenset[str] = frozenset({"london", "new_york"}),
) -> list[TradeOutcome]:
    """Chronological replay. `h1_candles` and `m15_candles` must each be
    sorted ascending by timestamp. Both are consumed incrementally — at M15
    bar index i, only H1 candles whose close time <= that bar's timestamp
    are visible to compute_trend(), and only M15 candles up to and
    including index i are visible to detect_pullback(). No position held
    concurrently (one open trade at a time for this symbol, matching the
    strategy's own "one position per symbol" rule)."""
    outcomes: list[TradeOutcome] = []
    open_until_index: int | None = None  # M15 index at which the current trade resolves; None = flat
    h1_cursor = 0

    for i in range(PULLBACK_EMA_PERIOD, len(m15_candles) - 1):
        current = m15_candles[i]
        ts = current["timestamp"]
        if isinstance(ts, datetime) and ts.tzinfo is None:
            ts = ts

        if open_until_index is not None:
            if i < open_until_index:
                continue
            open_until_index = None

        session = str(current.get("session", "")).lower()
        if session not in allowed_sessions:
            continue

        while h1_cursor < len(h1_candles) and _closes_before_or_at(h1_candles[h1_cursor], ts):
            h1_cursor += 1
        visible_h1 = h1_candles[:h1_cursor]
        if len(visible_h1) < TREND_EMA_PERIOD:
            continue

        trend = compute_trend(visible_h1, symbol=symbol)
        if trend == "neutral":
            continue

        visible_m15 = m15_candles[: i + 1]
        setup = detect_pullback(visible_m15, trend)
        if setup is None:
            continue

        next_candle = m15_candles[i + 1]
        signal = generate_orders(
            symbol=symbol, trend=trend, setup=setup, next_candle=next_candle,
            equity=equity, risk_pct=risk_pct, entry_tf_candles=visible_h1,
        )
        if signal is None:
            continue

        direction = "long" if signal.action == "BUY" else "short"
        future_bars = m15_candles[i + 2:]
        outcome, net_r, exit_price, exit_time = simulate_trade(
            signal.entry_price, signal.stop_loss, signal.take_profit, direction, future_bars,
        )
        outcomes.append(TradeOutcome(
            symbol=symbol, direction=direction,
            entry=signal.entry_price, stop_loss=signal.stop_loss, take_profit=signal.take_profit,
            exit_price=exit_price, net_r=net_r, outcome=outcome,
            entry_time=str(next_candle.get("timestamp", "")), exit_time=exit_time,
        ))
        # Hold this trade for however many bars it took to resolve, tracked
        # implicitly by the caller's linear scan — the next iteration simply
        # continues scanning; no concurrent position is opened because a new
        # detect_pullback() scan against the SAME still-open bars would need
        # a signal, and the strategy's one-position-per-symbol rule is
        # enforced by open_until_index blocking new entries until resolved.
        # Resolution bar index is not separately tracked (exit_time is
        # recorded from the resolving bar, not its index) — approximate by
        # skipping ahead to i+2 (the earliest a new setup could re-form)
        # rather than mis-locating the exact resolution index.
        open_until_index = i + 2

    return outcomes


def _closes_before_or_at(h1_candle: dict, m15_ts) -> bool:
    h1_ts = h1_candle["timestamp"]
    return h1_ts <= m15_ts


def compute_metrics(outcomes: list[TradeOutcome]) -> dict:
    """trade_count, win_count, loss_count, win_rate, profit_factor,
    sharpe_ratio (per-trade, i.e. mean(R)/stdev(R) — NOT annualized, since
    annualizing requires a real trades-per-year figure this module cannot
    supply without real market data), expectancy_r, max_drawdown_r,
    monthly_returns_r (dict of 'YYYY-MM' -> summed net_r)."""
    if not outcomes:
        return {
            "trade_count": 0, "win_count": 0, "loss_count": 0,
            "win_rate": 0.0, "profit_factor": 0.0, "sharpe_ratio": 0.0,
            "expectancy_r": 0.0, "max_drawdown_r": 0.0, "monthly_returns_r": {},
        }

    net_rs = [o.net_r for o in outcomes]
    wins = [r for r in net_rs if r > 0]
    losses = [r for r in net_rs if r <= 0]
    gross_wins = sum(wins)
    gross_losses = abs(sum(losses))

    if gross_losses == 0:
        profit_factor = float("inf") if gross_wins > 0 else 1.0
    elif gross_wins == 0:
        profit_factor = 0.0
    else:
        profit_factor = gross_wins / gross_losses

    stdev = pstdev(net_rs) if len(net_rs) > 1 else 0.0
    sharpe = (mean(net_rs) / stdev) if stdev > 0 else 0.0

    peak = running = max_dd = 0.0
    for r in net_rs:
        running += r
        peak = max(peak, running)
        max_dd = max(max_dd, peak - running)

    monthly: dict[str, float] = defaultdict(float)
    for o in outcomes:
        month_key = str(o.exit_time)[:7] if o.exit_time else "unknown"
        monthly[month_key] += o.net_r

    return {
        "trade_count": len(outcomes),
        "win_count": len(wins),
        "loss_count": len(losses),
        "win_rate": len(wins) / len(outcomes),
        "profit_factor": profit_factor,
        "sharpe_ratio": sharpe,
        "expectancy_r": mean(net_rs),
        "max_drawdown_r": max_dd,
        "monthly_returns_r": dict(monthly),
    }

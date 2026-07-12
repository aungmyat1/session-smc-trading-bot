"""ST-B1 deterministic backtest and validation helpers."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from statistics import mean, pstdev
from typing import Iterable

from strategies.st_b1_simple_pullback import (
    NEUTRAL_THRESHOLD_PIPS_DEFAULT,
    PULLBACK_EMA_PERIOD,
    TREND_EMA_PERIOD,
    PullbackSetup,
    ema,
    generate_orders,
)

MAX_TRADE_BARS = 96
PIP_SIZE = {"EURUSD": 0.0001, "GBPUSD": 0.0001, "XAUUSD": 0.1}
DEFAULT_ALLOWED_SESSIONS = frozenset({"london", "new_york"})


@dataclass
class TradeOutcome:
    symbol: str
    direction: str
    session: str
    entry: float
    stop_loss: float
    take_profit: float
    exit_price: float
    gross_r: float
    net_r: float
    outcome: str
    entry_time: str
    exit_time: str
    bars_held: int
    risk_pips: float
    cost_pips: float = 0.0
    spread_model: str = "gross"

    def to_dict(self) -> dict:
        return asdict(self)


def parse_ts(value) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def normalize_bars(rows: Iterable[dict]) -> list[dict]:
    bars: list[dict] = []
    for row in rows:
        ts = row.get("timestamp") or row.get("timestamp_utc") or row.get("time")
        if ts is None:
            continue
        bar = dict(row)
        bar["timestamp"] = parse_ts(ts)
        for key in ("open", "high", "low", "close"):
            bar[key] = float(bar[key])
        bars.append(bar)
    bars.sort(key=lambda item: item["timestamp"])
    return bars


def session_for_timestamp(ts: datetime) -> str:
    ts = parse_ts(ts)
    if ts.weekday() >= 5:
        return "blocked"
    minutes = ts.hour * 60 + ts.minute
    if 7 * 60 <= minutes < 10 * 60:
        return "london"
    if 13 * 60 <= minutes < 16 * 60:
        return "new_york"
    if 0 <= minutes < 7 * 60:
        return "asian"
    return "off"


def with_sessions(m15_candles: list[dict]) -> list[dict]:
    bars = normalize_bars(m15_candles)
    for bar in bars:
        if not bar.get("session"):
            bar["session"] = session_for_timestamp(bar["timestamp"])
        else:
            bar["session"] = str(bar["session"]).lower()
    return bars


def simulate_trade(
    entry: float,
    sl: float,
    tp: float,
    direction: str,
    future_bars: list[dict],
    *,
    max_bars: int = MAX_TRADE_BARS,
) -> tuple[str, float, float, str, int]:
    """Walk M15 bars forward with conservative SL-before-TP precedence."""
    risk = abs(entry - sl)
    if risk == 0:
        return "timeout", 0.0, entry, "", 0

    bars = future_bars[:max_bars]
    for offset, bar in enumerate(bars, start=1):
        hi, lo = float(bar["high"]), float(bar["low"])
        exit_time = parse_ts(bar["timestamp"]).isoformat() if bar.get("timestamp") is not None else ""
        if direction == "long":
            if lo <= sl:
                return "loss", -1.0, sl, exit_time, offset
            if hi >= tp:
                return "win", (tp - entry) / risk, tp, exit_time, offset
        else:
            if hi >= sl:
                return "loss", -1.0, sl, exit_time, offset
            if lo <= tp:
                return "win", (entry - tp) / risk, tp, exit_time, offset

    if bars:
        last = bars[-1]
        exit_price = float(last["close"])
        net_r = (exit_price - entry) / risk if direction == "long" else (entry - exit_price) / risk
        exit_time = parse_ts(last["timestamp"]).isoformat() if last.get("timestamp") is not None else ""
        return "timeout", net_r, exit_price, exit_time, len(bars)
    return "timeout", 0.0, entry, "", 0


def _h1_closed_before_or_at(h1_candle: dict, m15_ts) -> bool:
    return parse_ts(h1_candle["timestamp"]) + timedelta(hours=1) <= parse_ts(m15_ts)


def _trend_from_precomputed(h1: list[dict], h1_ema: list[float | None], cursor: int, symbol: str) -> str:
    if cursor < TREND_EMA_PERIOD:
        return "neutral"
    latest_close = float(h1[cursor - 1]["close"])
    latest_ema = h1_ema[cursor - 1]
    if latest_ema is None:
        return "neutral"
    threshold = NEUTRAL_THRESHOLD_PIPS_DEFAULT * PIP_SIZE.get(symbol, 0.0001)
    if abs(latest_close - latest_ema) < threshold:
        return "neutral"
    return "bullish" if latest_close > latest_ema else "bearish"


def _setup_from_precomputed(m15: list[dict], m15_ema: list[float | None], index: int, trend: str) -> PullbackSetup | None:
    if trend not in ("bullish", "bearish") or index < 1:
        return None
    latest_ema = m15_ema[index]
    if latest_ema is None:
        return None
    rejection = m15[index]
    prior = m15[index - 1]
    if trend == "bullish":
        if float(rejection["low"]) <= latest_ema and float(rejection["close"]) > float(prior["high"]):
            return PullbackSetup(
                direction="long",
                rejection_candle=rejection,
                prior_candle=prior,
                swing_low=float(rejection["low"]),
                swing_high=float(rejection["high"]),
                ema20_at_rejection=float(latest_ema),
            )
        return None
    if float(rejection["high"]) >= latest_ema and float(rejection["close"]) < float(prior["low"]):
        return PullbackSetup(
            direction="short",
            rejection_candle=rejection,
            prior_candle=prior,
            swing_low=float(rejection["low"]),
            swing_high=float(rejection["high"]),
            ema20_at_rejection=float(latest_ema),
        )
    return None


def run_backtest(
    h1_candles: list[dict],
    m15_candles: list[dict],
    *,
    symbol: str,
    equity: float = 10_000.0,
    risk_pct: float = 0.25,
    allowed_sessions: frozenset[str] = DEFAULT_ALLOWED_SESSIONS,
) -> list[TradeOutcome]:
    """Chronological replay with closed H1 context and one position per symbol."""
    h1 = normalize_bars(h1_candles)
    m15 = with_sessions(m15_candles)
    h1_ema = ema([float(bar["close"]) for bar in h1], TREND_EMA_PERIOD)
    m15_ema = ema([float(bar["close"]) for bar in m15], PULLBACK_EMA_PERIOD)
    outcomes: list[TradeOutcome] = []
    open_until_index = -1
    h1_cursor = 0

    for index in range(PULLBACK_EMA_PERIOD, len(m15) - 1):
        if index <= open_until_index:
            continue
        current = m15[index]
        ts = current["timestamp"]
        session = str(current.get("session", "")).lower()
        if session not in allowed_sessions:
            continue

        while h1_cursor < len(h1) and _h1_closed_before_or_at(h1[h1_cursor], ts):
            h1_cursor += 1
        if h1_cursor < TREND_EMA_PERIOD:
            continue

        trend = _trend_from_precomputed(h1, h1_ema, h1_cursor, symbol)
        if trend == "neutral":
            continue

        setup = _setup_from_precomputed(m15, m15_ema, index, trend)
        if setup is None:
            continue

        next_candle = m15[index + 1]
        visible_h1 = h1[:h1_cursor]
        signal = generate_orders(
            symbol=symbol,
            trend=trend,
            setup=setup,
            next_candle=next_candle,
            equity=equity,
            risk_pct=risk_pct,
            entry_tf_candles=visible_h1,
        )
        if signal is None:
            continue

        direction = "long" if signal.action == "BUY" else "short"
        outcome, gross_r, exit_price, exit_time, bars_held = simulate_trade(
            signal.entry_price,
            signal.stop_loss,
            signal.take_profit,
            direction,
            m15[index + 2 :],
        )
        risk_pips = abs(signal.entry_price - signal.stop_loss) / PIP_SIZE.get(symbol, 0.0001)
        outcomes.append(
            TradeOutcome(
                symbol=symbol,
                direction=direction,
                session=str(signal.metadata.get("session", session)),
                entry=float(signal.entry_price),
                stop_loss=float(signal.stop_loss),
                take_profit=float(signal.take_profit),
                exit_price=float(exit_price),
                gross_r=float(gross_r),
                net_r=float(gross_r),
                outcome=outcome,
                entry_time=parse_ts(next_candle["timestamp"]).isoformat(),
                exit_time=exit_time,
                bars_held=int(bars_held),
                risk_pips=float(risk_pips),
            )
        )
        open_until_index = index + 1 + max(bars_held, 1)

    return outcomes


def apply_costs(outcomes: list[TradeOutcome], cost_pips_by_symbol: dict[str, float], spread_model: str) -> list[TradeOutcome]:
    adjusted: list[TradeOutcome] = []
    for outcome in outcomes:
        cost_pips = float(cost_pips_by_symbol.get(outcome.symbol, 0.0) or 0.0)
        cost_r = cost_pips / outcome.risk_pips if outcome.risk_pips > 0 else 0.0
        payload = outcome.to_dict()
        payload.update(
            {
                "net_r": outcome.gross_r - cost_r,
                "cost_pips": cost_pips,
                "spread_model": spread_model,
            }
        )
        adjusted.append(TradeOutcome(**payload))
    return adjusted


def compute_metrics(outcomes: list[TradeOutcome], *, risk_pct: float = 0.25) -> dict:
    if not outcomes:
        return {
            "trade_count": 0,
            "win_count": 0,
            "loss_count": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "sharpe_ratio": 0.0,
            "expectancy_r": 0.0,
            "max_drawdown_r": 0.0,
            "max_drawdown_pct": 0.0,
            "total_net_r": 0.0,
            "monthly_returns_r": {},
        }

    net_rs = [float(o.net_r) for o in outcomes]
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
    sharpe = mean(net_rs) / stdev if stdev > 0 else 0.0

    peak = running = max_dd = 0.0
    for r_value in net_rs:
        running += r_value
        peak = max(peak, running)
        max_dd = max(max_dd, peak - running)

    monthly: dict[str, float] = defaultdict(float)
    for outcome in outcomes:
        month_key = str(outcome.exit_time or outcome.entry_time)[:7]
        monthly[month_key] += float(outcome.net_r)

    return {
        "trade_count": len(outcomes),
        "win_count": len(wins),
        "loss_count": len(losses),
        "win_rate": len(wins) / len(outcomes),
        "profit_factor": profit_factor,
        "sharpe_ratio": sharpe,
        "expectancy_r": mean(net_rs),
        "max_drawdown_r": max_dd,
        "max_drawdown_pct": max_dd * risk_pct,
        "total_net_r": sum(net_rs),
        "monthly_returns_r": dict(sorted(monthly.items())),
    }


def gate_passed(metrics_standard: dict, metrics_stress: dict) -> bool:
    return (
        metrics_standard["trade_count"] >= 200
        and metrics_standard["profit_factor"] > 1.25
        and metrics_stress["profit_factor"] > 1.25
        and metrics_standard["sharpe_ratio"] > 1.20
        and metrics_stress["sharpe_ratio"] > 1.20
        and metrics_standard["max_drawdown_pct"] < 15.0
        and metrics_stress["max_drawdown_pct"] < 15.0
    )

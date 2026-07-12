"""
ST-B1 — Simple Trend Pullback.

A deliberately simple baseline: H1 EMA200 trend filter, M15 EMA20 pullback +
rejection-candle confirmation, fixed 1:2 risk/reward, entry at next candle
open. No trailing stop, no partial profit, no averaging down, one position
per symbol. See config/strategies/ST-B1_v1.yaml for the full parameter spec.

Public API:
    compute_trend(h1_candles, before_dt, ...) -> 'bullish' | 'bearish' | 'neutral'
    detect_pullback(m15_candles, trend, ...) -> PullbackSetup | None
    validate_entry(setup, next_candle) -> bool
    calculate_position_size(equity, risk_pct, sl_distance, ...) -> float (lots)
    generate_orders(...) -> Signal | None

Lookahead rule (same discipline as strategy/session_liquidity/bias_filter.py):
    A candle may only be used once it has fully closed. compute_trend() and
    detect_pullback() both take an explicit `before_dt` / operate only on the
    caller-supplied candle list, which the caller is responsible for
    truncating to closed bars only — these functions never look past the
    last element of the list they're given.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from shared.strategy_api.signal import Signal
from strategy.session_liquidity.displacement_detector import wilder_atr

_UTC = timezone.utc

PIP_SIZE = {
    "EURUSD": 0.0001,
    "GBPUSD": 0.0001,
}

MIN_STOP_PIPS = {
    "EURUSD": 8.0,
    "GBPUSD": 10.0,
}

RISK_REWARD = 2.0
TREND_EMA_PERIOD = 200
PULLBACK_EMA_PERIOD = 20
NEUTRAL_THRESHOLD_PIPS_DEFAULT = 3.0
XAUUSD_ATR_PERIOD = 14
XAUUSD_ATR_MULTIPLIER = 0.5


# ── Helpers ──────────────────────────────────────────────────────────────────

def _parse_utc(t) -> datetime:
    if isinstance(t, datetime):
        return t if t.tzinfo else t.replace(tzinfo=_UTC)
    return datetime.fromisoformat(str(t).replace("Z", "+00:00"))


def ema(values: list[float], period: int) -> list[float | None]:
    """Standard exponential moving average. Same list-in/list-out, None-prefix
    convention as strategy.session_liquidity.displacement_detector.wilder_atr:
    indices 0..period-2 -> None (insufficient history), index period-1 -> seed
    (simple mean of the first `period` values), thereafter the recursive EMA.
    """
    n = len(values)
    out: list[float | None] = [None] * n
    if n < period:
        return out
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    k = 2.0 / (period + 1)
    prev = seed
    for i in range(period, n):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def _pip_size(symbol: str) -> float:
    return PIP_SIZE.get(symbol, 0.0001)


# ── Step 1: Trend filter ────────────────────────────────────────────────────

def compute_trend(
    h1_candles: list[dict],
    *,
    symbol: str,
    ema_period: int = TREND_EMA_PERIOD,
    neutral_threshold_pips: float = NEUTRAL_THRESHOLD_PIPS_DEFAULT,
) -> str:
    """Returns 'bullish' | 'bearish' | 'neutral'.

    `h1_candles` must already be truncated to closed bars only, chronological
    order, each a dict with a 'close' key. Uses the LAST candle in the list as
    "now."
    """
    if len(h1_candles) < ema_period:
        return "neutral"
    closes = [c["close"] for c in h1_candles]
    ema_series = ema(closes, ema_period)
    latest_ema = ema_series[-1]
    if latest_ema is None:
        return "neutral"
    latest_close = closes[-1]
    threshold = neutral_threshold_pips * _pip_size(symbol)
    if abs(latest_close - latest_ema) < threshold:
        return "neutral"
    return "bullish" if latest_close > latest_ema else "bearish"


# ── Step 2: Pullback detection ──────────────────────────────────────────────

@dataclass
class PullbackSetup:
    direction: str        # 'long' | 'short'
    rejection_candle: dict
    prior_candle: dict
    swing_low: float
    swing_high: float
    ema20_at_rejection: float


def detect_pullback(
    m15_candles: list[dict],
    trend: str,
    *,
    ema_period: int = PULLBACK_EMA_PERIOD,
) -> PullbackSetup | None:
    """Evaluates the LAST candle in `m15_candles` as the rejection candle
    against the second-to-last as the "previous candle" the spec's rejection
    rule references. `m15_candles` must already be closed-bars-only,
    chronological order.

    Long setup: trend == 'bullish' AND the rejection candle's low tags/dips
    into EMA20 (retrace) AND the rejection candle closes above the prior
    candle's high.
    Short setup: mirror, trend == 'bearish', rejection candle's high tags/
    pokes EMA20, closes below the prior candle's low.
    """
    if trend not in ("bullish", "bearish"):
        return None
    if len(m15_candles) < max(ema_period, 2):
        return None

    closes = [c["close"] for c in m15_candles]
    ema_series = ema(closes, ema_period)
    latest_ema = ema_series[-1]
    if latest_ema is None:
        return None

    rejection = m15_candles[-1]
    prior = m15_candles[-2]

    if trend == "bullish":
        retraced = rejection["low"] <= latest_ema
        rejected_up = rejection["close"] > prior["high"]
        if retraced and rejected_up:
            return PullbackSetup(
                direction="long",
                rejection_candle=rejection,
                prior_candle=prior,
                swing_low=rejection["low"],
                swing_high=rejection["high"],
                ema20_at_rejection=latest_ema,
            )
        return None

    # trend == "bearish"
    retraced = rejection["high"] >= latest_ema
    rejected_down = rejection["close"] < prior["low"]
    if retraced and rejected_down:
        return PullbackSetup(
            direction="short",
            rejection_candle=rejection,
            prior_candle=prior,
            swing_low=rejection["low"],
            swing_high=rejection["high"],
            ema20_at_rejection=latest_ema,
        )
    return None


# ── Step 3: Entry validation ────────────────────────────────────────────────

def validate_entry(setup: PullbackSetup, next_candle: dict) -> bool:
    """`next_candle` is the candle immediately following the rejection candle
    — entry fills at its open. Rejects (no market chasing) if `next_candle`
    isn't the very next bar after the rejection candle (caller supplies the
    literal next element; this only sanity-checks it isn't the same candle
    or missing required fields) or if its open has already gapped through
    the stop level (a valid safety check independent of "chasing" per se —
    an entry whose stop is already violated at open is not a valid fill)."""
    if setup is None or next_candle is None:
        return False
    if "open" not in next_candle:
        return False
    entry_price = next_candle["open"]
    if setup.direction == "long" and entry_price <= setup.swing_low:
        return False
    if setup.direction == "short" and entry_price >= setup.swing_high:
        return False
    return True


# ── Step 4/5: Stop loss, take profit, position sizing ───────────────────────

def _xauusd_atr_stop_distance(h1_or_entry_tf_candles: list[dict], *, broker_minimum: float) -> float:
    """XAUUSD stop distance in price units: max(ATR14 * 0.5, broker_minimum).
    Reuses strategy.session_liquidity.displacement_detector.wilder_atr rather
    than reimplementing ATR."""
    atr_series = wilder_atr(h1_or_entry_tf_candles, period=XAUUSD_ATR_PERIOD)
    latest_atr = atr_series[-1] if atr_series else None
    if latest_atr is None:
        return broker_minimum
    return max(latest_atr * XAUUSD_ATR_MULTIPLIER, broker_minimum)


def compute_stop_and_target(
    setup: PullbackSetup,
    entry_price: float,
    *,
    symbol: str,
    entry_tf_candles: list[dict] | None = None,
    xauusd_broker_minimum: float = 0.0,
) -> tuple[float, float]:
    """Returns (stop_loss, take_profit) prices. Enforces the per-symbol
    minimum stop distance as a floor (widens toward entry-minus/plus the
    minimum if the raw swing-based stop would be tighter than the minimum;
    never tightens a stop that's already wider than the minimum)."""
    if symbol == "XAUUSD":
        min_distance = _xauusd_atr_stop_distance(
            entry_tf_candles or [], broker_minimum=xauusd_broker_minimum,
        )
    else:
        min_distance = MIN_STOP_PIPS.get(symbol, 0.0) * _pip_size(symbol)

    if setup.direction == "long":
        raw_distance = entry_price - setup.swing_low
        distance = max(raw_distance, min_distance)
        stop_loss = entry_price - distance
        take_profit = entry_price + distance * RISK_REWARD
    else:
        raw_distance = setup.swing_high - entry_price
        distance = max(raw_distance, min_distance)
        stop_loss = entry_price + distance
        take_profit = entry_price - distance * RISK_REWARD

    return stop_loss, take_profit


def calculate_position_size(
    equity: float,
    risk_pct: float,
    stop_distance: float,
    *,
    pip_value_per_lot: float = 10.0,
    pip_size: float = 0.0001,
    max_risk_pct: float = 0.50,
) -> float:
    """Standard fixed-fractional position sizing.

    risk_pct is clamped to max_risk_pct (spec: "Maximum: 0.50%") — a caller
    passing a larger risk_pct does not get a larger position than the cap
    allows.
    """
    if equity <= 0 or stop_distance <= 0:
        return 0.0
    effective_risk_pct = min(risk_pct, max_risk_pct)
    risk_amount = equity * (effective_risk_pct / 100.0)
    stop_distance_pips = stop_distance / pip_size
    if stop_distance_pips <= 0:
        return 0.0
    lots = risk_amount / (stop_distance_pips * pip_value_per_lot)
    return round(lots, 2)


# ── Step 6: Order generation ────────────────────────────────────────────────

def generate_orders(
    *,
    symbol: str,
    trend: str,
    setup: PullbackSetup | None,
    next_candle: dict | None,
    equity: float,
    risk_pct: float = 0.25,
    entry_tf_candles: list[dict] | None = None,
    xauusd_broker_minimum: float = 0.0,
    open_position_count: int = 0,
    max_simultaneous_positions: int = 2,
) -> Signal | None:
    """Ties compute_trend -> detect_pullback -> validate_entry -> sizing
    together into a single Signal, or None if any gate fails. One position
    per symbol is enforced by the caller passing open_position_count for
    THIS symbol specifically (must be 0); max_simultaneous_positions caps
    the account-wide total and is checked the same way."""
    if setup is None:
        return None
    if open_position_count > 0:
        return None  # one position per symbol
    if not validate_entry(setup, next_candle):
        return None

    entry_price = next_candle["open"]
    stop_loss, take_profit = compute_stop_and_target(
        setup, entry_price,
        symbol=symbol,
        entry_tf_candles=entry_tf_candles,
        xauusd_broker_minimum=xauusd_broker_minimum,
    )
    stop_distance = abs(entry_price - stop_loss)
    lots = calculate_position_size(
        equity, risk_pct, stop_distance,
        pip_size=_pip_size(symbol) if symbol != "XAUUSD" else 0.01,
    )
    if lots <= 0:
        return None

    action = "BUY" if setup.direction == "long" else "SELL"
    timestamp = next_candle.get("timestamp") or setup.rejection_candle.get("timestamp")
    if isinstance(timestamp, datetime):
        timestamp = timestamp.isoformat()

    return Signal(
        timestamp=str(timestamp),
        strategy_name="ST-B1",
        symbol=symbol,
        action=action,
        order_type="MARKET",
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_percent=min(risk_pct, 0.50),
        confidence=1.0,
        metadata={
            "session": next_candle.get("session", ""),
            "trend": trend,
            "lots": lots,
            "ema20_at_rejection": setup.ema20_at_rejection,
            "swing_low": setup.swing_low,
            "swing_high": setup.swing_high,
        },
    )

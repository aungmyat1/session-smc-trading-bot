"""
SA-06 — Entry Engine.

Converts a confirmed SweepResult + DisplacementResult into a Signal.
No broker interaction. No position sizing. Signal generation only.

Public API:
    Signal         — dataclass consumed by execution layer and backtest
    build_signal() — returns Signal | None
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from strategy.session_liquidity.session_builder import AsianRange
from strategy.session_liquidity.sweep_detector import SweepResult
from strategy.session_liquidity.displacement_detector import DisplacementResult

_UTC = timezone.utc
_PIP = 0.0001
_VALID_SESSIONS = frozenset({"london", "new_york"})


# ── Signal contract (execution layer reads exactly these fields) ───────────────

@dataclass
class Signal:
    """
    Output of the signal chain. Immutable once created.

    Execution contract (EXECUTION_SPEC.md §Signal Contract):
        side, entry, stop_loss, take_profit, reason, session, timestamp

    Backtest extras:
        risk_pips, reward_pips, rr
    """
    side: str            # 'long' | 'short'
    entry: float
    stop_loss: float
    take_profit: float
    risk_pips: float     # sl_distance / 0.0001
    reward_pips: float   # risk_pips × rr
    rr: float

    session: str         # 'london' | 'new_york'
    timestamp: datetime  # UTC, bar-close time of displacement candle
    reason: str


# ── Entry engine ──────────────────────────────────────────────────────────────

def build_signal(
    candle: dict,
    sweep: SweepResult,
    displacement: DisplacementResult,
    asian_range: AsianRange,
    session: str,
    rr: float,
    sl_buffer_pips: float,
) -> "Signal | None":
    """
    Convert a confirmed sweep + displacement pair into a Signal.

    Args:
        candle:          The displacement candle (bar-close execution).
                         Must have float-coercible 'close' and a 'time' field.
        sweep:           SweepResult from detect_sweep(). Must have detected=True.
        displacement:    DisplacementResult from detect_displacement(). Must have detected=True.
        asian_range:     AsianRange for the trade date. Must have high > low.
        session:         'london' | 'new_york'
        rr:              Risk-reward ratio (positive float). e.g. 2.0, 3.0, 4.0, 5.0
        sl_buffer_pips:  Buffer added below/above sweep wick for stop loss (in pips).

    Returns:
        Signal if all gates pass, None otherwise.

    Rejection reasons (any triggers None):
        - sweep.detected is False
        - displacement.detected is False
        - session not in {'london', 'new_york'}
        - asian_range is None or asian_range.high <= asian_range.low
        - rr <= 0
        - sl_buffer_pips < 0
        - candle missing 'close' or invalid numeric
        - risk (sl_distance) <= 0 — degenerate geometry
    """
    # ── Gate 1: inputs detected ───────────────────────────────────────────────
    if sweep is None or not sweep.detected:
        return None
    if displacement is None or not displacement.detected:
        return None

    # ── Gate 2: session ───────────────────────────────────────────────────────
    if session not in _VALID_SESSIONS:
        return None

    # ── Gate 3: asian range valid ─────────────────────────────────────────────
    if asian_range is None or asian_range.high <= asian_range.low:
        return None

    # ── Gate 4: rr and buffer ─────────────────────────────────────────────────
    if rr <= 0:
        return None
    if sl_buffer_pips < 0:
        return None

    # ── Gate 5: candle parse ──────────────────────────────────────────────────
    try:
        entry = float(candle["close"])
    except (KeyError, TypeError, ValueError):
        return None

    # sweep_price is guaranteed non-None when detected=True
    sweep_price = sweep.sweep_price
    if sweep_price is None:
        return None

    buf = sl_buffer_pips * _PIP

    # ── Gate 6: SL geometry ───────────────────────────────────────────────────
    if sweep.side == "long":
        stop_loss = sweep_price - buf
        risk = entry - stop_loss
    elif sweep.side == "short":
        stop_loss = sweep_price + buf
        risk = stop_loss - entry
    else:
        return None

    if risk <= 0:
        return None

    # ── Compute TP and pip metrics ────────────────────────────────────────────
    if sweep.side == "long":
        take_profit = entry + risk * rr
    else:
        take_profit = entry - risk * rr

    risk_pips   = risk / _PIP
    reward_pips = risk_pips * rr

    # ── Timestamp ─────────────────────────────────────────────────────────────
    raw_time = candle.get("time")
    if raw_time is None:
        timestamp = datetime.now(_UTC)
    elif isinstance(raw_time, datetime):
        timestamp = raw_time if raw_time.tzinfo else raw_time.replace(tzinfo=_UTC)
    else:
        try:
            timestamp = datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
        except ValueError:
            timestamp = datetime.now(_UTC)

    reason = (
        f"{sweep.side} sweep @ {sweep_price:.5f} → "
        f"displacement @ {entry:.5f} | "
        f"SL {stop_loss:.5f} | RR {rr}"
    )

    return Signal(
        side=sweep.side,
        entry=entry,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_pips=round(risk_pips, 2),
        reward_pips=round(reward_pips, 2),
        rr=rr,
        session=session,
        timestamp=timestamp,
        reason=reason,
    )

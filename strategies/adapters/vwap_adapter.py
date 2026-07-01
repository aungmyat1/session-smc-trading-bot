"""
VWAP Mean Reversion Adapter.

Session-scoped VWAP fade strategy for London and New York windows.
The engine looks for an exhaustion sweep away from session VWAP, then
waits for a reclaim back toward fair value before creating a trade.

Legacy compatibility:
    VWAPBreakoutAdapter is kept as an alias so older imports keep working.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from core.base_strategy import BaseStrategy
from shared.strategy_api import Signal

_PIP = {"EURUSD": 0.0001, "GBPUSD": 0.0001, "USDJPY": 0.01, "XAUUSD": 0.1}

_SESSION_HOURS = {
    "london": range(7, 10),
    "new_york": range(13, 16),
}

_MIN_BARS = 12
_MIN_SESSION_BARS = 8
_EXTREME_ATR_MULT = 1.0
_RECLAIM_ATR_MULT = 0.6
_SWEEP_BUFFER_MULT = 0.35
_TP_RR = 1.8

_DEFAULT_PARAMS = {
    "min_session_bars": _MIN_SESSION_BARS,
    "sweep_buffer_mult": _SWEEP_BUFFER_MULT,
    "extreme_atr_mult": _EXTREME_ATR_MULT,
    "reclaim_atr_mult": _RECLAIM_ATR_MULT,
    "tp_rr": _TP_RR,
}


def _session_name(hour: int) -> str:
    for name, hours in _SESSION_HOURS.items():
        if hour in hours:
            return name
    return ""


def _parse_time(value) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _calc_vwap(candles: list[dict]) -> float:
    total_pv = sum(
        ((c["high"] + c["low"] + c["close"]) / 3) * c.get("volume", 1)
        for c in candles
    )
    total_v = sum(c.get("volume", 1) for c in candles)
    return total_pv / total_v if total_v else 0.0


def _calc_atr(candles: list[dict]) -> float:
    if len(candles) < 2:
        return 0.0

    true_ranges: list[float] = []
    prev_close = candles[0]["close"]
    for candle in candles[1:]:
        high = candle["high"]
        low = candle["low"]
        true_ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
        prev_close = candle["close"]

    return sum(true_ranges) / len(true_ranges) if true_ranges else 0.0


def _session_bars(candles: list[dict], session: str) -> list[dict]:
    bars: list[dict] = []
    for candle in candles:
        ts = _parse_time(candle.get("time"))
        if ts is None:
            continue
        if _session_name(ts.astimezone(timezone.utc).hour) == session:
            bars.append(candle)
    return bars


def _strategy_params(symbol: str, config: dict | None = None) -> dict:
    cfg = config or {}
    params = cfg.get("parameters", {}) if isinstance(cfg, dict) else {}
    merged = {**_DEFAULT_PARAMS, **params.get("default", {})}
    if isinstance(params.get(symbol), dict):
        merged.update(params[symbol])
    return merged


def _mean_reversion_signal(
    session_bars: list[dict],
    symbol: str,
    session: str,
    timestamp: str,
    params: dict | None = None,
) -> Optional[Signal]:
    p = {**_DEFAULT_PARAMS, **(params or {})}
    min_session_bars = int(p["min_session_bars"])
    sweep_buffer_mult = float(p["sweep_buffer_mult"])
    extreme_atr_mult = float(p["extreme_atr_mult"])
    reclaim_atr_mult = float(p["reclaim_atr_mult"])
    tp_rr = float(p["tp_rr"])

    if len(session_bars) < min_session_bars:
        return None

    pip = _PIP.get(symbol, 0.0001)
    vwap = _calc_vwap(session_bars)
    atr = _calc_atr(session_bars)
    if vwap <= 0 or atr <= 0:
        return None

    last = session_bars[-1]
    prev = session_bars[-2]
    close = last["close"]
    high = last["high"]
    low = last["low"]
    prev_close = prev["close"]

    lookback = min(5, len(session_bars) - 1)
    prior_window = session_bars[-(lookback + 1):-1]
    rolling_high = max(c["high"] for c in prior_window)
    rolling_low = min(c["low"] for c in prior_window)
    sweep_buffer = max(pip * sweep_buffer_mult, atr * 0.1)

    distance_from_vwap = abs(close - vwap)
    distance_atr = distance_from_vwap / atr

    # Long: price sweeps below recent low, then reclaims higher toward VWAP.
    long_sweep = low < rolling_low - sweep_buffer
    long_reclaim = close > prev_close and (close - low) >= atr * reclaim_atr_mult
    long_extension = vwap - close >= atr * extreme_atr_mult
    if long_sweep and long_reclaim and long_extension and close < vwap:
        entry = close
        sl = low - 1.5 * pip
        risk = entry - sl
        if risk > 0:
            tp = min(vwap, entry + risk * tp_rr)
            reward = tp - entry
            if reward > 0:
                confidence = min(0.95, 0.62 + min(0.28, distance_atr / 6.0))
                return Signal(
                    timestamp=timestamp,
                    strategy_name="VWAPMeanReversion",
                    symbol=symbol,
                    action="BUY",
                    order_type="MARKET",
                    entry_price=entry,
                    stop_loss=round(sl, 5),
                    take_profit=round(tp, 5),
                    risk_percent=0.20,
                    confidence=round(confidence, 2),
                    metadata={
                        "session": session,
                        "vwap": round(vwap, 5),
                        "atr": round(atr, 5),
                        "distance_from_vwap": round(distance_from_vwap, 5),
                        "distance_atr": round(distance_atr, 2),
                        "risk_pips": round(risk / pip, 1),
                        "reward_pips": round(reward / pip, 1),
                        "rr": round(reward / risk, 2),
                        "reason": "vwap_mean_reversion_long",
                    },
                )

    # Short: price sweeps above recent high, then fades back toward VWAP.
    short_sweep = high > rolling_high + sweep_buffer
    short_reclaim = close < prev_close and (high - close) >= atr * reclaim_atr_mult
    short_extension = close - vwap >= atr * extreme_atr_mult
    if short_sweep and short_reclaim and short_extension and close > vwap:
        entry = close
        sl = high + 1.5 * pip
        risk = sl - entry
        if risk > 0:
            tp = max(vwap, entry - risk * tp_rr)
            reward = entry - tp
            if reward > 0:
                confidence = min(0.95, 0.62 + min(0.28, distance_atr / 6.0))
                return Signal(
                    timestamp=timestamp,
                    strategy_name="VWAPMeanReversion",
                    symbol=symbol,
                    action="SELL",
                    order_type="MARKET",
                    entry_price=entry,
                    stop_loss=round(sl, 5),
                    take_profit=round(tp, 5),
                    risk_percent=0.20,
                    confidence=round(confidence, 2),
                    metadata={
                        "session": session,
                        "vwap": round(vwap, 5),
                        "atr": round(atr, 5),
                        "distance_from_vwap": round(distance_from_vwap, 5),
                        "distance_atr": round(distance_atr, 2),
                        "risk_pips": round(risk / pip, 1),
                        "reward_pips": round(reward / pip, 1),
                        "rr": round(reward / risk, 2),
                        "reason": "vwap_mean_reversion_short",
                    },
                )

    return None


class VWAPMeanReversionAdapter(BaseStrategy):
    @property
    def name(self) -> str:
        return "VWAPMeanReversion"

    def generate_signal(self, data: dict) -> Optional[Signal]:
        """
        Args:
            data: {"symbol": str, "m15": list[dict], "spread_pips": float}
        """
        m15 = data.get("m15", [])
        symbol = data.get("symbol", "")
        params = _strategy_params(symbol, data.get("config"))

        if len(m15) < _MIN_BARS:
            return None

        latest_ts = None
        latest_ts_str = ""
        for candle in reversed(m15):
            latest_ts = _parse_time(candle.get("time"))
            if latest_ts is not None:
                latest_ts_str = candle.get("time") if isinstance(candle.get("time"), str) else latest_ts.astimezone(timezone.utc).isoformat()
                break

        if latest_ts is None:
            latest_ts = datetime.now(timezone.utc)
            latest_ts_str = latest_ts.isoformat()

        session = _session_name(latest_ts.astimezone(timezone.utc).hour)
        if not session:
            return None

        session_bars = _session_bars(m15, session)
        if len(session_bars) < int(params["min_session_bars"]):
            return None

        signal = _mean_reversion_signal(session_bars, symbol, session, latest_ts_str, params)
        if signal is not None:
            return signal

        # Fallback: if session-scoped bars are thin, use the trailing window.
        trailing = m15[-max(int(params["min_session_bars"]), 12):]
        trailing_session = _mean_reversion_signal(trailing, symbol, session, latest_ts_str, params)
        return trailing_session


class VWAPBreakoutAdapter(VWAPMeanReversionAdapter):
    @property
    def name(self) -> str:
        return "VWAPBreakout"

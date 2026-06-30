"""
VWAP Breakout Adapter — session VWAP cross with volume confirmation.

Pure-Python, no external dependencies. Fires only during active sessions
(London 07-10 UTC, NY 13-16 UTC). One signal per symbol per session.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from core.base_strategy import BaseStrategy
from core.signal import Signal

_LONDON_HOURS = range(7, 10)
_NY_HOURS = range(13, 16)
_MIN_BARS = 20
_MIN_VOL_MULT = 1.3  # current volume must be ≥ 1.3× session average


def _session_name(hour: int) -> str:
    if hour in _LONDON_HOURS:
        return "london"
    if hour in _NY_HOURS:
        return "new_york"
    return ""


def _calc_vwap(candles: list[dict]) -> float:
    total_pv = sum(
        ((c["high"] + c["low"] + c["close"]) / 3) * c.get("volume", 1) for c in candles
    )
    total_v = sum(c.get("volume", 1) for c in candles)
    return total_pv / total_v if total_v else 0.0


class VWAPBreakoutAdapter(BaseStrategy):

    @property
    def name(self) -> str:
        return "VWAPBreakout"

    def generate_signal(self, data: dict) -> Optional[Signal]:
        """
        Args:
            data: {"symbol": str, "m15": list[dict], "spread_pips": float}
        """
        m15 = data.get("m15", [])
        symbol = data.get("symbol", "")
        spread = data.get("spread_pips", 0.0)

        if len(m15) < _MIN_BARS:
            return None

        now = datetime.now(timezone.utc)
        sess = _session_name(now.hour)
        if not sess:
            return None

        # Session candles: only current session
        session_bars = [
            c
            for c in m15
            if isinstance(c.get("time"), datetime)
            and _session_name(c["time"].hour) == sess
        ] or m15[-_MIN_BARS:]

        if len(session_bars) < 5:
            return None

        vwap = _calc_vwap(session_bars)
        last = session_bars[-1]
        prev = session_bars[-2]
        close = last["close"]
        high = last["high"]
        low = last["low"]
        vol = last.get("volume", 0)
        avg_vol = sum(c.get("volume", 0) for c in session_bars[:-1]) / max(
            len(session_bars) - 1, 1
        )

        if vwap == 0 or avg_vol == 0:
            return None

        # Volume confirmation
        if vol < avg_vol * _MIN_VOL_MULT:
            return None

        pip = 0.0001

        # Bullish cross: prev close < vwap, current close > vwap
        if prev["close"] < vwap < close:
            sl = low - 5 * pip
            tp = close + (close - sl) * 1.5
            sl_pips = (close - sl) / pip
            confidence = min(1.0, (vol / avg_vol - 1.0))
            return Signal(
                timestamp=now.isoformat(),
                strategy_name=self.name,
                symbol=symbol,
                action="BUY",
                order_type="MARKET",
                entry_price=close,
                stop_loss=round(sl, 5),
                take_profit=round(tp, 5),
                risk_percent=0.10,  # shadow tier-3: 0.10% per strategy_portfolio.yaml
                confidence=round(confidence, 2),
                metadata={
                    "session": sess,
                    "vwap": round(vwap, 5),
                    "vol_ratio": round(vol / avg_vol, 2),
                    "risk_pips": round(sl_pips, 1),
                    "reason": "vwap_bull_cross",
                },
            )

        # Bearish cross: prev close > vwap, current close < vwap
        if prev["close"] > vwap > close:
            sl = high + 5 * pip
            tp = close - (sl - close) * 1.5
            sl_pips = (sl - close) / pip
            confidence = min(1.0, (vol / avg_vol - 1.0))
            return Signal(
                timestamp=now.isoformat(),
                strategy_name=self.name,
                symbol=symbol,
                action="SELL",
                order_type="MARKET",
                entry_price=close,
                stop_loss=round(sl, 5),
                take_profit=round(tp, 5),
                risk_percent=0.10,  # shadow tier-3: 0.10% per strategy_portfolio.yaml
                confidence=round(confidence, 2),
                metadata={
                    "session": sess,
                    "vwap": round(vwap, 5),
                    "vol_ratio": round(vol / avg_vol, 2),
                    "risk_pips": round(sl_pips, 1),
                    "reason": "vwap_bear_cross",
                },
            )

        return None

"""
S1 — Market Feed.

Thin adapter over the existing data.forex_data.ForexData and
data.session_filter utilities. Does NOT open new broker connections —
accepts an already-connected ForexData instance.

Public API:
    MarketFeed(forex_data)
        async get_candles(symbol, timeframe, count) -> list[dict]
        async get_current_spread(symbol) -> float
        get_session() -> str | None
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from data.session_filter import get_active_session

if TYPE_CHECKING:
    from data.forex_data import ForexData

# Timeframe aliases → MetaAPI format
_TF_MAP = {
    "M5": "5m",
    "m5": "5m",
    "5m": "5m",
    "M15": "15m",
    "m15": "15m",
    "15m": "15m",
    "H1": "1h",
    "h1": "1h",
    "1h": "1h",
    "H4": "4h",
    "h4": "4h",
    "4h": "4h",
    "M1": "1m",
    "m1": "1m",
    "1m": "1m",
}


class MarketFeed:
    """
    Wraps an existing ForexData instance. No broker connection logic here.
    Pass a connected ForexData object from the main bot or test harness.
    """

    def __init__(self, forex_data: "ForexData") -> None:
        self._fd = forex_data

    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        count: int = 200,
    ) -> list[dict]:
        """
        Fetch OHLCV candles.

        timeframe: M5 | M15 | H1 | H4 (case-insensitive, with or without prefix)
        Returns list of dicts: {time, open, high, low, close, volume}
        """
        tf = _TF_MAP.get(timeframe, timeframe)
        return await self._fd.get_candles(symbol, tf, count)

    async def get_current_spread(self, symbol: str) -> float:
        """Return current spread in pips."""
        price = await self._fd.get_current_price(symbol)
        return float(price.get("spread_pips", 0.0))

    def get_session(self, dt: datetime | None = None) -> str | None:
        """
        Return the active session name using the existing session_filter.
        Returns 'london' | 'new_york' | 'asian' | None
        """
        return get_active_session(dt or datetime.now(timezone.utc))

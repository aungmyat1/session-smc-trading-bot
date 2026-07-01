"""
Forex data fetcher — wraps MetaAPI RPC calls for OHLCV and tick data.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class ForexData:
    """Thin wrapper around an active MT5Executor to pull market data."""

    def __init__(self, executor):
        self._ex = executor

    async def get_current_price(self, symbol: str) -> dict:
        """Return {bid, ask, spread_pips} for the symbol."""
        price = await self._ex.get_symbol_price(symbol)
        bid = price.get("bid", 0.0)
        ask = price.get("ask", 0.0)
        spread = round((ask - bid) / 0.0001, 1)
        return {"bid": bid, "ask": ask, "spread_pips": spread, "time": price.get("time")}

    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        count: int = 200,
        end_time: Optional[datetime] = None,
    ) -> list[dict]:
        """
        Fetch OHLCV candles from MetaAPI.

        timeframe: '1m' | '5m' | '15m' | '1h' | '4h' | '1d'
        Returns list of dicts with keys: time, open, high, low, close, volume
        """
        end_time = end_time or datetime.now(timezone.utc)
        account = getattr(self._ex, "_account", None)
        connection = getattr(self._ex, "_connection", None)

        if account is not None and hasattr(account, "get_historical_candles"):
            candles = await account.get_historical_candles(symbol, timeframe, end_time, count)
        elif connection is not None and hasattr(connection, "get_historical_candles"):
            candles = await connection.get_historical_candles(symbol, timeframe, end_time, count)
        elif connection is not None and hasattr(connection, "get_candles"):
            candles = await connection.get_candles(symbol, timeframe, end_time, count)
        else:
            raise AttributeError("No MetaAPI historical candle method available")

        result = []
        for c in (candles or []):
            result.append({
                "time": c.get("time"),
                "open": c.get("open"),
                "high": c.get("high"),
                "low": c.get("low"),
                "close": c.get("close"),
                "volume": c.get("tickVolume", 0),
            })
        return result

    async def get_multi_tf_candles(self, symbol: str, count: int = 200) -> dict:
        """Convenience: fetch 4H, 1H, and 15M candles in parallel."""
        import asyncio
        results = await asyncio.gather(
            self.get_candles(symbol, "4h", count),
            self.get_candles(symbol, "1h", count),
            self.get_candles(symbol, "15m", count),
            return_exceptions=True,
        )
        candles = {}
        for tf, res in zip(["4h", "1h", "15m"], results):
            if isinstance(res, Exception):
                logger.warning("Failed to fetch %s %s: %s", symbol, tf, res)
                candles[tf] = []
            else:
                candles[tf] = res
        return candles

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_TF_MAP = {
    "M1": "1m",
    "M5": "5m",
    "M15": "15m",
    "H1": "1h",
    "H4": "4h",
    "D1": "1d",
    "m1": "1m",
    "m5": "5m",
    "m15": "15m",
    "h1": "1h",
    "h4": "4h",
    "d1": "1d",
}


class MarketDataProvider(ABC):
    @abstractmethod
    async def get_candles(self, symbol: str, timeframe: str, limit: int) -> list[dict[str, Any]]:
        raise NotImplementedError


class MetaApiMarketDataProvider(MarketDataProvider):
    def __init__(
        self,
        *,
        account_getter: Callable[[], Any],
        connection_getter: Callable[[], Any],
        reconnect_callback: Callable[[], Awaitable[Any]] | None = None,
        retries: int = 3,
        retry_delay_s: float = 2.0,
    ) -> None:
        self._account_getter = account_getter
        self._connection_getter = connection_getter
        self._reconnect_callback = reconnect_callback
        self._retries = max(1, retries)
        self._retry_delay_s = max(0.0, retry_delay_s)
        self._metrics = {
            "requests": 0,
            "successes": 0,
            "retries": 0,
            "errors": 0,
            "empty_responses": 0,
            "last_error": "",
            "last_success_at": "",
        }

    @property
    def metrics(self) -> dict[str, Any]:
        return dict(self._metrics)

    async def get_candles(self, symbol: str, timeframe: str, limit: int) -> list[dict[str, Any]]:
        normalized_tf = _TF_MAP.get(timeframe, timeframe)
        end_time = datetime.now(timezone.utc)
        self._metrics["requests"] += 1

        last_error: Exception | None = None
        for attempt in range(1, self._retries + 1):
            try:
                raw = await self._fetch_raw(symbol, normalized_tf, end_time, limit)
                candles = [self._normalize_candle(item) for item in (raw or []) if isinstance(item, dict)]
                if not candles:
                    self._metrics["empty_responses"] += 1
                    logger.warning(
                        "Market data returned no candles for %s %s (attempt %d/%d)",
                        symbol, normalized_tf, attempt, self._retries,
                    )
                self._metrics["successes"] += 1
                self._metrics["last_success_at"] = datetime.now(timezone.utc).isoformat()
                return candles
            except Exception as exc:
                last_error = exc
                self._metrics["errors"] += 1
                self._metrics["last_error"] = str(exc)
                logger.warning(
                    "Market data fetch failed for %s %s (attempt %d/%d): %s",
                    symbol, normalized_tf, attempt, self._retries, exc,
                )
                if attempt >= self._retries:
                    break
                self._metrics["retries"] += 1
                # Only trigger reconnect on the final retry — earlier attempts may
                # recover on their own (transient socket hiccup). Reconnecting on
                # every attempt causes redundant disconnect/connect cycles.
                if attempt == self._retries - 1 and self._reconnect_callback is not None:
                    try:
                        await self._reconnect_callback()
                    except Exception as reconnect_exc:
                        logger.warning("Market data reconnect attempt failed: %s", reconnect_exc)
                # Exponential backoff: 2s, 4s, … capped at 10s
                delay = min(self._retry_delay_s * (2 ** (attempt - 1)), 10.0)
                if delay:
                    await asyncio.sleep(delay)

        if last_error is not None:
            raise last_error
        return []

    async def _fetch_raw(
        self,
        symbol: str,
        timeframe: str,
        end_time: datetime,
        limit: int,
    ) -> list[dict[str, Any]]:
        account = self._account_getter()
        connection = self._connection_getter()
        if account is None and connection is None:
            raise RuntimeError("MetaAPI market data unavailable: no account or connection")

        if account is not None and hasattr(account, "get_historical_candles"):
            return await account.get_historical_candles(symbol, timeframe, end_time, limit)

        if connection is not None and hasattr(connection, "get_historical_candles"):
            return await connection.get_historical_candles(symbol, timeframe, end_time, limit)

        if connection is not None and hasattr(connection, "get_candles"):
            return await connection.get_candles(symbol, timeframe, end_time, limit)

        raise AttributeError("MetaAPI historical candle API not available on account or connection")

    @staticmethod
    def _normalize_candle(raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "time": raw.get("time"),
            "open": raw.get("open"),
            "high": raw.get("high"),
            "low": raw.get("low"),
            "close": raw.get("close"),
            "volume": raw.get("tickVolume", raw.get("volume", 0)),
        }


_MT5_TIMEFRAME_ATTR = {
    "1m": "TIMEFRAME_M1",
    "5m": "TIMEFRAME_M5",
    "15m": "TIMEFRAME_M15",
    "1h": "TIMEFRAME_H1",
    "4h": "TIMEFRAME_H4",
    "1d": "TIMEFRAME_D1",
}


class MT5LinuxMarketDataProvider(MarketDataProvider):
    """Candle source backed by the mt5linux bridge (ADR-0011)."""

    def __init__(self, *, mt5_getter: Callable[[], Any]) -> None:
        self._mt5_getter = mt5_getter

    async def get_candles(self, symbol: str, timeframe: str, limit: int) -> list[dict[str, Any]]:
        import asyncio

        normalized_tf = _TF_MAP.get(timeframe, timeframe)
        mt5 = self._mt5_getter()
        if mt5 is None:
            raise RuntimeError("mt5linux market data unavailable: not connected")
        tf_attr = _MT5_TIMEFRAME_ATTR.get(normalized_tf)
        if tf_attr is None:
            raise ValueError(f"Unsupported timeframe for mt5linux: {timeframe}")
        tf_const = getattr(mt5, tf_attr)

        def _fetch() -> list[dict[str, Any]] | None:
            rates = mt5.copy_rates_from_pos(symbol, tf_const, 0, limit)
            return rates

        rates = await asyncio.to_thread(_fetch)
        if rates is None:
            raise RuntimeError(f"copy_rates_from_pos({symbol}) returned None: {mt5.last_error()}")
        return [
            {
                "time": datetime.fromtimestamp(r["time"], tz=timezone.utc).isoformat(),
                "open": r["open"],
                "high": r["high"],
                "low": r["low"],
                "close": r["close"],
                "volume": r["tick_volume"],
            }
            for r in rates
        ]


class MockMarketDataProvider(MarketDataProvider):
    def __init__(self, candles_by_key: dict[tuple[str, str], list[dict[str, Any]]]) -> None:
        self._candles_by_key = {
            (symbol.upper(), _TF_MAP.get(timeframe, timeframe)): list(rows)
            for (symbol, timeframe), rows in candles_by_key.items()
        }

    async def get_candles(self, symbol: str, timeframe: str, limit: int) -> list[dict[str, Any]]:
        rows = self._candles_by_key.get((symbol.upper(), _TF_MAP.get(timeframe, timeframe)), [])
        return list(rows[-limit:])


class ReplayMarketDataProvider(MarketDataProvider):
    def __init__(self, candles_by_key: dict[tuple[str, str], list[dict[str, Any]]]) -> None:
        self._mock = MockMarketDataProvider(candles_by_key)

    async def get_candles(self, symbol: str, timeframe: str, limit: int) -> list[dict[str, Any]]:
        return await self._mock.get_candles(symbol, timeframe, limit)

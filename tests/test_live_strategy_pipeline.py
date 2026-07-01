from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from execution.market_data import MockMarketDataProvider
from strategies.adapters.st_a2_adapter import ST2Adapter
from strategy.session_liquidity.session_strategy import run_strategy

_UTC = timezone.utc


def _bar(t: datetime, high: float, low: float, open_: float | None = None, close: float | None = None) -> dict:
    mid = round((high + low) / 2, 6)
    return {
        "time": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "open": open_ if open_ is not None else mid,
        "high": high,
        "low": low,
        "close": close if close is not None else mid,
        "volume": 100,
    }


def _asian_bars(base_high: float, base_low: float, trade_date: datetime) -> list[dict]:
    start = (trade_date - timedelta(days=1)).replace(hour=23, minute=0, second=0, microsecond=0)
    return [_bar(start + timedelta(minutes=15 * i), base_high, base_low) for i in range(32)]


def _h4_bullish() -> list[dict]:
    highs = [1, 2, 5, 2, 1, 2, 3, 3, 2, 1, 8, 2, 1]
    lows = [0.5, 1, 0.8, 0.5, 0.2, 0.8, 0.5, 0.8, 0.5, 0.3, 1.5, 0.5, 0.2]
    base = datetime(2024, 1, 12, 0, 0, tzinfo=_UTC)
    return [_bar(base + timedelta(hours=4 * i), float(h), float(l)) for i, (h, l) in enumerate(zip(highs, lows))]


def _h1_context(base_price: float, trade_date: datetime) -> list[dict]:
    start = trade_date.replace(hour=0, minute=0, second=0, microsecond=0)
    return [
        _bar(
            start + timedelta(hours=i),
            high=base_price + 0.0020 + (i * 0.0001),
            low=base_price - 0.0020 + (i * 0.0001),
        )
        for i in range(48)
    ]


def _m15_signal_fixture(symbol: str) -> tuple[list[dict], list[dict], list[dict]]:
    trade_date = datetime(2024, 1, 15, tzinfo=_UTC)
    if symbol == "EURUSD":
        high, low = 1.0750, 1.0700
        displacement_high, displacement_low, displacement_close = 1.0800, 1.0695, 1.0790
    elif symbol == "GBPUSD":
        high, low = 1.2750, 1.2700
        displacement_high, displacement_low, displacement_close = 1.2810, 1.2695, 1.2800
    else:
        high, low = 2350.0, 2345.0
        displacement_high, displacement_low, displacement_close = 2358.0, 2344.5, 2357.2

    m15 = _asian_bars(high, low, trade_date)
    m15.append(_bar(trade_date.replace(hour=7, minute=0), high=high - 0.0010, low=low + 0.0010, close=high - 0.0020))
    m15.append(_bar(trade_date.replace(hour=7, minute=15), high=high - 0.0002, low=low - 0.0018, open_=low + 0.0025, close=low + 0.0020))
    m15.append(
        _bar(
            trade_date.replace(hour=7, minute=30),
            high=displacement_high,
            low=displacement_low,
            open_=low,
            close=displacement_close,
        )
    )
    for idx in range(17):
        stamp = trade_date.replace(hour=7, minute=45) + timedelta(minutes=15 * idx)
        m15.append(
            _bar(
                stamp,
                high=displacement_close + 0.0008,
                low=displacement_close - 0.0008,
                close=displacement_close,
            )
        )
    return m15, _h1_context((high + low) / 2, trade_date), _h4_bullish()


@pytest.mark.asyncio
async def test_live_strategy_pipeline_passes_for_core_watchlist():
    symbols = ["EURUSD", "GBPUSD", "XAUUSD"]
    candles_by_key: dict[tuple[str, str], list[dict]] = {}
    symbol_inputs: dict[str, dict[str, list[dict]]] = {}

    for symbol in symbols:
        m15, h1, h4 = _m15_signal_fixture(symbol)
        symbol_inputs[symbol] = {"M15": m15, "H1": h1, "H4": h4}
        candles_by_key[(symbol, "15m")] = m15
        candles_by_key[(symbol, "1h")] = h1
        candles_by_key[(symbol, "4h")] = h4

    provider = MockMarketDataProvider(candles_by_key)
    adapter = ST2Adapter()

    market_data_pass = True
    feature_engine_pass = True
    smc_detection_pass = True
    signal_engine_pass = True

    for symbol in symbols:
        m15 = await provider.get_candles(symbol, "M15", 200)
        h1 = await provider.get_candles(symbol, "H1", 120)
        h4 = await provider.get_candles(symbol, "H4", 100)

        market_data_pass &= bool(m15) and bool(h1) and bool(h4)
        feature_engine_pass &= len(m15) >= 35 and len(h1) >= 24 and len(h4) >= 9

        signals, events = run_strategy(m15, h4, symbol, debug=True)
        smc_detection_pass &= any(event["event"] == "SWEEP" for event in events) and any(
            event["event"] == "SIGNAL" for event in events
        )

        signal = adapter.generate_signal({"symbol": symbol, "m15": m15, "h4": h4})
        signal_engine_pass &= signal is not None

    summary = {
        "Market Data": market_data_pass,
        "Feature Engine": feature_engine_pass,
        "SMC Detection": smc_detection_pass,
        "Signal Engine": signal_engine_pass,
    }

    assert summary == {
        "Market Data": True,
        "Feature Engine": True,
        "SMC Detection": True,
        "Signal Engine": True,
    }

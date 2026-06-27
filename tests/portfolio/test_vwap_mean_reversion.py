"""Tests for the VWAP mean-reversion adapter."""

from __future__ import annotations

import pytest

from strategies.adapters.vwap_adapter import (
    VWAPBreakoutAdapter,
    VWAPMeanReversionAdapter,
)


def _ts(hour: int, minute: int = 0) -> str:
    return f"2026-06-24T{hour:02d}:{minute:02d}:00+00:00"


def _candle(hour: int, minute: int, open_: float, high: float, low: float, close: float,
            volume: int = 1000) -> dict:
    return {
        "time": _ts(hour, minute),
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


def _flat_session_bars(base: float = 1.1000) -> list[dict]:
    bars = []
    for idx in range(18):
        hour = 7 + (idx // 4)
        minute = (idx % 4) * 15
        bars.append(_candle(hour, minute, base, base + 0.0008, base - 0.0008, base))
    return bars


def _long_setup() -> list[dict]:
    bars = _flat_session_bars()
    bars.extend(
        [
            _candle(8, 45, 1.0996, 1.1001, 1.0956, 1.0959),
            _candle(9, 0, 1.0959, 1.0990, 1.0952, 1.0972),
        ]
    )
    return bars


def _short_setup() -> list[dict]:
    bars = _flat_session_bars()
    bars.extend(
        [
            _candle(8, 45, 1.1004, 1.1046, 1.1000, 1.1044),
            _candle(9, 0, 1.1044, 1.1050, 1.1010, 1.1026),
        ]
    )
    return bars


class TestVWAPMeanReversionAdapter:
    def test_long_signal_on_sweep_and_reclaim(self):
        adapter = VWAPMeanReversionAdapter()
        sig = adapter.generate_signal({"symbol": "EURUSD", "m15": _long_setup()})
        assert sig is not None
        assert sig.strategy_name == "VWAPMeanReversion"
        assert sig.action == "BUY"
        assert sig.metadata["reason"] == "vwap_mean_reversion_long"

    def test_short_signal_on_sweep_and_reclaim(self):
        adapter = VWAPMeanReversionAdapter()
        sig = adapter.generate_signal({"symbol": "EURUSD", "m15": _short_setup()})
        assert sig is not None
        assert sig.action == "SELL"
        assert sig.strategy_name == "VWAPMeanReversion"

    def test_tp_and_sl_are_valid_geometry(self):
        adapter = VWAPMeanReversionAdapter()
        sig = adapter.generate_signal({"symbol": "EURUSD", "m15": _long_setup()})
        assert sig is not None
        assert sig.stop_loss < sig.entry_price < sig.take_profit
        risk = sig.entry_price - sig.stop_loss
        reward = sig.take_profit - sig.entry_price
        assert reward > 0
        assert reward == pytest.approx(risk * sig.metadata["rr"], rel=0.05)

    def test_legacy_alias_still_works(self):
        adapter = VWAPBreakoutAdapter()
        sig = adapter.generate_signal({"symbol": "EURUSD", "m15": _long_setup()})
        assert sig is not None
        assert sig.strategy_name == "VWAPMeanReversion"

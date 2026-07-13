"""
Unit tests for strategies/smc_lss/liquidity.py — synthetic candles only.

Covers: bullish/bearish sweep detection, no-breach rejection, penetration
threshold gating, and the no-lookahead guarantee (a candle's own high/low
is never part of its own swing reference window).
"""

from __future__ import annotations

import pytest

from strategies.smc_lss.liquidity import (
    detect_liquidity_sweep,
    prior_swing_high,
    prior_swing_low,
)


def _bar(o, h, l, c, ts="2024-01-01T00:00:00Z"):
    return {"timestamp": ts, "open": o, "high": h, "low": l, "close": c}


def _flat_history(n, low, high):
    return [_bar(low + 0.0002, high, low, low + 0.0003) for _ in range(n)]


class TestPriorSwingLevels:
    def test_insufficient_history_returns_none(self):
        candles = _flat_history(5, 1.0990, 1.1010)
        assert prior_swing_low(candles, 5, lookback=10) is None
        assert prior_swing_high(candles, 5, lookback=10) is None

    def test_excludes_current_candle_from_its_own_window(self):
        candles = _flat_history(10, 1.0990, 1.1010)
        # candle[10] has an extreme low that must NOT feed its own swing_low
        candles.append(_bar(1.1000, 1.1005, 0.5000, 1.1000))
        assert prior_swing_low(candles, 10, lookback=10) == pytest.approx(1.0990)
        assert prior_swing_high(candles, 10, lookback=10) == pytest.approx(1.1010)


class TestDetectLiquiditySweep:
    def test_bullish_sweep_detected(self):
        candles = _flat_history(10, 1.0990, 1.1010)
        candles.append(_bar(1.1000, 1.1005, 1.0985, 1.1002))  # breach + close back above
        event = detect_liquidity_sweep(
            candles, 10, symbol="EURUSD", atr=0.0010,
            swing_lookback=10, sweep_atr_threshold=0.25,
        )
        assert event is not None
        assert event.direction == "long"
        assert event.symbol == "EURUSD"
        assert event.swept_level == pytest.approx(1.0990)
        assert event.penetration == pytest.approx(0.0005)

    def test_bearish_sweep_detected(self):
        candles = _flat_history(10, 1.0990, 1.1010)
        candles.append(_bar(1.1000, 1.1025, 1.0995, 1.1002))  # breach above + close back below
        event = detect_liquidity_sweep(
            candles, 10, symbol="GBPUSD", atr=0.0010,
            swing_lookback=10, sweep_atr_threshold=0.25,
        )
        assert event is not None
        assert event.direction == "short"
        assert event.swept_level == pytest.approx(1.1010)
        assert event.penetration == pytest.approx(0.0015)

    def test_no_breach_returns_none(self):
        candles = _flat_history(10, 1.0990, 1.1010)
        candles.append(_bar(1.1000, 1.1005, 1.0995, 1.1000))  # stays inside range
        event = detect_liquidity_sweep(candles, 10, symbol="EURUSD", atr=0.0010)
        assert event is None

    def test_breach_without_close_back_inside_returns_none(self):
        candles = _flat_history(10, 1.0990, 1.1010)
        candles.append(_bar(1.0992, 1.0993, 1.0985, 1.0988))  # breach but closes outside
        event = detect_liquidity_sweep(candles, 10, symbol="EURUSD", atr=0.0010)
        assert event is None

    def test_penetration_below_atr_threshold_returns_none(self):
        candles = _flat_history(10, 1.0990, 1.1010)
        candles.append(_bar(1.1000, 1.1005, 1.0989, 1.1002))  # tiny 0.0001 penetration
        event = detect_liquidity_sweep(
            candles, 10, symbol="EURUSD", atr=0.0010,
            swing_lookback=10, sweep_atr_threshold=0.25,  # threshold = 0.00025
        )
        assert event is None

    def test_atr_none_or_zero_returns_none(self):
        candles = _flat_history(10, 1.0990, 1.1010)
        candles.append(_bar(1.1000, 1.1005, 1.0985, 1.1002))
        assert detect_liquidity_sweep(candles, 10, symbol="EURUSD", atr=None) is None
        assert detect_liquidity_sweep(candles, 10, symbol="EURUSD", atr=0.0) is None

    def test_no_lookahead_extreme_beyond_current_index_ignored(self):
        """A future candle's extreme low must never trigger a sweep for an
        earlier index — detect_liquidity_sweep only ever looks at
        candles[index] and candles[index-lookback:index]."""
        candles = _flat_history(10, 1.0990, 1.1010)
        candles.append(_bar(1.1000, 1.1005, 1.0995, 1.1000))  # index10: no sweep
        candles.append(_bar(1.1000, 1.1005, 0.5000, 1.1000))  # index11: extreme low, future bar
        event = detect_liquidity_sweep(candles, 10, symbol="EURUSD", atr=0.0010)
        assert event is None

"""
Unit tests for strategies/smc_lss/structure.py — synthetic candles only.

Covers: bullish/bearish CHoCH detection, insufficient-history rejection,
inducement window logic, and the no-lookahead guarantee (both comparison
windows are strictly before the evaluated candle).
"""

from __future__ import annotations

import pytest

from strategies.smc_lss.structure import apply_inducement, detect_choch


def _bar(o, h, l, c, ts="2024-01-01T00:00:00Z"):
    return {"timestamp": ts, "open": o, "high": h, "low": l, "close": c}


LOOKBACK = 3


def _bullish_choch_candles():
    prior = [_bar(1.0995, 1.1010, 1.0990, 1.1000) for _ in range(3)]
    recent = [
        _bar(1.0995, 1.1005, 1.0985, 1.0995),
        _bar(1.0990, 1.1005, 1.0988, 1.0995),
        _bar(1.0992, 1.1005, 1.0990, 1.0995),
    ]
    confirm = _bar(1.1000, 1.1015, 1.0998, 1.1010)  # close > recent_high(1.1005)
    return prior + recent + [confirm]


def _bearish_choch_candles():
    prior = [_bar(1.0995, 1.1010, 1.0990, 1.1000) for _ in range(3)]
    recent = [
        _bar(1.1005, 1.1015, 1.0995, 1.1005),
        _bar(1.1005, 1.1013, 1.0995, 1.1005),
        _bar(1.1005, 1.1012, 1.0995, 1.1005),
    ]
    confirm = _bar(1.1000, 1.1002, 1.0985, 1.0990)  # close < recent_low(1.0995)
    return prior + recent + [confirm]


class TestDetectCHoCH:
    def test_bullish_choch_detected(self):
        candles = _bullish_choch_candles()
        event = detect_choch(candles, 6, symbol="EURUSD", structure_lookback=LOOKBACK)
        assert event is not None
        assert event.direction == "long"
        assert event.broken_level == pytest.approx(1.1005)
        assert event.confirmation_close == pytest.approx(1.1010)

    def test_bearish_choch_detected(self):
        candles = _bearish_choch_candles()
        event = detect_choch(candles, 6, symbol="EURUSD", structure_lookback=LOOKBACK)
        assert event is not None
        assert event.direction == "short"
        assert event.broken_level == pytest.approx(1.0995)
        assert event.confirmation_close == pytest.approx(1.0990)

    def test_insufficient_history_returns_none(self):
        candles = _bullish_choch_candles()[:5]  # index 4 < 2*lookback(6)
        assert detect_choch(candles, 4, symbol="EURUSD", structure_lookback=LOOKBACK) is None

    def test_no_structure_break_returns_none(self):
        flat = [_bar(1.0995, 1.1005, 1.0990, 1.1000) for _ in range(7)]
        assert detect_choch(flat, 6, symbol="EURUSD", structure_lookback=LOOKBACK) is None

    def test_no_lookahead_future_candle_ignored(self):
        """A stronger future close must not retroactively change the
        verdict at an earlier index."""
        candles = _bullish_choch_candles()
        base_event = detect_choch(candles, 6, symbol="EURUSD", structure_lookback=LOOKBACK)
        candles.append(_bar(1.1010, 1.1200, 1.1005, 1.1190))  # extreme future bar
        same_event = detect_choch(candles, 6, symbol="EURUSD", structure_lookback=LOOKBACK)
        assert same_event == base_event


class TestApplyInducement:
    def _choch_event(self):
        candles = _bullish_choch_candles()
        return detect_choch(candles, 6, symbol="EURUSD", structure_lookback=LOOKBACK)

    def test_sweep_within_window_confirms_inducement(self):
        event = self._choch_event()
        annotated = apply_inducement(event, sweep_indices=[4, 5], choch_index=6, inducement_window=3)
        assert annotated.inducement is True
        assert annotated.inducement_sweep_index == 5  # most recent qualifying sweep

    def test_sweep_outside_window_rejects_inducement(self):
        event = self._choch_event()
        annotated = apply_inducement(event, sweep_indices=[1], choch_index=6, inducement_window=3)
        assert annotated.inducement is False
        assert annotated.inducement_sweep_index is None

    def test_no_sweeps_rejects_inducement(self):
        event = self._choch_event()
        annotated = apply_inducement(event, sweep_indices=[], choch_index=6, inducement_window=3)
        assert annotated.inducement is False

    def test_original_event_fields_preserved(self):
        event = self._choch_event()
        annotated = apply_inducement(event, sweep_indices=[5], choch_index=6, inducement_window=3)
        assert annotated.direction == event.direction
        assert annotated.broken_level == event.broken_level
        assert annotated.confirmation_close == event.confirmation_close

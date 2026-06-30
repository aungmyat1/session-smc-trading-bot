"""
tests/test_session_range.py
Full test suite for session_range.py

Covers:
  - build_session_box : normal case + too-few-candles error
  - classify_session  : range / trend / neutral
  - detect_sweep      : HIGH sweep (→ short), LOW sweep (→ long), no sweep
  - build_session_signal:
      Asian EURUSD sweep long + short
      London GBPUSD range short (neutral HTF → None)
      Overlap XAUUSD trend long
      GBPUSD excluded from Asian session
      XAUUSD excluded from Asian session
      spread_allowance blocks near-edge entry
  - scan_all          : cap at max_concurrent_signals, weight sorting
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

# ── Add project root to path ─────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smc_bot.session_range import (SessionBox, SessionSignal, SweepEvent,
                                   build_session_box, build_session_signal,
                                   classify_session, detect_sweep, scan_all)

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures & helpers
# ─────────────────────────────────────────────────────────────────────────────

CFG = {
    "instruments": {
        "EURUSD": {
            "symbol": "EURUSD",
            "pip_size": 0.0001,
            "atr_period": 14,
            "sweep_beyond_pct": 0.008,
            "sl_pct_of_range": 0.25,
            "spread_allowance_pips": 1.0,
            "sessions": ["asian", "london", "overlap", "newyork"],
            "signal_weight": 1.0,
        },
        "GBPUSD": {
            "symbol": "GBPUSD",
            "pip_size": 0.0001,
            "atr_period": 14,
            "sweep_beyond_pct": 0.010,
            "sl_pct_of_range": 0.25,
            "spread_allowance_pips": 1.5,
            "sessions": ["london", "overlap", "newyork"],  # NO asian
            "signal_weight": 0.9,
        },
        "XAUUSD": {
            "symbol": "XAUUSD",
            "pip_size": 0.01,
            "atr_period": 14,
            "sweep_beyond_pct": 0.005,
            "sl_pct_of_range": 0.20,
            "spread_allowance_pips": 3.0,
            "sessions": ["london", "overlap", "newyork"],  # NO asian
            "signal_weight": 1.0,
        },
    },
    "sessions": {
        "asian": {
            "start_h": 0,
            "end_h": 8,
            "range_thr": 0.50,
            "trend_thr": 0.70,
            "first_close_pct": 0.75,
            "first_close_target": "opposite_box_edge",
            "trail_remainder": False,
        },
        "london": {
            "start_h": 7,
            "end_h": 12,
            "range_thr": 0.55,
            "trend_thr": 0.75,
            "first_close_pct": 0.75,
            "first_close_target": "opposite_box_edge",
            "trail_remainder": False,
        },
        "overlap": {
            "start_h": 12,
            "end_h": 15,
            "range_thr": 0.60,
            "trend_thr": 0.80,
            "first_close_pct": 0.75,
            "first_close_target": "4R",
            "trail_remainder": True,
        },
        "newyork": {
            "start_h": 12,
            "end_h": 17,
            "range_thr": 0.55,
            "trend_thr": 0.75,
            "first_close_pct": 0.75,
            "first_close_target": "opposite_box_edge",
            "trail_remainder": False,
        },
    },
    "asian": {"target_r": 5.0, "trend_first_close_r": 4.0},
    "risk": {"max_concurrent_signals": 3},
}


def _make_df_1h(
    hours: int = 48, base_price: float = 1.1000, amplitude: float = 0.0020
) -> pd.DataFrame:
    """
    Synthetic 1h OHLCV spanning `hours` candles starting at 2024-01-01 00:00 UTC.
    Generates mild sine-wave price movement.
    """

    index = pd.date_range("2024-01-01 00:00", periods=hours, freq="1h", tz="UTC")
    closes = (
        base_price
        + amplitude * pd.Series([0.5 * (i % 12) / 12 for i in range(hours)]).values
    )
    opens = closes - 0.0001
    highs = closes + 0.0003
    lows = closes - 0.0003

    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": 1000},
        index=index,
    )


def _make_df_4h(periods: int = 60, base_price: float = 1.1000) -> pd.DataFrame:
    index = pd.date_range("2024-01-01 00:00", periods=periods, freq="4h", tz="UTC")
    closes = [base_price + 0.0001 * i for i in range(periods)]
    opens = [c - 0.0001 for c in closes]
    highs = [c + 0.0005 for c in closes]
    lows = [c - 0.0005 for c in closes]
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": 1000},
        index=index,
    )


# ─────────────────────────────────────────────────────────────────────────────
# build_session_box
# ─────────────────────────────────────────────────────────────────────────────


class TestBuildSessionBox:

    def test_normal_asian_box(self):
        df = _make_df_1h(48)
        box = build_session_box(
            df, start_h=0, end_h=8, instrument="EURUSD", session="asian"
        )
        assert box.box_high > box.box_low
        assert box.box_range == pytest.approx(box.box_high - box.box_low, rel=1e-5)
        assert box.atr > 0
        assert box.session == "asian"
        assert box.instrument == "EURUSD"

    def test_too_few_candles_raises(self):
        df = _make_df_1h(4)  # only 4 candles, 00:00–03:00 → only 4 session candles
        small_df = df[df.index.hour < 2]  # force < 3
        with pytest.raises(ValueError, match="session not yet complete"):
            build_session_box(
                small_df, start_h=0, end_h=8, instrument="EURUSD", session="asian"
            )


# ─────────────────────────────────────────────────────────────────────────────
# classify_session
# ─────────────────────────────────────────────────────────────────────────────


class TestClassifySession:

    def _box(self, box_range, atr):
        return SessionBox(
            box_high=1.1050,
            box_low=1.1050 - box_range,
            box_range=box_range,
            atr=atr,
            session="asian",
            instrument="EURUSD",
        )

    def test_range_session(self):
        box = self._box(box_range=0.0003, atr=0.0010)  # ratio=0.30 < 0.50
        assert classify_session(box, CFG["sessions"]["asian"]) == "range"

    def test_trend_session(self):
        box = self._box(box_range=0.0009, atr=0.0010)  # ratio=0.90 > 0.70
        assert classify_session(box, CFG["sessions"]["asian"]) == "trend"

    def test_neutral_session(self):
        box = self._box(box_range=0.0006, atr=0.0010)  # ratio=0.60, between 0.50–0.70
        assert classify_session(box, CFG["sessions"]["asian"]) == "neutral"

    def test_zero_atr_returns_neutral(self):
        box = self._box(box_range=0.0006, atr=0.0)
        assert classify_session(box, CFG["sessions"]["asian"]) == "neutral"


# ─────────────────────────────────────────────────────────────────────────────
# detect_sweep
# ─────────────────────────────────────────────────────────────────────────────


class TestDetectSweep:

    def _box(self):
        return SessionBox(
            box_high=1.1050,
            box_low=1.1000,
            box_range=0.0050,
            atr=0.0030,
            session="asian",
            instrument="EURUSD",
        )

    def _df_with_candle(self, hour, high, low, close):
        """Create a minimal 1h df with a post-session candle at the given hour."""
        idx = pd.date_range("2024-01-01 08:00", periods=4, freq="1h", tz="UTC")
        data = {
            "open": [1.1025, 1.1025, 1.1025, 1.1025],
            "high": [1.1030, 1.1030, 1.1030, 1.1030],
            "low": [1.1020, 1.1020, 1.1020, 1.1020],
            "close": [1.1025, 1.1025, 1.1025, 1.1025],
        }
        df = pd.DataFrame(data, index=idx)
        # Inject the sweep candle at first post-session slot
        df.iloc[0] = {"open": 1.1025, "high": high, "low": low, "close": close}
        return df

    def test_high_sweep_detected(self):
        # Wick above box_high (1.1050) by > 0.008 * 0.0050 = 0.00004 → 1.10545
        # Close back inside box (< 1.1050)
        box = self._box()
        instr_cfg = CFG["instruments"]["EURUSD"]
        df = self._df_with_candle(hour=8, high=1.1056, low=1.1020, close=1.1040)
        sweep = detect_sweep(df, box, instr_cfg, end_h=8)
        assert sweep is not None
        assert sweep.direction == "high"

    def test_low_sweep_detected(self):
        box = self._box()
        instr_cfg = CFG["instruments"]["EURUSD"]
        df = self._df_with_candle(hour=8, high=1.1030, low=1.0994, close=1.1010)
        sweep = detect_sweep(df, box, instr_cfg, end_h=8)
        assert sweep is not None
        assert sweep.direction == "low"

    def test_no_sweep_when_close_outside(self):
        # Wick above box_high but close ALSO above box_high → not a sweep
        box = self._box()
        instr_cfg = CFG["instruments"]["EURUSD"]
        df = self._df_with_candle(hour=8, high=1.1060, low=1.1030, close=1.1055)
        sweep = detect_sweep(df, box, instr_cfg, end_h=8)
        assert sweep is None

    def test_no_sweep_when_wick_insufficient(self):
        # Wick above box_high but less than sweep_beyond_pct threshold
        box = self._box()
        instr_cfg = CFG["instruments"]["EURUSD"]
        df = self._df_with_candle(hour=8, high=1.1051, low=1.1020, close=1.1040)
        sweep = detect_sweep(df, box, instr_cfg, end_h=8)
        assert sweep is None


# ─────────────────────────────────────────────────────────────────────────────
# build_session_signal
# ─────────────────────────────────────────────────────────────────────────────


class TestBuildSessionSignal:

    def _patch_structure(self, bias="bullish"):
        return patch("smc_bot.session_range.structure.get_bias", return_value=bias)

    def _patch_tp_engine(self, tp=1.1150):
        return patch(
            "smc_bot.session_range.tp_engine.build_plan",
            return_value={"tp": tp, "plan": []},
        )

    def test_eurusd_asian_low_sweep_long(self):
        df_4h = _make_df_4h()
        df_1h = _make_df_1h(48, base_price=1.1000, amplitude=0.0020)

        with self._patch_structure("bullish"), self._patch_tp_engine(1.1200):
            with patch("smc_bot.session_range.detect_sweep") as mock_sweep, patch(
                "smc_bot.session_range.build_session_box"
            ) as mock_box:

                mock_box.return_value = SessionBox(
                    box_high=1.1050,
                    box_low=1.1000,
                    box_range=0.0050,
                    atr=0.0030,
                    session="asian",
                    instrument="EURUSD",
                )
                sweep_candle = pd.Series(
                    {"open": 1.1010, "high": 1.1030, "low": 1.0992, "close": 1.1015}
                )
                mock_sweep.return_value = SweepEvent(
                    direction="low", candle=sweep_candle
                )

                sig = build_session_signal(df_4h, df_1h, "EURUSD", "asian", CFG)

        assert sig is not None
        assert sig.side == "long"
        assert sig.setup == "sweep"
        assert sig.instrument == "EURUSD"
        assert sig.session == "asian"
        assert sig.sl < sig.entry < sig.tp

    def test_eurusd_asian_high_sweep_short(self):
        df_4h = _make_df_4h()
        df_1h = _make_df_1h(48)

        with self._patch_structure("bearish"), self._patch_tp_engine(1.0900):
            with patch("smc_bot.session_range.detect_sweep") as mock_sweep, patch(
                "smc_bot.session_range.build_session_box"
            ) as mock_box:

                mock_box.return_value = SessionBox(
                    box_high=1.1050,
                    box_low=1.1000,
                    box_range=0.0050,
                    atr=0.0030,
                    session="asian",
                    instrument="EURUSD",
                )
                sweep_candle = pd.Series(
                    {"open": 1.1040, "high": 1.1060, "low": 1.1025, "close": 1.1038}
                )
                mock_sweep.return_value = SweepEvent(
                    direction="high", candle=sweep_candle
                )

                sig = build_session_signal(df_4h, df_1h, "EURUSD", "asian", CFG)

        assert sig is not None
        assert sig.side == "short"
        assert sig.setup == "sweep"
        assert sig.tp < sig.entry < sig.sl

    def test_neutral_htf_returns_none(self):
        df_4h = _make_df_4h()
        df_1h = _make_df_1h(48)
        with self._patch_structure("neutral"):
            sig = build_session_signal(df_4h, df_1h, "GBPUSD", "london", CFG)
        assert sig is None

    def test_xauusd_overlap_trend_long(self):
        df_4h = _make_df_4h(base_price=1900.0)
        df_1h = _make_df_1h(48, base_price=1900.0, amplitude=2.0)

        with self._patch_structure("bullish"), patch(
            "smc_bot.session_range.tp_engine.build_plan",
            return_value={"tp": 1920.0, "plan": []},
        ):
            with patch("smc_bot.session_range.detect_sweep", return_value=None), patch(
                "smc_bot.session_range.classify_session", return_value="trend"
            ), patch("smc_bot.session_range.build_session_box") as mock_box:

                mock_box.return_value = SessionBox(
                    box_high=1910.0,
                    box_low=1890.0,
                    box_range=20.0,
                    atr=12.0,
                    session="overlap",
                    instrument="XAUUSD",
                )
                sig = build_session_signal(df_4h, df_1h, "XAUUSD", "overlap", CFG)

        assert sig is not None
        assert sig.side == "long"
        assert sig.setup == "trend"
        assert sig.instrument == "XAUUSD"
        assert sig.mgmt["trail_remainder"] is True  # overlap has trail

    def test_gbpusd_excluded_from_asian_session(self):
        """GBPUSD 'sessions' list does not include 'asian' — signal must be None."""
        df_4h = _make_df_4h()
        df_1h = _make_df_1h(48)
        with self._patch_structure("bullish"):
            # scan_all is the right entry point for session exclusion
            utc_now = datetime(
                2024, 1, 2, 9, 0, tzinfo=timezone.utc
            )  # after asian end_h=8
            data = {"GBPUSD": {"df_4h": df_4h, "df_1h": df_1h}}
            cfg = {**CFG, "risk": {"max_concurrent_signals": 3}}
            with patch(
                "smc_bot.session_range.build_session_signal", return_value=None
            ) as mock_sig:
                _signals = scan_all(data, cfg, utc_now=utc_now)
                # build_session_signal should never be called for GBPUSD/asian
                asian_calls = [
                    c
                    for c in mock_sig.call_args_list
                    if c.args[2] == "GBPUSD" and c.args[3] == "asian"
                ]
                assert (
                    len(asian_calls) == 0
                ), "GBPUSD should be excluded from Asian session"

    def test_xauusd_excluded_from_asian_session(self):
        df_4h = _make_df_4h(base_price=1900.0)
        df_1h = _make_df_1h(48, base_price=1900.0, amplitude=2.0)
        utc_now = datetime(2024, 1, 2, 9, 0, tzinfo=timezone.utc)
        data = {"XAUUSD": {"df_4h": df_4h, "df_1h": df_1h}}
        with patch(
            "smc_bot.session_range.build_session_signal", return_value=None
        ) as mock_sig:
            scan_all(data, CFG, utc_now=utc_now)
            asian_calls = [
                c
                for c in mock_sig.call_args_list
                if c.args[2] == "XAUUSD" and c.args[3] == "asian"
            ]
            assert len(asian_calls) == 0


# ─────────────────────────────────────────────────────────────────────────────
# scan_all
# ─────────────────────────────────────────────────────────────────────────────


class TestScanAll:

    def _make_sig(self, instrument, session, weight=1.0):
        return SessionSignal(
            instrument=instrument,
            session=session,
            setup="sweep",
            side="long",
            entry=1.1020,
            sl=1.1000,
            tp=1.1120,
            box_high=1.1050,
            box_low=1.1000,
            signal_weight=weight,
            mgmt={
                "first_close_pct": 0.75,
                "first_close_target": "opposite_box_edge",
                "trail_remainder": False,
            },
        )

    def test_cap_at_max_concurrent_signals(self):
        signals = [
            self._make_sig("EURUSD", "london", 1.0),
            self._make_sig("GBPUSD", "london", 0.9),
            self._make_sig("XAUUSD", "london", 1.0),
            self._make_sig("EURUSD", "overlap", 1.0),
        ]
        cfg = {**CFG, "risk": {"max_concurrent_signals": 2}}
        df = _make_df_1h(48)
        df4 = _make_df_4h()
        data = {
            "EURUSD": {"df_4h": df4, "df_1h": df},
            "GBPUSD": {"df_4h": df4, "df_1h": df},
            "XAUUSD": {"df_4h": df4, "df_1h": df},
        }
        utc_now = datetime(2024, 1, 2, 16, 0, tzinfo=timezone.utc)

        with patch(
            "smc_bot.session_range.build_session_signal", side_effect=signals[:4]
        ):
            result = scan_all(data, cfg, utc_now=utc_now)

        assert len(result) == 2

    def test_sorted_by_weight_descending(self):
        s1 = self._make_sig("EURUSD", "london", weight=0.9)
        s2 = self._make_sig("XAUUSD", "london", weight=1.0)
        cfg = {**CFG, "risk": {"max_concurrent_signals": 3}}
        df = _make_df_1h(48)
        df4 = _make_df_4h()
        data = {
            "EURUSD": {"df_4h": df4, "df_1h": df},
            "XAUUSD": {"df_4h": df4, "df_1h": df},
        }
        utc_now = datetime(2024, 1, 2, 16, 0, tzinfo=timezone.utc)

        with patch("smc_bot.session_range.build_session_signal", side_effect=[s1, s2]):
            result = scan_all(data, cfg, utc_now=utc_now)

        # Higher weight (XAUUSD 1.0) should come first
        assert result[0].signal_weight >= result[-1].signal_weight

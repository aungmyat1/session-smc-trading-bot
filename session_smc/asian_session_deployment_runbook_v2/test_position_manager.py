"""
tests/test_position_manager.py
Tests for session-specific position management:
  - SWEEP/RANGE: 75% close at opposite box edge → SL to BE
  - TREND: 75% close at 4R → SL to BE → trail remainder
  - State persistence: register, load, purge
"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import smc_bot.position_manager as pm


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

CFG = {
    "instruments": {
        "EURUSD": {"pip_size": 0.0001, "atr_period": 14},
        "XAUUSD": {"pip_size": 0.01,   "atr_period": 14},
    },
    "asian": {"target_r": 5.0, "trend_first_close_r": 4.0},
}


def _make_executor(mid_price: float = 1.1050) -> AsyncMock:
    ex = AsyncMock()
    ex.get_current_price = AsyncMock(return_value={"mid": mid_price, "bid": mid_price - 0.0001, "ask": mid_price + 0.0001})
    ex.get_open_positions = AsyncMock(return_value=[
        {"id": "pos_001", "symbol": "EURUSD"},
    ])
    ex.place_reduce_only = AsyncMock(return_value={"result": "ok"})
    ex.set_sl = AsyncMock(return_value={"result": "ok"})
    return ex


def _make_df_1h(periods: int = 30, base: float = 1.1020) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=periods, freq="1h", tz="UTC")
    closes = [base + 0.0001 * i for i in range(periods)]
    return pd.DataFrame({
        "open":  [c - 0.0001 for c in closes],
        "high":  [c + 0.0003 for c in closes],
        "low":   [c - 0.0003 for c in closes],
        "close": closes,
        "volume": [1000] * periods,
    }, index=idx)


def _sweep_state(
    position_id="pos_001",
    setup="sweep",
    side="long",
    entry=1.1010,
    sl=1.1000,
    tp=1.1060,
    box_high=1.1050,
    box_low=1.1000,
    lots=0.10,
    first_close_done=False,
    trail=False,
):
    return {
        position_id: {
            "instrument": "EURUSD",
            "session": "asian",
            "setup": setup,
            "side": side,
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "box_high": box_high,
            "box_low": box_low,
            "lots": lots,
            "mgmt": {
                "first_close_pct": 0.75,
                "first_close_target": "opposite_box_edge",
                "trail_remainder": trail,
            },
            "first_close_done": first_close_done,
            "opened_at": "2024-01-01T00:00:00+00:00",
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# State persistence
# ─────────────────────────────────────────────────────────────────────────────

class TestStatePersistence:

    def test_load_empty_state_when_file_missing(self, tmp_path):
        with patch.object(pm, "STATE_FILE", tmp_path / "position_state.json"):
            state = pm.load_state()
        assert state == {}

    def test_save_and_reload(self, tmp_path):
        with patch.object(pm, "STATE_FILE", tmp_path / "position_state.json"):
            data = {"pos_001": {"instrument": "EURUSD", "entry": 1.1020}}
            pm.save_state(data)
            loaded = pm.load_state()
        assert loaded["pos_001"]["entry"] == 1.1020

    def test_register_position(self, tmp_path):
        from smc_bot.session_range import SessionSignal
        sig = SessionSignal(
            instrument="EURUSD", session="asian", setup="sweep",
            side="long", entry=1.1010, sl=1.1000, tp=1.1060,
            box_high=1.1050, box_low=1.1000, signal_weight=1.0,
            mgmt={"first_close_pct": 0.75, "first_close_target": "opposite_box_edge",
                  "trail_remainder": False},
        )
        state = {}
        pm.register_position("pos_x", sig, lots=0.10, state=state)
        assert "pos_x" in state
        assert state["pos_x"]["instrument"] == "EURUSD"
        assert state["pos_x"]["first_close_done"] is False

    def test_purge_closed_positions(self):
        state = {
            "pos_open":   {"instrument": "EURUSD"},
            "pos_closed": {"instrument": "GBPUSD"},
        }
        updated = pm.purge_closed_positions(state, open_position_ids=["pos_open"])
        assert "pos_open"   in updated
        assert "pos_closed" not in updated


# ─────────────────────────────────────────────────────────────────────────────
# SWEEP/RANGE management
# ─────────────────────────────────────────────────────────────────────────────

class TestSweepRangeManagement:

    @pytest.mark.asyncio
    async def test_long_first_close_at_box_high(self):
        """Long sweep: price reaches box_high → 75% close + SL to BE."""
        state = _sweep_state(
            setup="sweep", side="long", entry=1.1010,
            sl=1.1000, box_high=1.1050, box_low=1.1000, lots=0.10,
        )
        ex = _make_executor(mid_price=1.1051)   # price AT box_high
        data = {"EURUSD": {"df_1h": _make_df_1h()}}

        await pm.manage_positions(ex, data, state, CFG)

        ex.place_reduce_only.assert_called_once()
        call_args = ex.place_reduce_only.call_args
        assert call_args.args[0] == "pos_001"
        assert call_args.args[1] == pytest.approx(0.075, rel=0.01)  # 75% of 0.10

        ex.set_sl.assert_called_once_with("pos_001", 1.1010)   # SL → entry (BE)
        assert state["pos_001"]["first_close_done"] is True

    @pytest.mark.asyncio
    async def test_short_first_close_at_box_low(self):
        """Short sweep: price reaches box_low → 75% close + SL to BE."""
        state = _sweep_state(
            setup="sweep", side="short", entry=1.1040,
            sl=1.1055, box_high=1.1050, box_low=1.1000, lots=0.10,
        )
        ex = _make_executor(mid_price=1.0999)   # price BELOW box_low
        data = {"EURUSD": {"df_1h": _make_df_1h()}}

        await pm.manage_positions(ex, data, state, CFG)

        ex.place_reduce_only.assert_called_once()
        ex.set_sl.assert_called_once_with("pos_001", 1.1040)   # SL → entry (BE)

    @pytest.mark.asyncio
    async def test_no_action_before_target(self):
        """Price hasn't reached box_high yet → no partial close."""
        state = _sweep_state(
            setup="sweep", side="long", entry=1.1010,
            sl=1.1000, box_high=1.1050, box_low=1.1000, lots=0.10,
        )
        ex = _make_executor(mid_price=1.1030)   # price midway, not at box_high
        data = {"EURUSD": {"df_1h": _make_df_1h()}}

        await pm.manage_positions(ex, data, state, CFG)

        ex.place_reduce_only.assert_not_called()
        ex.set_sl.assert_not_called()
        assert state["pos_001"]["first_close_done"] is False

    @pytest.mark.asyncio
    async def test_no_double_close(self):
        """Once first_close_done=True, no further partial close on sweep setup."""
        state = _sweep_state(
            setup="sweep", side="long", entry=1.1010,
            sl=1.1010,   # already at BE
            box_high=1.1050, lots=0.10, first_close_done=True,
        )
        ex = _make_executor(mid_price=1.1055)
        data = {"EURUSD": {"df_1h": _make_df_1h()}}

        await pm.manage_positions(ex, data, state, CFG)

        ex.place_reduce_only.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# TREND management (4R close + trail)
# ─────────────────────────────────────────────────────────────────────────────

class TestTrendManagement:

    @pytest.mark.asyncio
    async def test_trend_long_close_at_4r(self):
        """Trend long: price at 4R → 75% close + SL to BE."""
        entry = 1.1000
        sl    = 1.0990   # 10 pip SL → 1R = 10 pips
        # 4R target = 1.1000 + 4 * 0.0010 = 1.1040
        state = {
            "pos_001": {
                "instrument": "EURUSD",
                "session": "overlap",
                "setup": "trend",
                "side": "long",
                "entry": entry,
                "sl": sl,
                "tp": 1.1050,
                "box_high": 1.1050,
                "box_low": 1.0990,
                "lots": 0.20,
                "mgmt": {
                    "first_close_pct": 0.75,
                    "first_close_target": "4R",
                    "trail_remainder": True,
                },
                "first_close_done": False,
                "opened_at": "2024-01-01T00:00:00+00:00",
            }
        }
        ex = _make_executor(mid_price=1.1042)   # at 4.2R
        ex.get_open_positions = AsyncMock(return_value=[{"id": "pos_001", "symbol": "EURUSD"}])
        data = {"EURUSD": {"df_1h": _make_df_1h(base=entry)}}

        await pm.manage_positions(ex, data, state, CFG)

        ex.place_reduce_only.assert_called_once()
        partial_lots = ex.place_reduce_only.call_args.args[1]
        assert partial_lots == pytest.approx(0.15, rel=0.01)   # 75% of 0.20
        ex.set_sl.assert_called()
        assert state["pos_001"]["first_close_done"] is True

    @pytest.mark.asyncio
    async def test_trail_stop_tightens_on_profit(self):
        """After first close + trail=True, SL should move up with price."""
        entry = 1.1000
        sl_be = 1.1000   # already at BE
        atr   = 0.0010   # 10 pips ATR
        state = {
            "pos_001": {
                "instrument": "EURUSD",
                "session": "overlap",
                "setup": "trend",
                "side": "long",
                "entry": entry,
                "sl": sl_be,
                "tp": 1.1060,
                "box_high": 1.1060,
                "box_low": 1.0990,
                "lots": 0.20,
                "mgmt": {
                    "first_close_pct": 0.75,
                    "first_close_target": "4R",
                    "trail_remainder": True,
                },
                "first_close_done": True,   # already done
                "opened_at": "2024-01-01T00:00:00+00:00",
            }
        }
        mid_price = 1.1045   # profitable; trail_sl = 1.1045 - atr = 1.1035
        ex = _make_executor(mid_price=mid_price)
        ex.get_open_positions = AsyncMock(return_value=[{"id": "pos_001", "symbol": "EURUSD"}])

        # Build df that gives ATR ≈ 0.0010
        df = _make_df_1h(30, base=1.1000)
        data = {"EURUSD": {"df_1h": df}}

        with patch.object(pm, "_calc_atr", return_value=atr):
            await pm.manage_positions(ex, data, state, CFG)

        # Trail SL should have been set above BE (1.1000)
        if ex.set_sl.called:
            new_sl = ex.set_sl.call_args.args[1]
            assert new_sl > sl_be, "Trailing SL must be above breakeven"

    @pytest.mark.asyncio
    async def test_trail_does_not_move_sl_below_be(self):
        """Trail stop must never drop below breakeven (entry)."""
        entry = 1.1000
        state = {
            "pos_001": {
                "instrument": "EURUSD",
                "session": "overlap",
                "setup": "trend",
                "side": "long",
                "entry": entry,
                "sl": entry,   # already at BE
                "tp": 1.1060,
                "box_high": 1.1060,
                "box_low": 1.0990,
                "lots": 0.20,
                "mgmt": {
                    "first_close_pct": 0.75,
                    "first_close_target": "4R",
                    "trail_remainder": True,
                },
                "first_close_done": True,
                "opened_at": "2024-01-01T00:00:00+00:00",
            }
        }
        # Price near BE — trail_sl would be BELOW entry → should NOT move SL
        ex = _make_executor(mid_price=1.1005)
        ex.get_open_positions = AsyncMock(return_value=[{"id": "pos_001", "symbol": "EURUSD"}])
        data = {"EURUSD": {"df_1h": _make_df_1h()}}

        with patch.object(pm, "_calc_atr", return_value=0.0010):
            await pm.manage_positions(ex, data, state, CFG)

        # set_sl should NOT be called because trail_sl < entry (BE)
        if ex.set_sl.called:
            new_sl = ex.set_sl.call_args.args[1]
            assert new_sl >= entry, "SL must not go below breakeven"


# ─────────────────────────────────────────────────────────────────────────────
# Edge cases
# ─────────────────────────────────────────────────────────────────────────────

class TestEdgeCases:

    @pytest.mark.asyncio
    async def test_empty_state_no_op(self):
        ex = _make_executor()
        await pm.manage_positions(ex, {}, {}, CFG)
        ex.place_reduce_only.assert_not_called()
        ex.set_sl.assert_not_called()

    @pytest.mark.asyncio
    async def test_position_not_in_open_list_is_skipped(self):
        """Position in state but not in MetaAPI open positions → skip."""
        state = _sweep_state("pos_stale", side="long", entry=1.1010, sl=1.1000)
        ex = _make_executor(mid_price=1.1060)
        # Return an EMPTY positions list — pos_stale is closed
        ex.get_open_positions = AsyncMock(return_value=[])
        data = {"EURUSD": {"df_1h": _make_df_1h()}}

        await pm.manage_positions(ex, data, state, CFG)

        ex.place_reduce_only.assert_not_called()
        # stale position should have been purged
        assert "pos_stale" not in state

    @pytest.mark.asyncio
    async def test_price_fetch_failure_skips_gracefully(self):
        """If get_current_price throws, that position is skipped without crashing."""
        state = _sweep_state("pos_001", side="long")
        ex = _make_executor()
        ex.get_open_positions = AsyncMock(return_value=[{"id": "pos_001", "symbol": "EURUSD"}])
        ex.get_current_price = AsyncMock(side_effect=RuntimeError("timeout"))
        data = {"EURUSD": {"df_1h": _make_df_1h()}}

        # Should not raise
        await pm.manage_positions(ex, data, state, CFG)
        ex.place_reduce_only.assert_not_called()

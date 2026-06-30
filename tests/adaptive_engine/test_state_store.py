"""Tests for adaptive/state/state_store.py"""

import json

import pytest

from adaptive.state.state_store import StateStore


@pytest.fixture
def tmp_path_state(tmp_path):
    return tmp_path / "adaptive_state.json"


class TestStateStore:
    def test_creates_default_state_when_file_absent(self, tmp_path_state):
        s = StateStore(tmp_path_state)
        state = s.get()
        assert state["halted"] is False
        assert state["trades_today"] == 0
        assert state["daily_loss_pct"] == 0.0

    def test_save_and_reload(self, tmp_path_state):
        s = StateStore(tmp_path_state)
        state = s.get()
        state["trades_today"] = 3
        s.update(state)
        s2 = StateStore(tmp_path_state)
        assert s2.get()["trades_today"] == 3

    def test_update_auto_saves(self, tmp_path_state):
        s = StateStore(tmp_path_state)
        state = s.get()
        state["daily_loss_pct"] = 0.012
        s.update(state)
        raw = json.loads(tmp_path_state.read_text())
        assert raw["daily_loss_pct"] == pytest.approx(0.012)

    def test_reset_daily_clears_counters(self, tmp_path_state):
        s = StateStore(tmp_path_state)
        state = s.get()
        state["trades_today"] = 5
        state["daily_loss_pct"] = 0.02
        state["halted"] = True
        s.update(state)
        s.reset_daily()
        state = s.get()
        assert state["trades_today"] == 0
        assert state["daily_loss_pct"] == 0.0
        assert state["halted"] is False

    def test_needs_daily_reset_true_when_no_last_reset(self, tmp_path_state):
        s = StateStore(tmp_path_state)
        assert s.needs_daily_reset() is True

    def test_needs_daily_reset_false_after_reset_today(self, tmp_path_state):
        s = StateStore(tmp_path_state)
        s.reset_daily()
        assert s.needs_daily_reset() is False

    def test_load_handles_corrupt_file(self, tmp_path_state):
        tmp_path_state.write_text("not json")
        s = StateStore(tmp_path_state)
        assert s.get()["halted"] is False

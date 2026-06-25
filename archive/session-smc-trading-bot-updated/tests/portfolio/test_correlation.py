"""Tests: correlation manager blocking."""

from core.correlation_manager import CorrelationManager
from core.signal import Signal
from datetime import datetime, timezone


def _sig(symbol="EURUSD", action="BUY") -> Signal:
    return Signal(
        timestamp=datetime.now(timezone.utc).isoformat(),
        strategy_name="ST-A2",
        symbol=symbol,
        action=action,
        entry_price=1.10,
        stop_loss=1.095,
        take_profit=1.11,
        confidence=0.9,
    )


class TestCorrelationBlock:
    def test_same_group_same_direction_blocked(self):
        cm = CorrelationManager()
        blocked, reason = cm.check("EURJPY", "BUY", {"EURUSD": "BUY"})
        assert blocked
        assert "EUR" in reason

    def test_same_group_opposite_direction_allowed(self):
        cm = CorrelationManager()
        blocked, _ = cm.check("EURJPY", "SELL", {"EURUSD": "BUY"})
        assert not blocked

    def test_different_group_allowed(self):
        cm = CorrelationManager()
        blocked, _ = cm.check("USDJPY", "BUY", {"EURUSD": "BUY"})
        assert not blocked

    def test_no_open_positions_allowed(self):
        cm = CorrelationManager()
        blocked, _ = cm.check("EURUSD", "BUY", {})
        assert not blocked

    def test_gbp_group_blocked(self):
        cm = CorrelationManager()
        blocked, reason = cm.check("GBPJPY", "SELL", {"GBPUSD": "SELL"})
        assert blocked
        assert "GBP" in reason

    def test_jpy_group_blocked(self):
        cm = CorrelationManager()
        blocked, reason = cm.check("GBPJPY", "BUY", {"USDJPY": "BUY"})
        assert blocked
        assert "JPY" in reason

    def test_filter_signals_removes_correlated(self):
        cm = CorrelationManager()
        signals = [_sig("EURUSD", "BUY"), _sig("EURJPY", "BUY")]
        result = cm.filter_signals(signals, {})
        assert len(result) == 1
        assert result[0].symbol == "EURUSD"

    def test_filter_signals_opposite_both_pass(self):
        cm = CorrelationManager()
        signals = [_sig("EURUSD", "BUY"), _sig("EURJPY", "SELL")]
        result = cm.filter_signals(signals, {})
        assert len(result) == 2

    def test_get_groups(self):
        cm = CorrelationManager()
        groups = cm.get_groups("EURGBP")
        assert "EUR" in groups
        assert "GBP" in groups

    def test_unknown_symbol_not_blocked(self):
        cm = CorrelationManager()
        blocked, _ = cm.check("XAUUSD", "BUY", {"EURUSD": "BUY"})
        assert not blocked

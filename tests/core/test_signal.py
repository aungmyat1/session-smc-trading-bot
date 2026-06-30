"""Tests for core.Signal dataclass."""

from core.signal import Signal


def _make_signal(**kwargs) -> Signal:
    defaults = dict(
        timestamp="2026-01-01T07:00:00+00:00",
        strategy_name="TEST",
        symbol="EURUSD",
        action="BUY",
        entry_price=1.1000,
        stop_loss=1.0950,
        take_profit=1.1100,
        risk_percent=0.25,
        confidence=0.9,
        metadata={"session": "london"},
    )
    defaults.update(kwargs)
    return Signal(**defaults)


class TestSignalCreation:
    def test_required_fields_set(self):
        s = _make_signal()
        assert s.symbol == "EURUSD"
        assert s.action == "BUY"
        assert s.entry_price == 1.1000

    def test_defaults(self):
        s = Signal(
            timestamp="2026-01-01T00:00:00+00:00",
            strategy_name="X",
            symbol="GBPUSD",
            action="SELL",
        )
        assert s.order_type == "MARKET"
        assert s.risk_percent == 0.25
        assert s.confidence == 1.0
        assert s.metadata == {}

    def test_compatibility_pair(self):
        s = _make_signal(symbol="GBPUSD")
        assert s.pair == "GBPUSD"

    def test_compatibility_side_buy(self):
        s = _make_signal(action="BUY")
        assert s.side == "long"

    def test_compatibility_side_sell(self):
        s = _make_signal(action="SELL")
        assert s.side == "short"

    def test_compatibility_entry(self):
        s = _make_signal(entry_price=1.2345)
        assert s.entry == 1.2345

    def test_compatibility_session_from_metadata(self):
        s = _make_signal(metadata={"session": "new_york"})
        assert s.session == "new_york"

    def test_session_empty_when_not_in_metadata(self):
        s = _make_signal(metadata={})
        assert s.session == ""

    def test_to_dict_contains_all_fields(self):
        s = _make_signal()
        d = s.to_dict()
        for key in (
            "timestamp",
            "strategy_name",
            "symbol",
            "action",
            "order_type",
            "entry_price",
            "stop_loss",
            "take_profit",
            "risk_percent",
            "confidence",
            "metadata",
        ):
            assert key in d

    def test_close_action(self):
        s = _make_signal(action="CLOSE")
        assert s.action == "CLOSE"

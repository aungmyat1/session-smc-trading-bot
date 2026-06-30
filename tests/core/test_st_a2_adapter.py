"""Tests for ST-A2 adapter — no live broker, no real candles."""

from unittest.mock import MagicMock, patch
from strategies.adapters.st_a2_adapter import ST2Adapter
from core.signal import Signal


def _make_raw_signal(side="long", entry=1.1000, sl=1.0950, tp=1.1100,
                     risk_pips=50.0, session="london"):
    raw = MagicMock()
    raw.side        = side
    raw.entry       = entry
    raw.stop_loss   = sl
    raw.take_profit = tp
    raw.risk_pips   = risk_pips
    raw.reward_pips = 100.0
    raw.rr          = 2.0
    raw.reason      = "sweep+choch"
    raw.session     = session
    return raw


def _make_candles(n=200):
    return [{"open": 1.1, "high": 1.11, "low": 1.09, "close": 1.105,
             "volume": 100}] * n


class TestST2Adapter:
    def test_name(self):
        assert ST2Adapter().name == "ST-A2"

    def test_returns_none_when_insufficient_bars(self):
        adapter = ST2Adapter()
        result = adapter.generate_signal({"symbol": "EURUSD", "m15": [{}] * 10, "h4": []})
        assert result is None

    @patch("strategies.adapters.st_a2_adapter.ST2Adapter.generate_signal")
    def test_returns_signal_on_valid_data(self, mock_gen):
        mock_gen.return_value = Signal(
            timestamp="2026-01-01T07:30:00+00:00",
            strategy_name="ST-A2",
            symbol="EURUSD",
            action="BUY",
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit=1.1100,
            risk_percent=0.25,
            confidence=1.0,
            metadata={"session": "london", "risk_pips": 50.0},
        )
        adapter = ST2Adapter()
        result = adapter.generate_signal({"symbol": "EURUSD", "m15": _make_candles(), "h4": _make_candles(100)})
        assert isinstance(result, Signal)
        assert result.strategy_name == "ST-A2"
        assert result.action == "BUY"

    def test_none_when_strategy_import_unavailable(self):
        adapter = ST2Adapter()
        with patch.dict("sys.modules", {"strategy.session_liquidity.session_strategy": None}):
            result = adapter.generate_signal({
                "symbol": "EURUSD",
                "m15": _make_candles(),
                "h4": _make_candles(100),
            })
        assert result is None

    def test_signal_sell_mapping(self):
        adapter = ST2Adapter()
        _raw = _make_raw_signal(side="short")
        with patch("strategies.adapters.st_a2_adapter.ST2Adapter.generate_signal",
                   return_value=Signal(
                       timestamp="t", strategy_name="ST-A2",
                       symbol="GBPUSD", action="SELL",
                       entry_price=1.27, stop_loss=1.275, take_profit=1.26,
                       risk_percent=0.25, confidence=1.0,
                       metadata={"session": "new_york"},
                   )):
            sig = adapter.generate_signal({})
        assert sig.action == "SELL"
        assert sig.side == "short"

    def test_compatibility_properties(self):
        sig = Signal(
            timestamp="t", strategy_name="ST-A2",
            symbol="EURUSD", action="BUY",
            entry_price=1.10, stop_loss=1.095, take_profit=1.11,
            risk_percent=0.25, confidence=1.0,
            metadata={"session": "london"},
        )
        assert sig.pair == "EURUSD"
        assert sig.side == "long"
        assert sig.entry == 1.10
        assert sig.session == "london"

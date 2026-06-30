"""Tests: signal expiry, conflict resolution, duplicate blocking."""

from datetime import datetime, timedelta, timezone

from core.signal import Signal
from core.signal_router import SignalRouter


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _old(seconds: int = 400) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


def _sig(
    symbol="EURUSD",
    action="BUY",
    confidence=0.9,
    entry=1.10,
    sl=1.095,
    tp=1.11,
    ts=None,
    ttl=300,
) -> Signal:
    return Signal(
        timestamp=ts or _now(),
        strategy_name="ST-A2",
        symbol=symbol,
        action=action,
        entry_price=entry,
        stop_loss=sl,
        take_profit=tp,
        confidence=confidence,
        ttl_seconds=ttl,
    )


class TestSignalExpiry:
    def test_fresh_signal_passes(self):
        router = SignalRouter()
        result = router.route([_sig(ts=_now())])
        assert len(result) == 1

    def test_expired_signal_rejected(self):
        router = SignalRouter()
        result = router.route([_sig(ts=_old(400), ttl=300)])
        assert result == []

    def test_ttl_exactly_at_boundary(self):
        router = SignalRouter()
        ts = (datetime.now(timezone.utc) - timedelta(seconds=301)).isoformat()
        result = router.route([_sig(ts=ts, ttl=300)])
        assert result == []


class TestConflictResolution:
    def test_buy_and_sell_same_symbol_rejected(self):
        router = SignalRouter()
        buy = _sig(action="BUY", confidence=0.9)
        sell = _sig(action="SELL", confidence=0.8, entry=1.10, sl=1.105, tp=1.09)
        result = router.route([buy, sell])
        assert result == []

    def test_buy_only_passes(self):
        router = SignalRouter()
        result = router.route([_sig(action="BUY")])
        assert len(result) == 1

    def test_different_symbols_no_conflict(self):
        router = SignalRouter()
        eur = _sig(symbol="EURUSD", action="BUY")
        gbp = _sig(symbol="GBPUSD", action="BUY", entry=1.27, sl=1.265, tp=1.28)
        result = router.route([eur, gbp])
        assert len(result) == 2


class TestDuplicateBlock:
    def test_same_symbol_direction_keeps_highest_confidence(self):
        router = SignalRouter()
        s1 = Signal(
            timestamp=_now(),
            strategy_name="ST-A2",
            symbol="EURUSD",
            action="BUY",
            entry_price=1.10,
            stop_loss=1.095,
            take_profit=1.11,
            confidence=0.9,
        )
        s2 = Signal(
            timestamp=_now(),
            strategy_name="LondonBreakout",
            symbol="EURUSD",
            action="BUY",
            entry_price=1.10,
            stop_loss=1.095,
            take_profit=1.11,
            confidence=0.75,
        )
        result = router.route([s1, s2])
        assert len(result) == 1
        assert result[0].confidence == 0.9

    def test_sorted_by_confidence_desc(self):
        router = SignalRouter()
        low = _sig(symbol="EURUSD", action="BUY", confidence=0.7)
        high = _sig(
            symbol="GBPUSD",
            action="BUY",
            confidence=0.95,
            entry=1.27,
            sl=1.265,
            tp=1.28,
        )
        result = router.route([low, high])
        assert result[0].confidence == 0.95


class TestGeometryValidation:
    def test_buy_sl_above_entry_rejected(self):
        router = SignalRouter()
        sig = _sig(action="BUY", entry=1.10, sl=1.11, tp=1.12)
        assert router.route([sig]) == []

    def test_sell_sl_below_entry_rejected(self):
        router = SignalRouter()
        sig = Signal(
            timestamp=_now(),
            strategy_name="ST-A2",
            symbol="EURUSD",
            action="SELL",
            entry_price=1.10,
            stop_loss=1.09,
            take_profit=1.05,
            confidence=0.9,
        )
        assert router.route([sig]) == []

    def test_valid_sell_passes(self):
        router = SignalRouter()
        sig = Signal(
            timestamp=_now(),
            strategy_name="ST-A2",
            symbol="EURUSD",
            action="SELL",
            entry_price=1.10,
            stop_loss=1.105,
            take_profit=1.09,
            confidence=0.9,
        )
        assert len(router.route([sig])) == 1

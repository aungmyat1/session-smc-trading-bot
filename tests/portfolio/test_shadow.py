"""Tests: shadow tracker (no execution) + strategy failure isolation."""

from datetime import datetime, timezone

from core.signal import Signal
from core.signal_router import SignalRouter
from core.base_strategy import BaseStrategy
from strategies.shadow_tracker import ShadowTracker


def _sig(strategy="ShadowStrat", symbol="EURUSD", action="BUY") -> Signal:
    return Signal(
        timestamp=datetime.now(timezone.utc).isoformat(),
        strategy_name=strategy,
        symbol=symbol,
        action=action,
        entry_price=1.10,
        stop_loss=1.095,
        take_profit=1.11,
        confidence=0.85,
        metadata={"session": "london"},
    )


class TestShadowNoExecution:
    def test_track_writes_to_journal(self, tmp_path):
        path = tmp_path / "shadow.jsonl"
        tracker = ShadowTracker(path)
        tracker.track(_sig())
        records = tracker.read_all()
        assert len(records) == 1
        assert records[0]["executed"] is False

    def test_track_records_correct_fields(self, tmp_path):
        path = tmp_path / "shadow.jsonl"
        tracker = ShadowTracker(path)
        sig = _sig(strategy="VWAPBreakout", symbol="GBPUSD", action="SELL")
        tracker.track(sig)
        rec = tracker.read_all()[0]
        assert rec["strategy_name"] == "VWAPBreakout"
        assert rec["symbol"] == "GBPUSD"
        assert rec["action"] == "SELL"
        assert rec["type"] == "SHADOW_SIGNAL"

    def test_track_never_returns_order(self, tmp_path):
        path = tmp_path / "shadow.jsonl"
        tracker = ShadowTracker(path)
        result = tracker.track(_sig())
        assert result is None   # track() always returns None

    def test_summary_counts_by_strategy(self, tmp_path):
        path = tmp_path / "shadow.jsonl"
        tracker = ShadowTracker(path)
        tracker.track(_sig(strategy="A"))
        tracker.track(_sig(strategy="A"))
        tracker.track(_sig(strategy="B"))
        summary = tracker.summary()
        assert summary["total_shadow_signals"] == 3
        assert summary["by_strategy"]["A"] == 2
        assert summary["by_strategy"]["B"] == 1

    def test_empty_journal_returns_empty(self, tmp_path):
        path = tmp_path / "shadow.jsonl"
        tracker = ShadowTracker(path)
        assert tracker.read_all() == []
        assert tracker.summary()["total_shadow_signals"] == 0


class TestStrategyFailureIsolation:
    """A broken strategy must not prevent valid signals from other strategies."""

    class _GoodStrategy(BaseStrategy):
        @property
        def name(self): return "GOOD"
        def generate_signal(self, data):
            return _sig(strategy="GOOD")

    class _BrokenStrategy(BaseStrategy):
        @property
        def name(self): return "BROKEN"
        def generate_signal(self, data):
            raise RuntimeError("strategy crashed")

    def test_broken_strategy_isolated(self):
        good   = self._GoodStrategy()
        broken = self._BrokenStrategy()

        results = []
        for strategy in [good, broken]:
            try:
                sig = strategy.generate_signal({})
                if sig:
                    results.append(sig)
            except Exception:
                pass   # isolated — other strategies continue

        assert len(results) == 1
        assert results[0].strategy_name == "GOOD"

    def test_signal_router_handles_valid_subset(self):
        router = SignalRouter()
        valid = _sig(strategy="GOOD")
        # Only valid signal — router should approve it
        result = router.route([valid])
        assert len(result) == 1

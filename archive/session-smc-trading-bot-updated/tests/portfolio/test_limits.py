"""Tests: daily trade limit, daily/weekly/monthly loss limits, circuit breaker."""

from datetime import date, datetime, timedelta, timezone

import pytest

from core.circuit_breaker import CircuitBreaker
from core.portfolio_manager import PortfolioManager
from core.signal import Signal


def _sig(strategy="ST-A2", symbol="EURUSD", action="BUY", confidence=0.9) -> Signal:
    return Signal(
        timestamp=datetime.now(timezone.utc).isoformat(),
        strategy_name=strategy,
        symbol=symbol,
        action=action,
        entry_price=1.10,
        stop_loss=1.095,
        take_profit=1.11,
        confidence=confidence,
    )


def _pm(**overrides) -> PortfolioManager:
    cfg = {
        "portfolio": {
            "max_trades_per_day": 4,
            "max_open_positions": 3,
            "daily_loss_limit_pct": 2.0,
            "weekly_loss_limit_pct": 5.0,
            "monthly_loss_limit_pct": 8.0,
            "min_confidence": 0.6,
        },
        "strategies": {"ST-A2": {"enabled": True}},
    }
    cfg["portfolio"].update(overrides)
    return PortfolioManager(cfg)


class TestDailyTradeLimit:
    def test_blocks_when_limit_reached(self):
        pm = _pm(max_trades_per_day=2)
        pm._trades_today = 2
        pm._last_reset = date.today().isoformat()
        assert pm.evaluate([_sig()]) == []

    def test_allows_below_limit(self):
        pm = _pm(max_trades_per_day=4)
        pm._trades_today = 2
        pm._last_reset = date.today().isoformat()
        assert len(pm.evaluate([_sig()])) == 1


class TestDailyLossLimit:
    def test_is_daily_loss_hit_true(self):
        pm = _pm()
        pm._daily_pnl_pct = -0.021
        assert pm.is_daily_loss_hit()

    def test_is_daily_loss_hit_false(self):
        pm = _pm()
        pm._daily_pnl_pct = -0.01
        assert not pm.is_daily_loss_hit()

    def test_weekly_loss_hit(self):
        pm = _pm()
        pm._weekly_pnl_pct = -0.051
        assert pm.is_weekly_loss_hit()

    def test_monthly_loss_hit(self):
        pm = _pm()
        pm._monthly_pnl_pct = -0.081
        assert pm.is_monthly_loss_hit()

    def test_any_loss_limit(self):
        pm = _pm()
        pm._weekly_pnl_pct = -0.06
        assert pm.any_loss_limit_hit()

    def test_record_close_accumulates_all_periods(self):
        pm = _pm()
        pm.record_trade(_sig())
        pm.record_close("EURUSD", pnl_pct=-0.003)
        assert pm._daily_pnl_pct == -0.003
        assert pm._weekly_pnl_pct == -0.003
        assert pm._monthly_pnl_pct == -0.003


class TestRiskTiers:
    def test_tier1_strategy(self):
        pm = _pm()
        assert pm.get_risk_pct("ST-A2") == 0.30

    def test_tier2_strategy(self):
        pm = _pm()
        assert pm.get_risk_pct("LondonBreakout") == 0.20

    def test_tier3_unknown(self):
        pm = _pm()
        assert pm.get_risk_pct("NewUnknownStrategy") == 0.10


class TestCircuitBreaker:
    def test_blocks_after_signal_rate_limit(self):
        cb = CircuitBreaker({"ST-A2": {"max_signals_hour": 2}})
        cb.record_signal("ST-A2")
        cb.record_signal("ST-A2")
        ok, reason = cb.check("ST-A2")
        assert not ok
        assert "rate limit" in reason

    def test_allows_before_limit(self):
        cb = CircuitBreaker({"ST-A2": {"max_signals_hour": 3}})
        cb.record_signal("ST-A2")
        ok, _ = cb.check("ST-A2")
        assert ok

    def test_blocks_after_daily_trade_limit(self):
        cb = CircuitBreaker({"ST-A2": {"max_trades_day": 2}})
        st = cb._state_for("ST-A2")
        st.trades_today = 2
        ok, reason = cb.check("ST-A2")
        assert not ok
        assert "daily trade limit" in reason

    def test_cooldown_after_max_losses(self):
        cb = CircuitBreaker({"ST-A2": {"max_losses": 2, "cooldown_hours": 1}})
        st = cb._state_for("ST-A2")
        st.consecutive_losses = 2
        ok, reason = cb.check("ST-A2")
        assert not ok
        assert "cooldown" in reason

    def test_win_resets_consecutive_losses(self):
        cb = CircuitBreaker()
        cb.record_trade("ST-A2", won=False)
        cb.record_trade("ST-A2", won=False)
        cb.record_trade("ST-A2", won=True)
        assert cb._state_for("ST-A2").consecutive_losses == 0

    def test_reset_clears_state(self):
        cb = CircuitBreaker()
        cb.record_signal("ST-A2")
        cb.reset_strategy("ST-A2")
        assert "ST-A2" not in cb._state

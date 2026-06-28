"""Tests for core.PortfolioManager."""

from core.signal import Signal
from core.portfolio_manager import PortfolioManager


def _sig(strategy="ST-A2", symbol="EURUSD", action="BUY", confidence=0.9) -> Signal:
    return Signal(
        timestamp="2026-01-01T08:00:00+00:00",
        strategy_name=strategy,
        symbol=symbol,
        action=action,
        entry_price=1.1000,
        stop_loss=1.0950,
        take_profit=1.1100,
        risk_percent=0.25,
        confidence=confidence,
        metadata={"session": "london"},
    )


def _cfg(**overrides) -> dict:
    base = {
        "portfolio": {
            "max_trades_per_day": 4,
            "max_open_positions": 2,
            "daily_loss_limit_pct": 1.5,
            "min_confidence": 0.6,
        },
        "correlation_groups": [["EURUSD", "GBPUSD"]],
        "strategies": {
            "ST-A2":          {"enabled": True,  "risk": 0.25, "min_confidence": 0.7},
            "LondonBreakout": {"enabled": True,  "risk": 0.25, "min_confidence": 0.6},
            "NYMomentum":     {"enabled": False, "risk": 0.25, "min_confidence": 0.6},
        },
    }
    base["portfolio"].update(overrides)
    return base


class TestPortfolioManager:

    def test_approve_valid_signal(self):
        pm = PortfolioManager(_cfg())
        result = pm.evaluate([_sig(confidence=0.9)])
        assert len(result) == 1

    def test_reject_disabled_strategy(self):
        pm = PortfolioManager(_cfg())
        result = pm.evaluate([_sig(strategy="NYMomentum", confidence=0.9)])
        assert result == []

    def test_reject_below_strategy_min_confidence(self):
        pm = PortfolioManager(_cfg())
        result = pm.evaluate([_sig(strategy="ST-A2", confidence=0.65)])
        assert result == []

    def test_reject_below_global_min_confidence(self):
        pm = PortfolioManager(_cfg())
        result = pm.evaluate([_sig(strategy="LondonBreakout", confidence=0.5)])
        assert result == []

    def test_reject_already_open_symbol(self):
        pm = PortfolioManager(_cfg())
        pm.record_trade(_sig())
        result = pm.evaluate([_sig()])
        assert result == []

    def test_correlation_filter_same_direction_keeps_highest(self):
        pm = PortfolioManager(_cfg())
        eur = _sig(symbol="EURUSD", action="BUY", confidence=0.9)
        gbp = _sig(strategy="LondonBreakout", symbol="GBPUSD", action="BUY", confidence=0.75)
        result = pm.evaluate([gbp, eur])
        assert len(result) == 1
        assert result[0].symbol == "EURUSD"   # higher confidence wins

    def test_correlation_filter_opposite_directions_both_pass(self):
        pm = PortfolioManager(_cfg())
        eur = _sig(symbol="EURUSD", action="BUY",  confidence=0.9)
        gbp = _sig(strategy="LondonBreakout", symbol="GBPUSD", action="SELL", confidence=0.8)
        result = pm.evaluate([eur, gbp])
        assert len(result) == 2

    def test_max_daily_trades_cap(self):
        from datetime import date
        pm = PortfolioManager(_cfg(max_trades_per_day=2))
        pm._trades_today = 2
        pm._last_reset   = date.today().isoformat()   # prevent reset clearing counter
        result = pm.evaluate([_sig()])
        assert result == []

    def test_max_open_positions_cap(self):
        from datetime import date
        pm = PortfolioManager(_cfg(max_open_positions=1))
        pm._open_symbols = {"EURUSD"}
        pm._last_reset   = date.today().isoformat()
        result = pm.evaluate([_sig(symbol="GBPUSD", strategy="LondonBreakout")])
        assert result == []

    def test_sorted_by_confidence_desc(self):
        pm = PortfolioManager(_cfg())
        s1 = _sig(strategy="ST-A2",          symbol="EURUSD", action="BUY",  confidence=0.9)
        s2 = _sig(strategy="LondonBreakout", symbol="GBPUSD", action="SELL", confidence=0.75)
        result = pm.evaluate([s2, s1])
        assert result[0].confidence > result[1].confidence

    def test_record_trade_updates_state(self):
        pm = PortfolioManager(_cfg())
        pm.record_trade(_sig())
        assert pm._trades_today == 1
        assert "EURUSD" in pm._open_symbols

    def test_record_close_removes_symbol(self):
        pm = PortfolioManager(_cfg())
        pm.record_trade(_sig())
        pm.record_close("EURUSD", pnl_pct=-0.002)
        assert "EURUSD" not in pm._open_symbols

    def test_daily_loss_limit(self):
        pm = PortfolioManager(_cfg())
        pm._daily_pnl_pct = -0.016    # 1.6% loss > 1.5% limit
        assert pm.is_daily_loss_hit()

    def test_stats_output(self):
        pm = PortfolioManager(_cfg())
        pm.record_trade(_sig())
        s = pm.stats()
        assert s["trades_today"] == 1
        assert "EURUSD" in s["open_symbols"]

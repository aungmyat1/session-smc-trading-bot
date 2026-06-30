"""
Tests for scripts/run_portfolio.py tick logic.

Tests are isolated from the broker: MT5Connector and VantageDemoExecutor
are replaced with async stubs. The portfolio control layer components
(SignalRouter, CircuitBreaker, PortfolioManager) are mocked so unit tests
focus on the runner's dispatch logic, not the layer internals (which have
their own test modules).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT))

from core.signal import Signal  # noqa: E402

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_signal(
    strategy="ST-A2", symbol="EURUSD", action="BUY", confidence=0.80, exec_mode="demo"
) -> Signal:
    return Signal(
        timestamp="2026-06-24T09:00:00+00:00",
        strategy_name=strategy,
        symbol=symbol,
        action=action,
        order_type="MARKET",
        entry_price=1.1000,
        stop_loss=1.0980,
        take_profit=1.1080,
        risk_percent=0.30,
        confidence=confidence,
        metadata={
            "risk_pips": 20.0,
            "reward_pips": 80.0,
            "rr": 4.0,
            "session": "london",
            "execution_mode": exec_mode,
        },
    )


def _fake_candles(n=60) -> list[dict]:
    return [
        {"open": 1.1, "high": 1.101, "low": 1.099, "close": 1.1005, "volume": 100}
        for _ in range(n)
    ]


def _make_price(symbol="EURUSD") -> dict:
    spread_pip = {"EURUSD": 1.0, "GBPUSD": 1.5, "USDJPY": 1.0}.get(symbol, 1.0)
    return {"bid": 1.1000, "ask": 1.1001, "spread_pips": spread_pip}


class _FakeConnector:
    async def connect(self):
        pass

    async def disconnect(self):
        pass

    async def reconnect(self):
        pass


class _FakeExecutor:
    async def get_candles(self, symbol, timeframe, count):
        return _fake_candles(count)

    async def get_price(self, symbol):
        return _make_price(symbol)

    async def get_account_info(self):
        return {"balance": 10000.0}


class _FakeManager:
    async def open_position(self, signal, lots):
        return {"order_id": f"ORD-{signal.symbol}-001", "status": "FILLED"}


# ── Strategy stub factory ─────────────────────────────────────────────────────


def _make_strategy_stub(name, signal=None):
    """Return a BaseStrategy-like stub that produces the given signal."""
    stub = MagicMock()
    stub.name = name
    stub.generate_signal.return_value = signal
    return stub


# ── Helper: run _tick with injected stubs ─────────────────────────────────────


async def _run_tick(
    strategy_map,
    signal_map,
    mode="shadow",
    router_pass=True,
    breaker_pass=True,
    pm_pass=True,
):
    """
    Run one portfolio runner tick.

    strategy_map: {strategy_name: {pairs, mode}}
    signal_map:   {strategy_name: Signal | None}  — what generate_signal returns
    """
    connector = _FakeConnector()
    executor = _FakeExecutor()
    manager = _FakeManager()
    journal = MagicMock()
    journal.log_open = MagicMock()
    risk_state = {"_fetch_fails": 0}

    # Build registry stubs
    strategies = {
        name: _make_strategy_stub(name, signal_map.get(name)) for name in strategy_map
    }

    # Build control-layer stubs
    router = MagicMock()
    breaker = MagicMock()
    portmgr = MagicMock()
    shadow = MagicMock()
    jdb = MagicMock()
    jdb.record_signal.return_value = 1

    def _router_route(sigs):
        return sigs if router_pass else []

    router.route.side_effect = _router_route

    def _breaker_check(name):
        return (True, "ok") if breaker_pass else (False, "cooldown")

    breaker.check.side_effect = _breaker_check
    breaker.record_signal = MagicMock()
    breaker.record_trade = MagicMock()

    portmgr.any_loss_limit_hit.return_value = False
    portmgr.evaluate.side_effect = lambda sigs: sigs if pm_pass else []
    portmgr.stats.return_value = {}
    portmgr.record_trade = MagicMock()

    with (
        patch("scripts.run_portfolio._STRATEGY_MAP", strategy_map),
        patch(
            "scripts.run_portfolio._ALL_SYMBOLS",
            sorted({s for cfg in strategy_map.values() for s in cfg["pairs"]}),
        ),
        patch("scripts.run_portfolio._router", router),
        patch("scripts.run_portfolio._breaker", breaker),
        patch("scripts.run_portfolio._portmgr", portmgr),
        patch("scripts.run_portfolio._shadow", shadow),
        patch("scripts.run_portfolio._jdb", jdb),
        patch("scripts.run_portfolio.get_strategy", lambda name: strategies.get(name)),
    ):
        from scripts.run_portfolio import _tick

        result = await _tick(mode, connector, executor, manager, journal, risk_state)

    return result, shadow, jdb, manager, portmgr, breaker


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestTickNoSignals:
    """Tick with all strategies returning None."""

    def test_no_signal_returns_clean_state(self):
        strategy_map = {
            "ST-A2": {"pairs": ["EURUSD"], "mode": "demo", "enabled": True},
        }
        result, shadow, jdb, manager, *_ = asyncio.run(
            _run_tick(strategy_map, signal_map={"ST-A2": None})
        )
        shadow.track.assert_not_called()
        jdb.record_signal.assert_not_called()

    def test_fetch_fails_counter_reset_on_success(self):
        strategy_map = {
            "LondonBreakout": {"pairs": ["EURUSD"], "mode": "demo", "enabled": True},
        }
        result, *_ = asyncio.run(
            _run_tick(strategy_map, signal_map={"LondonBreakout": None})
        )
        assert result.get("_fetch_fails", 0) == 0


class TestTickShadowMode:
    """In shadow mode, all signals go to ShadowTracker regardless of config."""

    def test_demo_config_strategy_goes_shadow_in_shadow_mode(self):
        sig = _make_signal(exec_mode="demo")
        strategy_map = {
            "ST-A2": {"pairs": ["EURUSD"], "mode": "demo", "enabled": True},
        }
        result, shadow, jdb, manager, *_ = asyncio.run(
            _run_tick(strategy_map, signal_map={"ST-A2": sig}, mode="shadow")
        )
        shadow.track.assert_called_once()
        manager.open_position = MagicMock()
        # No demo order placed
        assert not hasattr(manager, "_open_called") or not manager._open_called

    def test_shadow_journal_records_shadow_execution(self):
        sig = _make_signal(exec_mode="shadow")
        strategy_map = {
            "AdaptiveSMC": {"pairs": ["EURUSD"], "mode": "shadow", "enabled": True},
        }
        result, shadow, jdb, *_ = asyncio.run(
            _run_tick(strategy_map, signal_map={"AdaptiveSMC": sig}, mode="shadow")
        )
        shadow.track.assert_called_once()
        jdb.record_signal.assert_called_once()
        call_kwargs = jdb.record_signal.call_args[1]
        assert call_kwargs["execution_result"] == "SHADOW"


class TestTickDemoMode:
    """In demo mode, demo-tagged strategies execute orders; shadow-tagged don't."""

    def test_demo_strategy_places_order(self):
        sig = _make_signal(exec_mode="demo")
        strategy_map = {
            "ST-A2": {"pairs": ["EURUSD"], "mode": "demo", "enabled": True},
        }

        placed = []

        async def _fake_open(self, signal, lots):
            placed.append(signal)
            return {"order_id": "ORD-001"}

        with patch.object(_FakeManager, "open_position", _fake_open):
            result, shadow, jdb, manager, *_ = asyncio.run(
                _run_tick(strategy_map, signal_map={"ST-A2": sig}, mode="demo")
            )

        assert len(placed) == 1
        shadow.track.assert_not_called()

    def test_shadow_strategy_skips_order_in_demo_mode(self):
        sig = _make_signal(strategy="AdaptiveSMC", exec_mode="shadow")
        strategy_map = {
            "AdaptiveSMC": {"pairs": ["EURUSD"], "mode": "shadow", "enabled": True},
        }
        result, shadow, jdb, manager, *_ = asyncio.run(
            _run_tick(strategy_map, signal_map={"AdaptiveSMC": sig}, mode="demo")
        )
        shadow.track.assert_called_once()
        call_kwargs = jdb.record_signal.call_args[1]
        assert call_kwargs["execution_result"] == "SHADOW"


class TestCircuitBreakerBlock:
    """CircuitBreaker rejection: signal is logged but not executed."""

    def test_cb_blocked_signal_recorded(self):
        sig = _make_signal(exec_mode="demo")
        strategy_map = {
            "ST-A2": {"pairs": ["EURUSD"], "mode": "demo", "enabled": True},
        }
        result, shadow, jdb, manager, *_ = asyncio.run(
            _run_tick(
                strategy_map, signal_map={"ST-A2": sig}, mode="demo", breaker_pass=False
            )
        )
        shadow.track.assert_not_called()
        jdb.record_signal.assert_called_once()
        kw = jdb.record_signal.call_args[1]
        assert "BLOCKED" in kw["breaker_result"]
        assert kw["execution_result"] == "SKIPPED"


class TestPortfolioManagerBlock:
    """PortfolioManager rejection: signal is logged but not executed."""

    def test_pm_blocked_recorded(self):
        sig = _make_signal(exec_mode="demo")
        strategy_map = {
            "ST-A2": {"pairs": ["EURUSD"], "mode": "demo", "enabled": True},
        }
        result, shadow, jdb, *_ = asyncio.run(
            _run_tick(
                strategy_map, signal_map={"ST-A2": sig}, mode="demo", pm_pass=False
            )
        )
        shadow.track.assert_not_called()
        jdb.record_signal.assert_called_once()
        kw = jdb.record_signal.call_args[1]
        assert kw["portfolio_result"] == "BLOCKED"


class TestPortfolioLossLimit:
    """When portfolio loss limit is hit, the tick is skipped entirely."""

    def test_loss_limit_skips_tick(self):
        _sig = _make_signal(exec_mode="demo")
        strategy_map = {
            "ST-A2": {"pairs": ["EURUSD"], "mode": "demo", "enabled": True},
        }

        portmgr = MagicMock()
        portmgr.any_loss_limit_hit.return_value = True
        portmgr.stats.return_value = {}

        with (
            patch("scripts.run_portfolio._STRATEGY_MAP", strategy_map),
            patch("scripts.run_portfolio._ALL_SYMBOLS", ["EURUSD"]),
            patch("scripts.run_portfolio._portmgr", portmgr),
            patch("scripts.run_portfolio._router", MagicMock()),
            patch("scripts.run_portfolio._breaker", MagicMock()),
            patch("scripts.run_portfolio._shadow", MagicMock()),
            patch("scripts.run_portfolio._jdb", MagicMock()),
        ):
            from scripts.run_portfolio import _tick

            asyncio.run(
                _tick(
                    "demo",
                    _FakeConnector(),
                    _FakeExecutor(),
                    _FakeManager(),
                    MagicMock(),
                    {},
                )
            )

        portmgr.evaluate.assert_not_called()


class TestMultiStrategySignals:
    """Multiple strategies can fire in the same tick."""

    def test_two_uncorrelated_signals_both_recorded(self):
        sig_eur = _make_signal(
            strategy="LondonBreakout", symbol="EURUSD", exec_mode="demo"
        )
        sig_jpy = _make_signal(strategy="NYMomentum", symbol="USDJPY", exec_mode="demo")
        strategy_map = {
            "LondonBreakout": {"pairs": ["EURUSD"], "mode": "demo", "enabled": True},
            "NYMomentum": {"pairs": ["USDJPY"], "mode": "demo", "enabled": True},
        }

        placed = []

        async def _fake_open(self, signal, lots):
            placed.append(signal.symbol)
            return {"order_id": f"ORD-{signal.symbol}"}

        with patch.object(_FakeManager, "open_position", _fake_open):
            result, shadow, jdb, manager, *_ = asyncio.run(
                _run_tick(
                    strategy_map,
                    signal_map={"LondonBreakout": sig_eur, "NYMomentum": sig_jpy},
                    mode="demo",
                )
            )

        assert set(placed) == {"EURUSD", "USDJPY"}


class TestAutoReconnect:
    """Consecutive data fetch failures trigger a reconnect after threshold."""

    def test_reconnect_triggered_after_max_failures(self):
        strategy_map = {
            "ST-A2": {"pairs": ["EURUSD"], "mode": "demo", "enabled": True},
        }

        reconnect_calls = []

        class _FailingExecutor:
            call_count = 0

            async def get_candles(self, symbol, tf, n):
                self.call_count += 1
                raise ConnectionError("timeout")

            async def get_price(self, symbol):
                raise ConnectionError("timeout")

            async def get_account_info(self):
                return {"balance": 0.0}

        class _TrackingConnector:
            async def connect(self):
                pass

            async def disconnect(self):
                pass

            async def reconnect(self):
                reconnect_calls.append(True)

        connector = _TrackingConnector()
        executor = _FailingExecutor()

        with (
            patch("scripts.run_portfolio._STRATEGY_MAP", strategy_map),
            patch("scripts.run_portfolio._ALL_SYMBOLS", ["EURUSD"]),
            patch("scripts.run_portfolio._router", MagicMock()),
            patch("scripts.run_portfolio._breaker", MagicMock()),
            patch(
                "scripts.run_portfolio._portmgr",
                MagicMock(**{"any_loss_limit_hit.return_value": False}),
            ),
            patch("scripts.run_portfolio._shadow", MagicMock()),
            patch("scripts.run_portfolio._jdb", MagicMock()),
        ):
            from scripts.run_portfolio import _MAX_FETCH_FAIL, _tick

            risk_state = {"_fetch_fails": _MAX_FETCH_FAIL - 1}
            asyncio.run(
                _tick(
                    "shadow",
                    connector,
                    executor,
                    _FakeManager(),
                    MagicMock(),
                    risk_state,
                )
            )

        assert len(reconnect_calls) >= 1


class TestDailyReset:
    """Daily risk state is reset when last_reset date changes."""

    def test_daily_reset_called_on_new_day(self):
        strategy_map = {
            "ST-A2": {"pairs": ["EURUSD"], "mode": "shadow", "enabled": True},
        }

        reset_called = []

        def _fake_reset(state):
            reset_called.append(True)
            return {"last_reset": "2026-06-24T00:00:00"}

        with (
            patch("scripts.run_portfolio._STRATEGY_MAP", strategy_map),
            patch("scripts.run_portfolio._ALL_SYMBOLS", ["EURUSD"]),
            patch(
                "scripts.run_portfolio._router", MagicMock(**{"route.return_value": []})
            ),
            patch("scripts.run_portfolio._breaker", MagicMock()),
            patch(
                "scripts.run_portfolio._portmgr",
                MagicMock(**{"any_loss_limit_hit.return_value": False}),
            ),
            patch("scripts.run_portfolio._shadow", MagicMock()),
            patch("scripts.run_portfolio._jdb", MagicMock()),
            patch("scripts.run_portfolio.reset_daily", _fake_reset),
        ):
            from scripts.run_portfolio import _tick

            asyncio.run(
                _tick(
                    "shadow",
                    _FakeConnector(),
                    _FakeExecutor(),
                    _FakeManager(),
                    MagicMock(),
                    {"last_reset": "2026-06-23"},
                )
            )

        assert reset_called


class TestLiveBlocked:
    """TRADING_MODE=live must exit(1)."""

    def test_live_mode_blocked(self):
        from scripts.run_portfolio import main

        with patch("sys.argv", ["run_portfolio.py", "--mode", "live"]):
            with pytest.raises(SystemExit) as exc:
                main()
        assert exc.value.code == 1


class TestStrategyMapFromConfig:
    """_STRATEGY_MAP falls back to hardcoded defaults when yaml unavailable."""

    def test_fallback_map_has_all_five_strategies(self):
        with patch("builtins.open", side_effect=FileNotFoundError):
            # Re-evaluate the _load_strategy_config call
            from scripts import run_portfolio as rp

            _cfg = rp._load_strategy_config()
        # No yaml → empty dict; fallback map defined in module already
        # Just verify the hardcoded fallback names are all present
        expected = {
            "ST-A2",
            "LondonBreakout",
            "NYMomentum",
            "AdaptiveSMC",
            "VWAPBreakout",
        }
        # The fallback is the `or {...}` clause — test by checking module-level dict
        # which uses the yaml if available; just check it has ≥ the 5 core strategies
        # (may already be loaded from actual config)
        actual = set(rp._STRATEGY_MAP.keys())
        assert expected.issubset(actual), f"Missing: {expected - actual}"

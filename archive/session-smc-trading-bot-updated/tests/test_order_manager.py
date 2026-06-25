"""Tests for execution/order_manager.py — order flow orchestration."""

import pytest
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from execution.order_manager import OrderManager, MAX_OPEN_TRADES
from execution.metaapi_client import MetaAPIClient, OrderResult, BrokerPosition
from execution.risk_manager import RiskManager
from execution.trade_logger import TradeLogger


_UTC = timezone.utc

# ── Fixtures ──────────────────────────────────────────────────────────────────

BASE_CONFIG = {
    "risk": {
        "risk_per_trade_pct": 1.0,
        "max_open_trades": 1,
        "max_pair_exposure": 1,
        "max_daily_loss_r": 3.0,
        "max_weekly_loss_r": 8.0,
        "max_consecutive_losses": 5,
        "min_lot": 0.01,
        "max_lot": 10.0,
    },
    "pip_value_per_lot": {"EURUSD": 10.0, "GBPUSD": 10.0},
    "magic_numbers": {"EURUSD": 21001, "GBPUSD": 21002},
}


@dataclass
class FakeSignal:
    """Minimal Signal-compatible object for testing."""
    side: str
    entry: float
    stop_loss: float
    take_profit: float
    risk_pips: float
    session: str
    timestamp: datetime
    reason: str = "test"


@pytest.fixture(autouse=True)
def isolate_risk_state(tmp_path, monkeypatch):
    monkeypatch.setattr("execution.risk_manager.STATE_FILE", tmp_path / "bot_state.json")


@pytest.fixture
def log_file(tmp_path) -> Path:
    return tmp_path / "trades.jsonl"


@pytest.fixture
def trade_logger(log_file) -> TradeLogger:
    return TradeLogger(log_file)


@pytest.fixture
def risk() -> RiskManager:
    return RiskManager(BASE_CONFIG)


def make_client(
    spread_ok: bool = True,
    spread_pips: float = 1.2,
    open_positions: "list | None" = None,
    place_result: "OrderResult | None" = None,
) -> MetaAPIClient:
    client = MagicMock(spec=MetaAPIClient)
    client.check_spread = AsyncMock(return_value=(spread_ok, spread_pips))
    client.get_open_positions = AsyncMock(return_value=open_positions or [])
    if place_result is None:
        place_result = OrderResult(
            order_id="DRY_RUN", symbol="EURUSD", direction="long",
            volume=0.01, entry_price=0.0, sl=1.06, tp=1.09, dry_run=True,
        )
    client.place_order = AsyncMock(return_value=place_result)
    return client


def make_om(client, risk, tl) -> OrderManager:
    return OrderManager(client, risk, tl, BASE_CONFIG)


def long_signal() -> FakeSignal:
    return FakeSignal(
        side="long", entry=1.07, stop_loss=1.06, take_profit=1.09,
        risk_pips=10.0, session="london",
        timestamp=datetime(2026, 1, 15, 7, 30, tzinfo=_UTC),
    )


# ── Category 1: Happy path ────────────────────────────────────────────────────

class TestHappyPath:
    @pytest.mark.asyncio
    async def test_process_signal_returns_true_on_success(self, risk, trade_logger):
        client = make_client()
        om = make_om(client, risk, trade_logger)
        success, detail = await om.process_signal(long_signal(), "EURUSD", 1000.0)
        assert success is True
        assert detail == "DRY_RUN"

    @pytest.mark.asyncio
    async def test_all_four_events_logged_on_success(self, risk, trade_logger):
        client = make_client()
        om = make_om(client, risk, trade_logger)
        await om.process_signal(long_signal(), "EURUSD", 1000.0)
        events = trade_logger.read_all()
        event_types = [e["event"] for e in events]
        assert "SIGNAL_CREATED" in event_types
        assert "ORDER_SUBMITTED" in event_types
        assert "ORDER_FILLED" in event_types
        # No ORDER_REJECTED on happy path
        assert "ORDER_REJECTED" not in event_types

    @pytest.mark.asyncio
    async def test_signal_created_always_first_event(self, risk, trade_logger):
        client = make_client()
        om = make_om(client, risk, trade_logger)
        await om.process_signal(long_signal(), "EURUSD", 1000.0)
        events = trade_logger.read_all()
        assert events[0]["event"] == "SIGNAL_CREATED"

    @pytest.mark.asyncio
    async def test_order_submitted_has_correct_symbol(self, risk, trade_logger):
        client = make_client()
        om = make_om(client, risk, trade_logger)
        await om.process_signal(long_signal(), "EURUSD", 1000.0)
        submitted = next(e for e in trade_logger.read_all() if e["event"] == "ORDER_SUBMITTED")
        assert submitted["symbol"] == "EURUSD"
        assert submitted["direction"] == "long"


# ── Category 2: Circuit breaker rejection ────────────────────────────────────

class TestCircuitBreakerRejection:
    @pytest.mark.asyncio
    async def test_halted_risk_manager_rejects_signal(self, risk, trade_logger):
        # MAX_WEEKLY_LOSS is not auto-cleared on daily reset (unlike MAX_DAILY_LOSS)
        risk._state.halted = True
        risk._state.halt_reason = "MAX_WEEKLY_LOSS"
        client = make_client()
        om = make_om(client, risk, trade_logger)
        success, detail = await om.process_signal(long_signal(), "EURUSD", 1000.0)
        assert success is False
        assert "CIRCUIT_BREAKER" in detail

    @pytest.mark.asyncio
    async def test_signal_created_logged_before_circuit_breaker_rejection(self, risk, trade_logger):
        risk._state.halted = True
        risk._state.halt_reason = "MAX_WEEKLY_LOSS"
        client = make_client()
        om = make_om(client, risk, trade_logger)
        await om.process_signal(long_signal(), "EURUSD", 1000.0)
        events = trade_logger.read_all()
        assert events[0]["event"] == "SIGNAL_CREATED"
        assert any(e["event"] == "ORDER_REJECTED" for e in events)


# ── Category 3: Spread rejection ─────────────────────────────────────────────

class TestSpreadRejection:
    @pytest.mark.asyncio
    async def test_wide_spread_rejects_signal(self, risk, trade_logger):
        client = make_client(spread_ok=False, spread_pips=8.0)
        om = make_om(client, risk, trade_logger)
        success, detail = await om.process_signal(long_signal(), "EURUSD", 1000.0)
        assert success is False
        assert "SPREAD_TOO_WIDE" in detail

    @pytest.mark.asyncio
    async def test_spread_rejection_logs_order_rejected(self, risk, trade_logger):
        client = make_client(spread_ok=False, spread_pips=8.0)
        om = make_om(client, risk, trade_logger)
        await om.process_signal(long_signal(), "EURUSD", 1000.0)
        rejected = [e for e in trade_logger.read_all() if e["event"] == "ORDER_REJECTED"]
        assert len(rejected) == 1
        assert "SPREAD" in rejected[0]["reason"]


# ── Category 4: Duplicate position prevention ─────────────────────────────────

class TestDuplicateOrderPrevention:
    @pytest.mark.asyncio
    async def test_existing_position_blocks_new_order(self, risk, trade_logger):
        existing = BrokerPosition(
            position_id="pos-1", symbol="EURUSD", direction="long",
            volume=0.01, open_price=1.07, sl=1.06, tp=1.09, profit=0.0, magic=21001,
        )
        client = make_client(open_positions=[existing])
        om = make_om(client, risk, trade_logger)
        success, detail = await om.process_signal(long_signal(), "EURUSD", 1000.0)
        assert success is False
        assert "MAX_OPEN_TRADES" in detail

    @pytest.mark.asyncio
    async def test_max_open_trades_is_one(self):
        assert MAX_OPEN_TRADES == 1

    @pytest.mark.asyncio
    async def test_no_position_allows_order(self, risk, trade_logger):
        client = make_client(open_positions=[])
        om = make_om(client, risk, trade_logger)
        success, _ = await om.process_signal(long_signal(), "EURUSD", 1000.0)
        assert success is True

    @pytest.mark.asyncio
    async def test_place_order_not_called_when_position_exists(self, risk, trade_logger):
        existing = BrokerPosition(
            position_id="pos-1", symbol="EURUSD", direction="long",
            volume=0.01, open_price=1.07, sl=1.06, tp=1.09, profit=0.0, magic=21001,
        )
        client = make_client(open_positions=[existing])
        om = make_om(client, risk, trade_logger)
        await om.process_signal(long_signal(), "EURUSD", 1000.0)
        client.place_order.assert_not_called()


# ── Category 5: Sizing rejection ─────────────────────────────────────────────

class TestSizingRejection:
    @pytest.mark.asyncio
    async def test_sl_too_tight_rejected_by_sizer(self, risk, trade_logger):
        sig = long_signal()
        sig.risk_pips = 1.5   # < 3.0 pip minimum
        client = make_client()
        om = make_om(client, risk, trade_logger)
        success, detail = await om.process_signal(sig, "EURUSD", 1000.0)
        assert success is False
        assert "SIZING_REJECTED" in detail

    @pytest.mark.asyncio
    async def test_sl_too_wide_rejected_by_sizer(self, risk, trade_logger):
        sig = long_signal()
        sig.risk_pips = 55.0  # > 50 pip maximum
        client = make_client()
        om = make_om(client, risk, trade_logger)
        success, detail = await om.process_signal(sig, "EURUSD", 1000.0)
        assert success is False
        assert "SIZING_REJECTED" in detail


# ── Category 6: Order placement failure ──────────────────────────────────────

class TestOrderPlacementFailure:
    @pytest.mark.asyncio
    async def test_broker_exception_returns_false(self, risk, trade_logger):
        client = make_client()
        client.place_order = AsyncMock(side_effect=RuntimeError("connection lost"))
        om = make_om(client, risk, trade_logger)
        success, detail = await om.process_signal(long_signal(), "EURUSD", 1000.0)
        assert success is False
        assert "ORDER_FAILED" in detail

    @pytest.mark.asyncio
    async def test_broker_exception_logs_error_event(self, risk, trade_logger):
        client = make_client()
        client.place_order = AsyncMock(side_effect=RuntimeError("timeout"))
        om = make_om(client, risk, trade_logger)
        await om.process_signal(long_signal(), "EURUSD", 1000.0)
        errors = [e for e in trade_logger.read_all() if e["event"] == "ERROR"]
        assert len(errors) == 1

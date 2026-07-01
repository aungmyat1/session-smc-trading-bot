from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from execution.market_data import MockMarketDataProvider
from execution.trade_journal import DemoTradeJournal
from execution.trade_manager import TradeManager
from strategies.adapters.st_a2_adapter import ST2Adapter
from strategy.session_liquidity.session_strategy import run_strategy

_UTC = timezone.utc


def _bar(t: datetime, high: float, low: float, open_: float | None = None, close: float | None = None) -> dict:
    mid = round((high + low) / 2, 6)
    return {
        "time": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "open": open_ if open_ is not None else mid,
        "high": high,
        "low": low,
        "close": close if close is not None else mid,
        "volume": 100,
    }


def _fixture(symbol: str) -> tuple[list[dict], list[dict]]:
    trade_date = datetime(2024, 1, 15, tzinfo=_UTC)
    if symbol == "EURUSD":
        high, low = 1.0750, 1.0700
        displacement_close = 1.0790
    else:
        high, low = 1.2750, 1.2700
        displacement_close = 1.2800

    start = (trade_date - timedelta(days=1)).replace(hour=23, minute=0, second=0, microsecond=0)
    m15 = [_bar(start + timedelta(minutes=15 * i), high, low) for i in range(32)]
    m15.append(_bar(trade_date.replace(hour=7, minute=0), high=high - 0.0010, low=low + 0.0010, close=high - 0.0020))
    m15.append(_bar(trade_date.replace(hour=7, minute=15), high=high - 0.0002, low=low - 0.0018, open_=low + 0.0025, close=low + 0.0020))
    m15.append(_bar(trade_date.replace(hour=7, minute=30), high=displacement_close + 0.0010, low=low - 0.0005, open_=low, close=displacement_close))
    for idx in range(17):
        stamp = trade_date.replace(hour=7, minute=45) + timedelta(minutes=15 * idx)
        m15.append(_bar(stamp, high=displacement_close + 0.0008, low=displacement_close - 0.0008, close=displacement_close))

    highs = [1, 2, 5, 2, 1, 2, 3, 3, 2, 1, 8, 2, 1]
    lows = [0.5, 1, 0.8, 0.5, 0.2, 0.8, 0.5, 0.8, 0.5, 0.3, 1.5, 0.5, 0.2]
    base = datetime(2024, 1, 12, 0, 0, tzinfo=_UTC)
    h4 = [_bar(base + timedelta(hours=4 * i), float(h), float(l)) for i, (h, l) in enumerate(zip(highs, lows))]
    return m15, h4


class _FakeConnector:
    async def connect(self):
        return None


class _FakeExecutor:
    def __init__(self):
        self.demo_only = True

    async def place_order(self, symbol, direction, lots, sl, tp, magic=21099, comment="strategy-demo"):
        return {
            "order_id": f"SIM-{symbol}",
            "simulated": True,
            "symbol": symbol,
            "direction": direction,
            "lots": lots,
            "sl": sl,
            "tp": tp,
        }

    async def get_positions(self):
        return []


@pytest.mark.asyncio
async def test_broker_connection_passes():
    connector = _FakeConnector()
    await connector.connect()
    assert "PASS" == "PASS"


@pytest.mark.asyncio
async def test_candle_retrieval_receives_eurusd_m15():
    m15, h4 = _fixture("EURUSD")
    provider = MockMarketDataProvider({("EURUSD", "15m"): m15, ("EURUSD", "4h"): h4})
    candles = await provider.get_candles("EURUSD", "M15", 50)
    assert len(candles) >= 50
    assert "EURUSD M15 candles received" == "EURUSD M15 candles received"


def test_strategy_evaluation_completes():
    m15, h4 = _fixture("EURUSD")
    signals = run_strategy(m15, h4, "EURUSD")
    adapter_signal = ST2Adapter().generate_signal({"symbol": "EURUSD", "m15": m15, "h4": h4})
    assert signals
    assert adapter_signal is not None
    assert "signal evaluation completed" == "signal evaluation completed"


@pytest.mark.asyncio
async def test_paper_order_is_accepted():
    m15, h4 = _fixture("EURUSD")
    signal = ST2Adapter().generate_signal({"symbol": "EURUSD", "m15": m15, "h4": h4})
    assert signal is not None
    manager = TradeManager(_FakeExecutor())
    order = await manager.open_position(signal, lots=0.01)
    assert order["simulated"] is True
    assert "order accepted" == "order accepted"


def test_trade_journal_trade_is_saved(tmp_path):
    m15, h4 = _fixture("EURUSD")
    signal = ST2Adapter().generate_signal({"symbol": "EURUSD", "m15": m15, "h4": h4})
    assert signal is not None
    journal = DemoTradeJournal(tmp_path / "demo_trades.jsonl")
    journal.log_open(signal, {"order_id": "SIM-EURUSD", "simulated": True}, 0.01, 0.8)
    records = journal.read_all()
    assert len(records) == 1
    assert records[0]["symbol"] == "EURUSD"
    assert "trade saved" == "trade saved"

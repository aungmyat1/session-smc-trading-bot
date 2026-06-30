"""Tests for the D2E3 journal-to-PostgreSQL ingestion helpers."""

from datetime import datetime, timezone

import scripts.d2e3_journal_to_db as sync_db
from scripts.d2e3_journal_to_db import (build_daily_equity, build_metrics,
                                        build_trade_records)


def _ts(value: str) -> str:
    return value.replace("Z", "+00:00")


def test_build_trade_records_correlates_fill_and_close():
    events = [
        {
            "ts": "2026-06-26T11:00:00+00:00",
            "event": "SIGNAL_CREATED",
            "symbol": "EURUSD",
            "session": "utc",
            "side": "long",
            "entry": 1.1000,
            "sl": 1.0950,
            "tp": 1.1100,
            "sl_pips": 50.0,
            "reason": "setup",
        },
        {
            "ts": "2026-06-26T11:01:00+00:00",
            "event": "ORDER_FILLED",
            "symbol": "EURUSD",
            "order_id": "ord-1",
            "entry_price": 1.1001,
            "volume": 0.01,
            "sl": 1.0950,
            "tp": 1.1100,
            "dry_run": False,
        },
        {
            "ts": "2026-06-26T11:15:00+00:00",
            "event": "POSITION_CLOSED",
            "symbol": "EURUSD",
            "position_id": "pos-1",
            "result_r": 2.4,
            "exit_reason": "TP",
        },
    ]

    trades = build_trade_records(
        [{**ev, "_ts": datetime.fromisoformat(_ts(ev["ts"]))} for ev in events]
    )

    assert len(trades) == 1
    trade = trades[0]
    assert trade["symbol"] == "EURUSD"
    assert trade["direction"] == "long"
    assert trade["order_id"] == "ord-1"
    assert trade["risk_reward"] == 1.9412
    assert trade["result_r"] == 2.4
    assert trade["trade_id"].startswith("EURUSD:")


def test_build_daily_equity_and_metrics():
    trades = [
        {
            "close_ts": datetime(2026, 6, 26, 11, tzinfo=timezone.utc),
            "result_r": 2.0,
        },
        {
            "close_ts": datetime(2026, 6, 26, 12, tzinfo=timezone.utc),
            "result_r": -1.0,
        },
        {
            "close_ts": datetime(2026, 6, 27, 10, tzinfo=timezone.utc),
            "result_r": 1.5,
        },
    ]

    equity = build_daily_equity(trades)
    metrics = build_metrics(trades)

    assert len(equity) == 2
    assert metrics["total_trades"] == 3
    assert metrics["winning_trades"] == 2
    assert metrics["losing_trades"] == 1
    assert metrics["net_r"] == 2.5
    assert metrics["profit_factor"] > 1.0


def test_sync_journal_skips_when_database_unreachable(monkeypatch, tmp_path):
    log_file = tmp_path / "d2e3_trades.jsonl"

    monkeypatch.setattr(
        sync_db,
        "load_events",
        lambda _path: [{"_ts": datetime(2026, 6, 27, 9, 0, tzinfo=timezone.utc)}],
    )
    monkeypatch.setattr(
        sync_db,
        "build_trade_records",
        lambda _events: [
            {
                "symbol": "EURUSD",
                "session": "london",
                "direction": "long",
                "signal_ts": datetime(2026, 6, 27, 9, 0, tzinfo=timezone.utc),
                "fill_ts": datetime(2026, 6, 27, 9, 1, tzinfo=timezone.utc),
                "close_ts": datetime(2026, 6, 27, 9, 15, tzinfo=timezone.utc),
                "entry_price": 1.1,
                "stop_price": 1.095,
                "take_profit": 1.11,
                "sl_pips": 50.0,
                "risk_reward": 2.0,
                "volume": 0.01,
                "order_id": "ord-1",
                "dry_run": False,
                "result_r": 1.5,
                "exit_reason": "tp",
                "signal_reason": "test",
                "trade_id": "trade-1",
            }
        ],
    )
    monkeypatch.setattr(
        sync_db.psycopg2,
        "connect",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            sync_db.psycopg2.OperationalError("Connection refused")
        ),
    )

    result = sync_db.sync_journal(
        "postgresql://user:pass@127.0.0.1:5432/research",
        log_file,
    )

    assert result["skipped"] is True
    assert result["reason"] == "research database unavailable"

"""Tests for the ST-A2 trade autopsy report."""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone

import scripts.st_a2_trade_autopsy as autopsy

_UTC = timezone.utc


def _ts(base: datetime, minutes: int) -> str:
    return (base + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_bos_quality_and_primary_cause_rules():
    assert autopsy._bos_quality("long", 1.6, 0.82) == "strong"
    assert autopsy._bos_quality("short", 1.6, 0.18) == "strong"
    assert autopsy._bos_quality("long", 1.1, 0.60) == "weak"
    assert autopsy._classify_primary_cause("new_york", 1.9, 1.8, "medium", "medium") == "large_spread"
    assert autopsy._classify_primary_cause("london", 1.0, 1.8, "weak", "medium") == "weak_BOS"
    assert autopsy._classify_primary_cause("london", 1.0, 1.8, "medium", "small") == "small_FVG"
    assert autopsy._classify_primary_cause("new_york", 1.0, 1.8, "medium", "medium") == "NY_session"
    assert autopsy._classify_primary_cause("london", 1.0, 1.8, "medium", "medium") == "random"


def test_fvg_context_and_context_building(tmp_path, monkeypatch):
    base = datetime(2024, 1, 2, 0, 0, tzinfo=_UTC)
    hist = tmp_path / "EUR_USD_M15.csv"
    header = ["time", "open", "high", "low", "close", "volume"]
    body: list[list[str]] = []
    for i in range(20):
        t = _ts(base, i * 15)
        open_ = 1.1000 + i * 0.0001
        high = open_ + 0.0004
        low = open_ - 0.0003
        close = open_ + 0.0001
        body.append([t, f"{open_:.5f}", f"{high:.5f}", f"{low:.5f}", f"{close:.5f}", "100"])

    # Force a bullish FVG around index 15 (prev.high < next.low).
    body[14][2] = "1.10180"
    body[16][3] = "1.10230"
    body[16][4] = "1.10240"

    with hist.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(body)

    monkeypatch.setitem(autopsy.HISTORICAL_FILES, "EURUSD", hist)

    trades = tmp_path / "trades.csv"
    with trades.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "trade_id", "run_id", "timestamp_utc", "symbol", "session", "side",
            "entry", "stop_loss", "take_profit", "sl_pips", "rr", "exit_price",
            "exit_reason", "bars_held", "gross_r", "spread_cost_r", "net_r",
            "asian_high", "asian_low", "asian_range_pips", "htf_bias",
            "sweep_bar_time", "displacement_bar_time", "notes",
        ])
        writer.writerow([
            "T1", autopsy.CANONICAL_RUN_ID, _ts(base, 15 * 15), "EURUSD", "london", "long",
            "1.10100", "1.10000", "1.10600", "10.0", "5.0", "1.10000", "sl",
            "4", "-1.0", "0.10", "-1.10", "1.11000", "1.09000", "20.0",
            "bullish", _ts(base, 5 * 15), _ts(base, 15 * 15), "",
        ])

    rows = autopsy._load_trade_rows(trades, autopsy.CANONICAL_RUN_ID, 5.0)
    contexts = autopsy._build_contexts(rows)
    assert len(contexts) == 1
    ctx = contexts[0]
    assert ctx.atr_pips is not None and ctx.atr_pips > 0
    assert ctx.fvg_size_pips is not None
    assert ctx.sweep_type == "bullish"
    assert ctx.primary_cause in {"large_spread", "weak_BOS", "small_FVG", "NY_session", "random"}

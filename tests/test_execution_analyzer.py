"""Tests for research/execution_analyzer.py — RESEARCH-05 execution quality metrics."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from research.execution_analyzer import (
    load_bot_log_disconnects,
    _extract_latency_pairs,
    compute_signal_to_order_latency,
    compute_order_to_fill_latency,
    compute_fill_to_close_duration,
    compute_slippage_distribution,
    compute_spread_distribution,
    compute_execution_failures,
    compute_reconnect_during_trade,
    compute_duplicate_signal_attempts,
    _percentile,
    run,
)

_UTC = timezone.utc


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ts(s: str) -> datetime:
    """Parse 'YYYY-MM-DD HH:MM:SS' → UTC datetime."""
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=_UTC)


def _ev(event: str, ts_str: str, **fields) -> dict:
    """Build a synthetic event dict with _ts already set (as load_events would do)."""
    return {"event": event, "_ts": _ts(ts_str), "ts": ts_str + "+00:00", **fields}


def _sig(ts_str: str, sym: str = "EURUSD", side: str = "buy",
         entry: float = 1.0850, sess: str = "london", sl_pips: float = 10.0) -> dict:
    return _ev("SIGNAL_CREATED", ts_str, symbol=sym, side=side, entry=entry,
               session=sess, sl=entry - 0.0010, tp=entry + 0.0040, sl_pips=sl_pips)


def _sub(ts_str: str, sym: str = "EURUSD", side: str = "buy",
         sess: str = "london", dry_run: bool = True) -> dict:
    return _ev("ORDER_SUBMITTED", ts_str, symbol=sym, direction=side,
               session=sess, volume=0.01, lots=0.01, equity=10000.0,
               sl=1.0840, tp=1.0890, risk_pct=0.01, dry_run=dry_run)


def _fill(ts_str: str, sym: str = "EURUSD", entry_price: float = 1.0852,
          dry_run: bool = True) -> dict:
    return _ev("ORDER_FILLED", ts_str, symbol=sym, order_id="ORD001",
               entry_price=entry_price, volume=0.01,
               sl=1.0840, tp=1.0890, dry_run=dry_run)


def _close(ts_str: str, sym: str = "EURUSD", result_r: float = 4.0,
           exit_reason: str = "tp2") -> dict:
    return _ev("POSITION_CLOSED", ts_str, symbol=sym, position_id="POS001",
               result_r=result_r, exit_reason=exit_reason)


def _rej(ts_str: str, sym: str = "EURUSD", reason: str = "SPREAD_TOO_WIDE:3.5pip",
         side: str = "buy") -> dict:
    return _ev("ORDER_REJECTED", ts_str, symbol=sym, reason=reason, side=side)


def _err(ts_str: str, sym: str = "EURUSD", msg: str = "timeout",
         ctx: str = "place_order") -> dict:
    return _ev("ERROR", ts_str, symbol=sym, error=msg, context=ctx)


def _trade(
    sym: str = "EURUSD",
    fill_ts: str = "2026-06-22 08:00:00",
    close_ts: str = "2026-06-22 09:30:00",
    result_r: float = 4.0,
    exit_reason: str = "tp2",
    slippage_pips: float = 0.2,
    side: str = "buy",
    hold_minutes: float = 90.0,
) -> dict:
    return {
        "symbol": sym,
        "fill_ts": _ts(fill_ts),
        "close_ts": _ts(close_ts) if close_ts else None,
        "result_r": result_r,
        "exit_reason": exit_reason,
        "slippage_pips": slippage_pips,
        "side": side,
        "hold_minutes": hold_minutes,
        "session": "london",
        "entry_signal": 1.0850,
        "entry_fill": 1.0852,
    }


# ── § Percentile helper ───────────────────────────────────────────────────────

class TestPercentile:
    def test_empty_returns_none(self):
        assert _percentile([], 50) is None

    def test_single_value_all_percentiles(self):
        assert _percentile([5.0], 0) == 5.0
        assert _percentile([5.0], 50) == 5.0
        assert _percentile([5.0], 100) == 5.0

    def test_two_values_median_interpolated(self):
        result = _percentile([0.0, 10.0], 50)
        assert result == pytest.approx(5.0, abs=0.01)

    def test_p95_with_known_data(self):
        vals = list(range(100))   # 0–99
        # p95 at index 94.05 → 94.0 + 0.05×(95−94) = 94.05
        result = _percentile(vals, 95)
        assert result == pytest.approx(94.05, abs=0.01)


# ── § Bot log disconnect parsing ──────────────────────────────────────────────

class TestLoadBotLogDisconnects:
    def test_empty_log_returns_empty(self, tmp_path):
        p = tmp_path / "bot.log"
        p.write_text("")
        assert load_bot_log_disconnects(p) == []

    def test_missing_file_returns_empty(self, tmp_path):
        assert load_bot_log_disconnects(tmp_path / "missing.log") == []

    def test_connected_heartbeat_not_returned(self, tmp_path):
        p = tmp_path / "bot.log"
        p.write_text(
            "2026-06-22 08:00:00,000  INFO  bot  [HEARTBEAT] 2026-06-22T08:00 UTC\n"
            "uptime=300s  connection_status=CONNECTED  live=False\n"
            "balance=100000.00  equity=100000.00  open_positions=0\n"
        )
        assert load_bot_log_disconnects(p) == []

    def test_disconnected_heartbeat_returned(self, tmp_path):
        p = tmp_path / "bot.log"
        p.write_text(
            "2026-06-22 09:15:00,000  INFO  bot  [HEARTBEAT] 2026-06-22T09:15 UTC\n"
            "uptime=600s  connection_status=DISCONNECTED  live=False\n"
            "balance=100000.00  equity=100000.00  open_positions=0\n"
        )
        result = load_bot_log_disconnects(p)
        assert len(result) == 1
        assert result[0] == _ts("2026-06-22 09:15:00")

    def test_multiple_disconnects_all_returned(self, tmp_path):
        p = tmp_path / "bot.log"
        content = (
            "2026-06-22 08:00:00,000  INFO  bot  [HEARTBEAT] ...\n"
            "connection_status=CONNECTED\n"
            "2026-06-22 08:05:00,000  INFO  bot  [HEARTBEAT] ...\n"
            "connection_status=DISCONNECTED\n"
            "2026-06-22 08:10:00,000  INFO  bot  [HEARTBEAT] ...\n"
            "connection_status=DISCONNECTED\n"
        )
        p.write_text(content)
        result = load_bot_log_disconnects(p)
        assert len(result) == 2

    def test_non_heartbeat_lines_ignored(self, tmp_path):
        p = tmp_path / "bot.log"
        p.write_text(
            "2026-06-22 08:00:00,000  WARNING  bot  connection_status=DISCONNECTED (not in HB)\n"
        )
        assert load_bot_log_disconnects(p) == []


# ── § Latency extraction ──────────────────────────────────────────────────────

class TestExtractLatencyPairs:
    def test_signal_to_order_latency_computed(self):
        events = [
            _sig("2026-06-22 08:00:00"),
            _sub("2026-06-22 08:00:00", dry_run=False),  # 0.2s after
        ]
        # Both share the same second, delta = 0
        pairs = _extract_latency_pairs(events)
        assert len(pairs["sig_to_order_s"]) == 1
        assert pairs["sig_to_order_s"][0] == pytest.approx(0.0, abs=1.0)

    def test_latency_is_sub_second_precise(self):
        # Manually build events with _ts offset
        sig = _sig("2026-06-22 08:00:00")
        sub = _sub("2026-06-22 08:00:00")
        # Manually shift sub ts by 0.3s
        from datetime import timedelta
        sub["_ts"] = sig["_ts"] + timedelta(seconds=0.3)
        pairs = _extract_latency_pairs([sig, sub])
        assert pairs["sig_to_order_s"][0] == pytest.approx(0.3, abs=0.001)

    def test_rejection_clears_pending_signal(self):
        events = [
            _sig("2026-06-22 08:00:00"),
            _rej("2026-06-22 08:00:00"),
        ]
        pairs = _extract_latency_pairs(events)
        assert pairs["sig_to_order_s"] == []

    def test_order_to_fill_latency_computed(self):
        from datetime import timedelta
        sub = _sub("2026-06-22 08:00:00")
        fill = _fill("2026-06-22 08:00:00")
        fill["_ts"] = sub["_ts"] + timedelta(seconds=0.25)
        pairs = _extract_latency_pairs([_sig("2026-06-22 08:00:00"), sub, fill])
        assert len(pairs["ord_to_fill_s"]) == 1
        assert pairs["ord_to_fill_s"][0] == pytest.approx(0.25, abs=0.001)

    def test_no_events_returns_empty_lists(self):
        pairs = _extract_latency_pairs([])
        assert pairs["sig_to_order_s"] == []
        assert pairs["ord_to_fill_s"] == []


# ── § signal_to_order_latency ─────────────────────────────────────────────────

class TestSignalToOrderLatency:
    def test_no_submissions_returns_no_samples(self):
        events = [_sig("2026-06-22 08:00:00"), _rej("2026-06-22 08:00:01")]
        result = compute_signal_to_order_latency(events)
        assert result["status"] == "no_samples"

    def test_dry_run_count_tracked(self):
        from datetime import timedelta
        sig = _sig("2026-06-22 08:00:00")
        sub = _sub("2026-06-22 08:00:00", dry_run=True)
        sub["_ts"] = sig["_ts"] + timedelta(seconds=0.1)
        fill = _fill("2026-06-22 08:00:00")
        fill["_ts"] = sub["_ts"] + timedelta(seconds=0.15)
        result = compute_signal_to_order_latency([sig, sub, fill])
        assert result["samples"] == 1
        # dry_run in ORDER_SUBMITTED defaults to whatever we pass
        assert result["dry_run_samples"] == 1


# ── § order_to_fill_latency ───────────────────────────────────────────────────

class TestOrderToFillLatency:
    def test_no_fills_returns_no_samples(self):
        result = compute_order_to_fill_latency([_rej("2026-06-22 08:00:00")])
        assert result.get("samples", 0) == 0 or result.get("status") == "no_samples"

    def test_avg_computed_correctly(self):
        from datetime import timedelta
        # Two fills with 200ms and 400ms order→fill latency
        e1_sig = _sig("2026-06-22 08:00:00", sym="EURUSD")
        e1_sub = _sub("2026-06-22 08:00:00", sym="EURUSD")
        e1_fill = _fill("2026-06-22 08:00:00", sym="EURUSD")
        e1_sub["_ts"] = e1_sig["_ts"] + timedelta(seconds=0.05)
        e1_fill["_ts"] = e1_sub["_ts"] + timedelta(seconds=0.2)

        e2_sig = _sig("2026-06-22 09:00:00", sym="GBPUSD")
        e2_sub = _sub("2026-06-22 09:00:00", sym="GBPUSD")
        e2_fill = _fill("2026-06-22 09:00:00", sym="GBPUSD")
        e2_sub["_ts"] = e2_sig["_ts"] + timedelta(seconds=0.05)
        e2_fill["_ts"] = e2_sub["_ts"] + timedelta(seconds=0.4)

        result = compute_order_to_fill_latency(
            [e1_sig, e1_sub, e1_fill, e2_sig, e2_sub, e2_fill]
        )
        assert result["samples"] == 2
        assert result["avg_ms"] == pytest.approx(300.0, abs=1.0)


# ── § fill_to_close_duration ─────────────────────────────────────────────────

class TestFillToCloseDuration:
    def test_no_closed_trades_returns_status(self):
        # Open trade (no close_ts, result_r=None)
        result = compute_fill_to_close_duration([_trade(close_ts=None, result_r=None,
                                                        hold_minutes=None)])
        assert result.get("status") == "no_closed_trades"

    def test_avg_hold_time_correct(self):
        trades = [
            _trade(hold_minutes=60.0, exit_reason="sl"),
            _trade(hold_minutes=120.0, exit_reason="tp2"),
        ]
        result = compute_fill_to_close_duration(trades)
        assert result["avg_minutes"] == pytest.approx(90.0, abs=0.1)
        assert result["min_minutes"] == 60.0
        assert result["max_minutes"] == 120.0

    def test_by_exit_reason_breakdown(self):
        trades = [
            _trade(hold_minutes=45.0, exit_reason="sl"),
            _trade(hold_minutes=90.0, exit_reason="tp2"),
            _trade(hold_minutes=100.0, exit_reason="tp2"),
        ]
        result = compute_fill_to_close_duration(trades)
        assert result["by_exit_reason"]["sl"]["count"] == 1
        assert result["by_exit_reason"]["tp2"]["count"] == 2
        assert result["by_exit_reason"]["tp2"]["avg_minutes"] == pytest.approx(95.0, abs=0.1)

    def test_percentiles_in_output(self):
        trades = [_trade(hold_minutes=float(m)) for m in [10, 20, 30, 40, 50]]
        result = compute_fill_to_close_duration(trades)
        assert "p25_minutes" in result
        assert "p50_minutes" in result
        assert "p75_minutes" in result
        assert "p95_minutes" in result
        assert result["p50_minutes"] == pytest.approx(30.0, abs=0.1)


# ── § slippage_distribution ───────────────────────────────────────────────────

class TestSlippageDistribution:
    def test_no_fills_returns_status(self):
        result = compute_slippage_distribution([])
        assert result["status"] == "no_fills_yet"
        assert result["samples"] == 0

    def test_adverse_and_favourable_counted(self):
        trades = [
            _trade(slippage_pips=0.5, side="buy"),    # adverse for LONG
            _trade(slippage_pips=-0.3, side="buy"),   # favourable for LONG
            _trade(slippage_pips=0.0, side="sell"),   # zero
        ]
        result = compute_slippage_distribution(trades)
        assert result["adverse_count"] == 1
        assert result["favourable_count"] == 1
        assert result["zero_count"] == 1

    def test_by_symbol_breakdown_present(self):
        trades = [
            _trade(sym="EURUSD", slippage_pips=0.2),
            _trade(sym="GBPUSD", slippage_pips=0.4),
        ]
        result = compute_slippage_distribution(trades)
        assert "EURUSD" in result["by_symbol"]
        assert "GBPUSD" in result["by_symbol"]

    def test_by_side_breakdown_present(self):
        trades = [
            _trade(side="buy", slippage_pips=0.3),
            _trade(side="sell", slippage_pips=-0.2),
        ]
        result = compute_slippage_distribution(trades)
        assert "buy" in result["by_side"]
        assert "sell" in result["by_side"]

    def test_percentiles_in_output(self):
        trades = [_trade(slippage_pips=float(i)) for i in range(5)]
        result = compute_slippage_distribution(trades)
        assert "p25_pips" in result
        assert "p50_pips" in result
        assert "p75_pips" in result
        assert "p95_pips" in result


# ── § spread_distribution ─────────────────────────────────────────────────────

class TestSpreadDistribution:
    def test_fill_spread_documented_as_not_logged(self):
        result = compute_spread_distribution([])
        assert result["fills"]["status"] == "NOT_LOGGED_FOR_FILLS"

    def test_spread_too_wide_rejection_parsed(self):
        events = [
            _sig("2026-06-22 08:00:00", sym="EURUSD", sess="london"),
            _rej("2026-06-22 08:00:01", sym="EURUSD",
                 reason="SPREAD_TOO_WIDE:3.5pip"),
        ]
        result = compute_spread_distribution(events)
        assert "EURUSD" in result["rejections_by_symbol"]
        assert result["rejections_by_symbol"]["EURUSD"]["count"] == 1
        assert result["rejections_by_symbol"]["EURUSD"]["avg_pip"] == pytest.approx(3.5, abs=0.01)

    def test_rejection_rate_by_session(self):
        events = [
            _sig("2026-06-22 08:00:00", sym="EURUSD", sess="london"),
            _rej("2026-06-22 08:00:01", sym="EURUSD",
                 reason="SPREAD_TOO_WIDE:3.0pip"),
            _sig("2026-06-22 08:05:00", sym="EURUSD", sess="london"),
            _sub("2026-06-22 08:05:01", sym="EURUSD"),
        ]
        result = compute_spread_distribution(events)
        london = result["rejection_rate_by_session"].get("london", {})
        assert london["signals"] == 2
        assert london["spread_rejects"] == 1
        assert london["reject_rate"] == pytest.approx(0.5, abs=0.01)

    def test_non_spread_rejections_not_counted_in_spread(self):
        events = [
            _sig("2026-06-22 08:00:00"),
            _rej("2026-06-22 08:00:01", reason="MAX_OPEN_TRADES:1/1"),
        ]
        result = compute_spread_distribution(events)
        assert result["rejections_by_symbol"] == {}


# ── § execution_failures ─────────────────────────────────────────────────────

class TestExecutionFailures:
    def test_empty_events_all_zeros(self):
        result = compute_execution_failures([])
        assert result["signals_processed"] == 0
        assert result["orders_filled"] == 0
        assert result["orders_rejected"] == 0
        assert result["fill_rate"] is None

    def test_fill_and_reject_rates_sum_to_one(self):
        events = [
            _sig("2026-06-22 08:00:00"),
            _sub("2026-06-22 08:00:01"),
            _fill("2026-06-22 08:00:02"),
            _sig("2026-06-22 08:05:00"),
            _rej("2026-06-22 08:05:01", reason="SPREAD_TOO_WIDE:3.0pip"),
        ]
        result = compute_execution_failures(events)
        assert result["fill_rate"] + result["reject_rate"] == pytest.approx(1.0, abs=0.001)

    def test_by_reason_normalises_variable_suffix(self):
        events = [
            _sig("2026-06-22 08:00:00"),
            _rej("2026-06-22 08:00:01", reason="MAX_OPEN_TRADES:1/1"),
        ]
        result = compute_execution_failures(events)
        # Colon suffix stripped → key is "MAX_OPEN_TRADES"
        assert "MAX_OPEN_TRADES" in result["by_reason"]

    def test_error_events_counted(self):
        events = [
            _err("2026-06-22 08:00:00", ctx="place_order"),
            _err("2026-06-22 08:01:00", ctx="get_positions"),
        ]
        result = compute_execution_failures(events)
        assert result["errors"]["count"] == 2
        assert "place_order" in result["errors"]["by_context"]
        assert result["errors"]["by_context"]["place_order"] == 1

    def test_circuit_breaker_rejection_categorised(self):
        events = [
            _sig("2026-06-22 08:00:00"),
            _rej("2026-06-22 08:00:01", reason="CIRCUIT_BREAKER:daily_loss"),
        ]
        result = compute_execution_failures(events)
        assert "CIRCUIT_BREAKER" in result["by_reason"]


# ── § reconnect_during_trade ──────────────────────────────────────────────────

class TestReconnectDuringTrade:
    def test_no_disconnects_no_affected_trades(self):
        trades = [_trade()]
        result = compute_reconnect_during_trade(trades, [])
        assert result["trades_with_disconnect"] == 0
        assert result["total_disconnects_in_period"] == 0
        assert result["trades_checked"] == 1

    def test_disconnect_inside_trade_window_flagged(self):
        trade = _trade(fill_ts="2026-06-22 08:00:00", close_ts="2026-06-22 09:30:00")
        disconnect = _ts("2026-06-22 08:45:00")
        result = compute_reconnect_during_trade([trade], [disconnect])
        assert result["trades_with_disconnect"] == 1
        assert len(result["details"]) == 1
        assert result["details"][0]["disconnect_count"] == 1

    def test_disconnect_outside_trade_window_not_flagged(self):
        trade = _trade(fill_ts="2026-06-22 08:00:00", close_ts="2026-06-22 09:30:00")
        disconnect_before = _ts("2026-06-22 07:00:00")
        disconnect_after = _ts("2026-06-22 10:00:00")
        result = compute_reconnect_during_trade(
            [trade], [disconnect_before, disconnect_after]
        )
        assert result["trades_with_disconnect"] == 0

    def test_multiple_disconnects_within_same_trade(self):
        trade = _trade(fill_ts="2026-06-22 08:00:00", close_ts="2026-06-22 09:30:00")
        disconnects = [
            _ts("2026-06-22 08:15:00"),
            _ts("2026-06-22 09:00:00"),
        ]
        result = compute_reconnect_during_trade([trade], disconnects)
        assert result["trades_with_disconnect"] == 1
        assert result["details"][0]["disconnect_count"] == 2

    def test_open_trade_no_close_ts_still_checked(self):
        # Trade with no close_ts (still open) — disconnect during it should flag
        trade = _trade(fill_ts="2026-06-22 08:00:00", close_ts=None,
                       result_r=None, hold_minutes=None)
        disconnect = _ts("2026-06-22 09:00:00")
        result = compute_reconnect_during_trade([trade], [disconnect])
        assert result["trades_with_disconnect"] == 1


# ── § duplicate_signal_attempts ───────────────────────────────────────────────

class TestDuplicateSignalAttempts:
    def test_no_duplicates_when_all_unique_entries(self):
        events = [
            _sig("2026-06-22 08:00:00", entry=1.0850),
            _sig("2026-06-22 08:10:00", entry=1.0870),  # different entry
        ]
        result = compute_duplicate_signal_attempts(events)
        assert result["detected"] == 0

    def test_same_entry_within_120s_flagged(self):
        from datetime import timedelta
        sig1 = _sig("2026-06-22 08:00:00", entry=1.0850, sym="EURUSD",
                    sess="london", side="buy")
        sig2 = _sig("2026-06-22 08:00:00", entry=1.0850, sym="EURUSD",
                    sess="london", side="buy")
        sig2["_ts"] = sig1["_ts"] + timedelta(seconds=60)
        result = compute_duplicate_signal_attempts([sig1, sig2])
        assert result["detected"] == 1
        assert result["details"][0]["symbol"] == "EURUSD"
        assert result["details"][0]["delta_seconds"] == pytest.approx(60.0, abs=0.1)

    def test_same_entry_different_session_not_flagged(self):
        sig1 = _sig("2026-06-22 08:00:00", entry=1.0850, sess="london")
        sig2 = _sig("2026-06-22 13:00:00", entry=1.0850, sess="newyork")
        result = compute_duplicate_signal_attempts([sig1, sig2])
        assert result["detected"] == 0

    def test_entry_within_half_pip_flagged(self):
        from datetime import timedelta
        sig1 = _sig("2026-06-22 08:00:00", entry=1.08500)
        sig2 = _sig("2026-06-22 08:00:00", entry=1.08503)  # 0.3pip diff < 0.5pip
        sig2["_ts"] = sig1["_ts"] + timedelta(seconds=30)
        result = compute_duplicate_signal_attempts([sig1, sig2])
        assert result["detected"] == 1

    def test_entry_beyond_half_pip_not_flagged(self):
        from datetime import timedelta
        sig1 = _sig("2026-06-22 08:00:00", entry=1.08500)
        sig2 = _sig("2026-06-22 08:00:00", entry=1.08560)  # 0.6pip diff > 0.5pip
        sig2["_ts"] = sig1["_ts"] + timedelta(seconds=30)
        result = compute_duplicate_signal_attempts([sig1, sig2])
        assert result["detected"] == 0

    def test_beyond_120s_not_flagged(self):
        from datetime import timedelta
        sig1 = _sig("2026-06-22 08:00:00", entry=1.0850)
        sig2 = _sig("2026-06-22 08:00:00", entry=1.0850)
        sig2["_ts"] = sig1["_ts"] + timedelta(seconds=121)
        result = compute_duplicate_signal_attempts([sig1, sig2])
        assert result["detected"] == 0


# ── § Integration smoke test ──────────────────────────────────────────────────

class TestRunIntegration:
    """End-to-end test: write synthetic JSONL, call run(), verify output files."""

    def _write_trades_jsonl(self, path: Path) -> None:
        now_str = "2026-06-22T08:00:00+00:00"
        records = [
            {"ts": "2026-06-22T08:00:00+00:00", "event": "SIGNAL_CREATED",
             "symbol": "EURUSD", "session": "london", "side": "buy",
             "entry": 1.0850, "sl": 1.0840, "tp": 1.0890, "sl_pips": 10.0, "reason": "sweep"},
            {"ts": "2026-06-22T08:00:01+00:00", "event": "ORDER_SUBMITTED",
             "symbol": "EURUSD", "session": "london", "direction": "buy",
             "volume": 0.01, "sl": 1.0840, "tp": 1.0890,
             "lots": 0.01, "equity": 10000.0, "risk_pct": 0.01, "dry_run": True},
            {"ts": "2026-06-22T08:00:02+00:00", "event": "ORDER_FILLED",
             "symbol": "EURUSD", "order_id": "ORD001", "entry_price": 1.0851,
             "volume": 0.01, "sl": 1.0840, "tp": 1.0890, "dry_run": True},
            {"ts": "2026-06-22T09:30:00+00:00", "event": "POSITION_CLOSED",
             "symbol": "EURUSD", "position_id": "POS001",
             "result_r": 4.0, "exit_reason": "tp2"},
            {"ts": "2026-06-22T08:05:00+00:00", "event": "SIGNAL_CREATED",
             "symbol": "GBPUSD", "session": "london", "side": "sell",
             "entry": 1.2700, "sl": 1.2710, "tp": 1.2650, "sl_pips": 10.0, "reason": "sweep"},
            {"ts": "2026-06-22T08:05:01+00:00", "event": "ORDER_REJECTED",
             "symbol": "GBPUSD", "reason": "SPREAD_TOO_WIDE:4.2pip", "side": "sell"},
        ]
        with path.open("w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

    def test_run_creates_daily_output(self, tmp_path):
        trade_log = tmp_path / "trades.jsonl"
        bot_log = tmp_path / "bot.log"
        bot_log.write_text("")
        daily_out = tmp_path / "execution_daily.json"
        weekly_out = tmp_path / "execution_weekly.json"
        self._write_trades_jsonl(trade_log)

        from unittest.mock import patch
        import research.execution_analyzer as ea

        # Run with patched output paths
        now = datetime(2026, 6, 22, 10, 0, 0, tzinfo=_UTC)
        with (
            patch.object(ea, "_DAILY_OUT", daily_out),
            patch.object(ea, "_WEEKLY_OUT", weekly_out),
        ):
            daily, weekly = run(
                write_daily=True,
                write_weekly=True,
                log_file=trade_log,
                bot_log=bot_log,
                now=now,
                quiet=True,
            )

        assert daily_out.exists()
        assert weekly_out.exists()

        d = json.loads(daily_out.read_text())
        assert d["period"] == "daily"
        assert d["label"] == "2026-06-22"
        # One fill → one latency sample
        assert d["signal_to_order_latency"]["samples"] == 1
        assert d["order_to_fill_latency"]["samples"] == 1
        # One closed trade
        assert d["fill_to_close_duration"]["samples"] == 1
        # GBPUSD spread rejection logged
        assert "GBPUSD" in d["spread_distribution"]["rejections_by_symbol"]
        # Two signals total
        assert d["execution_failures"]["signals_processed"] == 2
        assert d["execution_failures"]["orders_filled"] == 1
        assert d["execution_failures"]["orders_rejected"] == 1

    def test_run_with_empty_log_no_crash(self, tmp_path):
        trade_log = tmp_path / "empty.jsonl"
        trade_log.write_text("")
        bot_log = tmp_path / "bot.log"
        bot_log.write_text("")
        daily_out = tmp_path / "ex_daily.json"
        weekly_out = tmp_path / "ex_weekly.json"

        import research.execution_analyzer as ea
        from unittest.mock import patch

        now = datetime(2026, 6, 22, 10, 0, 0, tzinfo=_UTC)
        with (
            patch.object(ea, "_DAILY_OUT", daily_out),
            patch.object(ea, "_WEEKLY_OUT", weekly_out),
        ):
            daily, _ = run(
                write_daily=True,
                write_weekly=False,
                log_file=trade_log,
                bot_log=bot_log,
                now=now,
                quiet=True,
            )

        assert daily["execution_failures"]["signals_processed"] == 0
        assert daily["reconnect_during_trade"]["trades_checked"] == 0

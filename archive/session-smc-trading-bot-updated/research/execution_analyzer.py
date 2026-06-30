#!/usr/bin/env python3
"""
RESEARCH-05 Execution Quality Analyzer.

Reads logs/trades.jsonl and logs/bot.log and emits:
    logs/execution_summary_daily.json    — execution metrics for the current UTC day
    logs/execution_summary_weekly.json   — execution metrics for the current ISO week

Usage:
    python3 research/execution_analyzer.py
    python3 research/execution_analyzer.py --daily
    python3 research/execution_analyzer.py --weekly
    python3 research/execution_analyzer.py --log <path> --botlog <path>
    python3 research/execution_analyzer.py --quiet

No strategy modifications. No execution modifications. Read-only.

Metrics
-------
signal_to_order_latency   SIGNAL_CREATED → ORDER_SUBMITTED gap (includes async
                          spread + position checks; DRY_RUN rounds to ≥0 ms)
order_to_fill_latency     ORDER_SUBMITTED → ORDER_FILLED gap (broker round-trip;
                          DRY_RUN fills are simulated so latency is bot overhead only)
fill_to_close_duration    ORDER_FILLED → POSITION_CLOSED in minutes, by exit_reason
slippage_distribution     (fill_price − signal_entry) × 10000 pips, with percentiles
spread_distribution       Spreads at rejection time (SPREAD_TOO_WIDE); fill spread
                          is NOT_LOGGED (not written to ORDER_SUBMITTED)
execution_failures        All ORDER_REJECTED by reason category + ERROR events
reconnect_during_trade    Heartbeat-based: DISCONNECTED events inside a trade window
duplicate_signal_attempts Near-duplicate SIGNAL_CREATED (same symbol/side/entry ±0.5pip
                          within 120 s) — indicates post-restart re-submission

Known gaps
----------
spread_at_fill            Not logged. Fix: add spread_pips to order_submitted() call.
sub-5min disconnects      Reconnect detection is heartbeat-granularity (5 min).
signal_bar_ts             Not logged in SIGNAL_CREATED; dedup relies on bar ts
                          inside bot.py (seen_signals). Log-based dedup detection
                          uses entry-price proximity as a proxy.
"""

import argparse
import json
import re
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# Allow `python3 research/execution_analyzer.py` from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import shared helpers from live_trade_analyzer (same research package)
from research.live_trade_analyzer import (
    load_events,
    build_trades,
    filter_period,
    daily_window,
    weekly_window,
)

_ROOT = Path(__file__).parent.parent
_TRADE_LOG = _ROOT / "logs" / "trades.jsonl"
_BOT_LOG = _ROOT / "logs" / "bot.log"
_DAILY_OUT = _ROOT / "logs" / "execution_summary_daily.json"
_WEEKLY_OUT = _ROOT / "logs" / "execution_summary_weekly.json"
_UTC = timezone.utc

_PIP_MUL: dict = {"EURUSD": 10_000.0, "GBPUSD": 10_000.0}

# Latency alert thresholds
_LATENCY_WARN_MS = 2_000  # warn if avg signal→order > 2 s (unusually slow)
_FILL_LATENCY_WARN_MS = 5_000  # warn if avg order→fill > 5 s

# Duplicate detection: entry must match within 0.5 pip, within 2× poll interval
_DUP_ENTRY_TOL_PIP = 0.5
_DUP_TIME_TOL_S = 120


# ── Percentile helper ─────────────────────────────────────────────────────────


def _percentile(values: list, p: float) -> Optional[float]:
    """
    Linear-interpolation percentile. p is 0–100.
    Returns None for empty input.
    """
    if not values:
        return None
    sv = sorted(values)
    n = len(sv)
    idx = p / 100.0 * (n - 1)
    lo = int(idx)
    hi = lo + 1
    if hi >= n:
        return round(sv[lo], 4)
    return round(sv[lo] + (idx - lo) * (sv[hi] - sv[lo]), 4)


def _latency_stats(seconds: list, dry_run_flags: list) -> dict:
    """
    Convert a list of latency samples (seconds) to a stats dict.
    Values are reported in milliseconds for readability.
    """
    if not seconds:
        return {"status": "no_samples", "samples": 0}
    ms = [round(s * 1000, 1) for s in seconds]
    dry_count = sum(1 for f in dry_run_flags if f)
    return {
        "avg_ms": round(statistics.mean(ms), 1),
        "min_ms": round(min(ms), 1),
        "max_ms": round(max(ms), 1),
        "p50_ms": _percentile(ms, 50),
        "p95_ms": _percentile(ms, 95),
        "samples": len(ms),
        "dry_run_samples": dry_count,
        "live_samples": len(ms) - dry_count,
    }


def _mean(values: list) -> Optional[float]:
    return round(statistics.mean(values), 4) if values else None


# ── Bot log parsing ───────────────────────────────────────────────────────────

_TS_PAT = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")


def load_bot_log_disconnects(bot_log: Path = _BOT_LOG) -> list:
    """
    Parse bot.log for HEARTBEAT blocks containing connection_status=DISCONNECTED.

    Returns list of datetime (UTC) when a disconnect was observed.
    Detection granularity = heartbeat interval (5 min); sub-5-min disconnects
    will be missed.

    Heartbeat block format in bot.log:
        2026-06-21 18:31:44,939  INFO  bot  [HEARTBEAT] 2026-06-21T18:31 UTC
        uptime=307s  connection_status=CONNECTED  live=False
        ...
    """
    if not bot_log.exists():
        return []

    lines = bot_log.read_text(encoding="utf-8").splitlines()
    disconnects: list = []
    i = 0
    while i < len(lines):
        m = _TS_PAT.match(lines[i])
        if m and "[HEARTBEAT]" in lines[i]:
            ts_str = m.group(1)
            # Scan next up-to-5 continuation lines (until next timestamped entry)
            for j in range(i + 1, min(i + 6, len(lines))):
                if _TS_PAT.match(lines[j]):
                    break  # new log entry starts — stop scanning this block
                if "connection_status=DISCONNECTED" in lines[j]:
                    try:
                        ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(
                            tzinfo=_UTC
                        )
                        disconnects.append(ts)
                    except ValueError:
                        pass
                    break
        i += 1
    return disconnects


# ── Latency extraction (shared pass over events) ──────────────────────────────


def _extract_latency_pairs(events: list) -> dict:
    """
    Single pass: extract (SIGNAL_CREATED → ORDER_SUBMITTED) and
    (ORDER_SUBMITTED → ORDER_FILLED) time deltas per symbol.

    Returns {
        'sig_to_order_s': list[float],
        'sig_to_order_dry': list[bool],
        'ord_to_fill_s': list[float],
        'ord_to_fill_dry': list[bool],
    }
    """
    pending_signal: dict = {}  # sym → most recent SIGNAL_CREATED
    pending_submit: dict = {}  # sym → most recent ORDER_SUBMITTED

    sig_to_order_s: list = []
    sig_to_order_dry: list = []
    ord_to_fill_s: list = []
    ord_to_fill_dry: list = []

    for ev in events:
        sym = ev.get("symbol", "")
        etype = ev.get("event", "")

        if etype == "SIGNAL_CREATED":
            pending_signal[sym] = ev

        elif etype == "ORDER_SUBMITTED":
            if sym in pending_signal:
                sig = pending_signal.pop(sym)
                dt = (ev["_ts"] - sig["_ts"]).total_seconds()
                if dt >= 0:
                    sig_to_order_s.append(dt)
                    sig_to_order_dry.append(ev.get("dry_run", False))
            pending_submit[sym] = ev

        elif etype == "ORDER_REJECTED":
            # Signal consumed without submission — clear so next signal is fresh
            pending_signal.pop(sym, None)

        elif etype == "ORDER_FILLED":
            if sym in pending_submit:
                sub = pending_submit.pop(sym)
                dt = (ev["_ts"] - sub["_ts"]).total_seconds()
                if dt >= 0:
                    ord_to_fill_s.append(dt)
                    ord_to_fill_dry.append(ev.get("dry_run", False))
            # Fill also consumes any lingering pending_signal
            pending_signal.pop(sym, None)

    return {
        "sig_to_order_s": sig_to_order_s,
        "sig_to_order_dry": sig_to_order_dry,
        "ord_to_fill_s": ord_to_fill_s,
        "ord_to_fill_dry": ord_to_fill_dry,
    }


# ── Individual metric computers ───────────────────────────────────────────────


def compute_signal_to_order_latency(events: list) -> dict:
    """
    Time from SIGNAL_CREATED to ORDER_SUBMITTED (per submitted signal).
    Covers: circuit-breaker check + async spread check + async position fetch + sizing.
    """
    pairs = _extract_latency_pairs(events)
    stats = _latency_stats(pairs["sig_to_order_s"], pairs["sig_to_order_dry"])
    if stats.get("avg_ms", 0) > _LATENCY_WARN_MS:
        stats["warning"] = f"avg > {_LATENCY_WARN_MS}ms — check MetaAPI connectivity"
    return stats


def compute_order_to_fill_latency(events: list) -> dict:
    """
    Time from ORDER_SUBMITTED to ORDER_FILLED (broker round-trip).
    DRY_RUN: simulated fill, latency is bot processing overhead only.
    Live: actual broker acknowledgement time.
    """
    pairs = _extract_latency_pairs(events)
    stats = _latency_stats(pairs["ord_to_fill_s"], pairs["ord_to_fill_dry"])
    if stats.get("avg_ms", 0) > _FILL_LATENCY_WARN_MS:
        stats["warning"] = (
            f"avg > {_FILL_LATENCY_WARN_MS}ms — check broker connectivity"
        )
    if stats.get("dry_run_samples", 0) > 0:
        stats["dry_run_note"] = (
            "DRY_RUN fills are simulated in place_order(); latency reflects "
            "bot processing overhead, not actual broker acknowledgement."
        )
    return stats


def compute_fill_to_close_duration(trades: list) -> dict:
    """
    Time from ORDER_FILLED to POSITION_CLOSED in minutes, with percentiles.
    Broken down by exit_reason (sl / tp1 / tp2 / session_close / unknown).
    """
    durations = [
        t["hold_minutes"]
        for t in trades
        if t.get("result_r") is not None and t.get("hold_minutes") is not None
    ]

    by_reason: dict = defaultdict(lambda: {"count": 0, "minutes": []})
    for t in trades:
        if t.get("result_r") is None or t.get("hold_minutes") is None:
            continue
        reason = t.get("exit_reason") or "unknown"
        by_reason[reason]["count"] += 1
        by_reason[reason]["minutes"].append(t["hold_minutes"])

    reason_summary = {}
    for reason, d in by_reason.items():
        reason_summary[reason] = {
            "count": d["count"],
            "avg_minutes": _mean(d["minutes"]),
            "min_minutes": round(min(d["minutes"]), 1) if d["minutes"] else None,
            "max_minutes": round(max(d["minutes"]), 1) if d["minutes"] else None,
        }

    if not durations:
        return {"status": "no_closed_trades", "samples": 0, "by_exit_reason": {}}

    return {
        "avg_minutes": _mean(durations),
        "min_minutes": round(min(durations), 1),
        "max_minutes": round(max(durations), 1),
        "p25_minutes": _percentile(durations, 25),
        "p50_minutes": _percentile(durations, 50),
        "p75_minutes": _percentile(durations, 75),
        "p95_minutes": _percentile(durations, 95),
        "samples": len(durations),
        "by_exit_reason": reason_summary,
    }


def compute_slippage_distribution(trades: list) -> dict:
    """
    (fill_price − signal_entry) × 10000 pips, per fill.
    Positive = bought above / sold below signal entry (adverse for LONG).
    Includes percentiles and breakdown by symbol and side.
    """
    slips = [
        (t["slippage_pips"], t.get("symbol", "?"), t.get("side", "?"))
        for t in trades
        if t.get("slippage_pips") is not None
    ]

    if not slips:
        return {
            "status": "no_fills_yet",
            "samples": 0,
            "note": "slippage = (fill_price − signal_entry) × 10000 pips",
        }

    all_pips = [s[0] for s in slips]
    adverse = sum(1 for p in all_pips if p > 0)
    favourable = sum(1 for p in all_pips if p < 0)
    zero = sum(1 for p in all_pips if p == 0)

    by_symbol: dict = defaultdict(list)
    by_side: dict = defaultdict(list)
    for pip, sym, side in slips:
        by_symbol[sym].append(pip)
        by_side[side].append(pip)

    def _sym_stats(vals: list) -> dict:
        return {
            "avg_pips": _mean(vals),
            "p50_pips": _percentile(vals, 50),
            "p95_pips": _percentile(vals, 95),
            "adverse_count": sum(1 for v in vals if v > 0),
            "favourable_count": sum(1 for v in vals if v < 0),
            "samples": len(vals),
        }

    return {
        "avg_pips": _mean(all_pips),
        "min_pips": round(min(all_pips), 1),
        "max_pips": round(max(all_pips), 1),
        "max_adverse_pips": round(max(all_pips, key=abs), 1),
        "p25_pips": _percentile(all_pips, 25),
        "p50_pips": _percentile(all_pips, 50),
        "p75_pips": _percentile(all_pips, 75),
        "p95_pips": _percentile(all_pips, 95),
        "adverse_count": adverse,
        "favourable_count": favourable,
        "zero_count": zero,
        "samples": len(all_pips),
        "by_symbol": {sym: _sym_stats(vals) for sym, vals in by_symbol.items()},
        "by_side": {side: _sym_stats(vals) for side, vals in by_side.items()},
        "note": "positive = bought above signal entry (LONG adverse; SHORT favourable)",
    }


def compute_spread_distribution(events: list) -> dict:
    """
    Spread at fill: NOT_LOGGED (not written to ORDER_SUBMITTED).
    Spread at rejection: recovered from ORDER_REJECTED reason strings.
    Rejection rate per session computed from SIGNAL_CREATED session tags.
    """
    # Track session of each signal per symbol for rejection attribution
    last_signal_session: dict = {}  # sym → session of most recent SIGNAL_CREATED
    rej_spreads_by_sym: dict = defaultdict(list)
    rej_by_session: dict = defaultdict(int)  # sess → spread reject count
    sig_by_session: dict = defaultdict(int)  # sess → total signal count

    for ev in events:
        sym = ev.get("symbol", "")
        etype = ev.get("event", "")

        if etype == "SIGNAL_CREATED":
            sess = ev.get("session", "unknown")
            last_signal_session[sym] = sess
            sig_by_session[sess] += 1

        elif etype == "ORDER_REJECTED":
            reason = ev.get("reason", "")
            if reason.startswith("SPREAD_TOO_WIDE:"):
                try:
                    pip_val = float(reason.split(":")[1].replace("pip", "").strip())
                    rej_spreads_by_sym[sym].append(pip_val)
                    sess = last_signal_session.get(sym, "unknown")
                    rej_by_session[sess] += 1
                except (IndexError, ValueError):
                    pass
            last_signal_session.pop(sym, None)  # reject consumed this signal

    # Build per-symbol spread summary
    sym_summary: dict = {}
    for sym, vals in rej_spreads_by_sym.items():
        sym_summary[sym] = {
            "count": len(vals),
            "avg_pip": round(statistics.mean(vals), 2),
            "min_pip": round(min(vals), 2),
            "max_pip": round(max(vals), 2),
            "p50_pip": _percentile(vals, 50),
            "p95_pip": _percentile(vals, 95),
            "values": sorted(vals),
        }

    # Rejection rate per session
    session_rates: dict = {}
    all_sessions = set(sig_by_session) | set(rej_by_session)
    for sess in sorted(all_sessions):
        total_sigs = sig_by_session.get(sess, 0)
        spread_rejects = rej_by_session.get(sess, 0)
        session_rates[sess] = {
            "signals": total_sigs,
            "spread_rejects": spread_rejects,
            "reject_rate": (
                round(spread_rejects / total_sigs, 4) if total_sigs else None
            ),
        }

    return {
        "fills": {
            "status": "NOT_LOGGED_FOR_FILLS",
            "note": (
                "Spread is checked in OrderManager.check_spread() but not written to "
                "ORDER_SUBMITTED. To enable: add spread_pips kwarg to "
                "trade_logger.order_submitted()."
            ),
        },
        "rejections_by_symbol": sym_summary,
        "rejection_rate_by_session": session_rates,
    }


def compute_execution_failures(events: list) -> dict:
    """
    All ORDER_REJECTED by reason category and ERROR events by context.
    Reports absolute counts and percentages of total signals processed.
    """
    signals = sum(1 for e in events if e.get("event") == "SIGNAL_CREATED")
    fills = sum(1 for e in events if e.get("event") == "ORDER_FILLED")
    rejects = sum(1 for e in events if e.get("event") == "ORDER_REJECTED")

    # Categorise rejections
    reason_counts: dict = defaultdict(int)
    for ev in events:
        if ev.get("event") != "ORDER_REJECTED":
            continue
        reason = ev.get("reason", "UNKNOWN")
        # Normalise variable-value suffixes (e.g. MAX_OPEN_TRADES:1/1 → MAX_OPEN_TRADES)
        key = reason.split(":")[0] if ":" in reason else reason
        reason_counts[key] += 1

    total_decisions = fills + rejects
    reason_pct: dict = {}
    for key, count in sorted(reason_counts.items()):
        reason_pct[key] = {
            "count": count,
            "pct_of_signals": round(count / signals, 4) if signals else None,
            "pct_of_rejects": round(count / rejects, 4) if rejects else None,
        }

    # Categorise errors
    error_events = [e for e in events if e.get("event") == "ERROR"]
    error_by_context: dict = defaultdict(int)
    for e in error_events:
        ctx = e.get("context") or "unknown"
        error_by_context[ctx] += 1

    return {
        "signals_processed": signals,
        "orders_filled": fills,
        "orders_rejected": rejects,
        "fill_rate": round(fills / total_decisions, 4) if total_decisions else None,
        "reject_rate": round(rejects / total_decisions, 4) if total_decisions else None,
        "by_reason": reason_pct,
        "errors": {
            "count": len(error_events),
            "by_context": dict(error_by_context),
        },
    }


def compute_reconnect_during_trade(trades: list, disconnects: list) -> dict:
    """
    Cross-reference heartbeat DISCONNECTED events with open trade windows.
    A reconnect is 'during trade' when fill_ts ≤ disconnect_ts ≤ close_ts.
    For still-open trades (close_ts=None), use datetime.max as the upper bound.
    """
    _MAX_DT = datetime(9999, 12, 31, 23, 59, 59, tzinfo=_UTC)

    affected: list = []
    for t in trades:
        fill_ts = t.get("fill_ts")
        if fill_ts is None:
            continue
        close_ts = t.get("close_ts") or _MAX_DT
        in_window = [d for d in disconnects if fill_ts <= d <= close_ts]
        if in_window:
            affected.append(
                {
                    "symbol": t.get("symbol"),
                    "fill_ts": fill_ts.isoformat(),
                    "close_ts": (
                        t["close_ts"].isoformat() if t.get("close_ts") else None
                    ),
                    "disconnect_count": len(in_window),
                    "disconnect_timestamps": [d.isoformat() for d in in_window],
                }
            )

    return {
        "trades_checked": len(trades),
        "trades_with_disconnect": len(affected),
        "total_disconnects_in_period": len(disconnects),
        "note": (
            "Detection based on 5-min heartbeat cycle. "
            "Sub-5-min disconnects will not be detected."
        ),
        "details": affected,
    }


def compute_duplicate_signal_attempts(events: list) -> dict:
    """
    Detect near-duplicate SIGNAL_CREATED events that appear to be the same
    strategy signal re-submitted after a bot restart (which resets seen_signals).

    Criterion: same (symbol, session, side, entry ±0.5pip) within 120 seconds
    of a previous SIGNAL_CREATED for the same symbol.

    Note: exact duplicates (same bar timestamp) are blocked by bot.py dedup before
    reaching process_signal(), so they never appear in the log. This metric detects
    near-duplicates that made it through — typically after a restart mid-session.
    """
    signal_events = sorted(
        [e for e in events if e.get("event") == "SIGNAL_CREATED"],
        key=lambda e: e["_ts"],
    )

    duplicates: list = []
    for i, ev in enumerate(signal_events):
        sym = ev.get("symbol")
        side = ev.get("side")
        entry = ev.get("entry")
        sess = ev.get("session")
        mul = _PIP_MUL.get(sym, 10_000.0)
        ts_i = ev["_ts"]

        for prev in signal_events[:i]:
            if (
                prev.get("symbol") != sym
                or prev.get("side") != side
                or prev.get("session") != sess
            ):
                continue
            prev_entry = prev.get("entry")
            if entry is None or prev_entry is None:
                continue
            if abs(entry - prev_entry) * mul > _DUP_ENTRY_TOL_PIP:
                continue
            delta_s = (ts_i - prev["_ts"]).total_seconds()
            if delta_s > _DUP_TIME_TOL_S:
                continue
            duplicates.append(
                {
                    "symbol": sym,
                    "session": sess,
                    "side": side,
                    "entry": entry,
                    "first_ts": prev["_ts"].isoformat(),
                    "repeat_ts": ts_i.isoformat(),
                    "delta_seconds": round(delta_s, 1),
                }
            )
            break  # flag once per event

    return {
        "detected": len(duplicates),
        "method": (
            "SIGNAL_CREATED pairs with matching (symbol, session, side, entry ±0.5pip) "
            "within 120s — proxy for post-restart re-submission"
        ),
        "details": duplicates,
    }


# ── Summary assembler ─────────────────────────────────────────────────────────


def compute_execution_summary(
    trades: list,
    events: list,
    disconnects: list,
    period: str,
    label: str,
    now: datetime,
) -> dict:
    """Assemble all execution metrics for the given trade/event/disconnect sets."""
    return {
        "generated_at": now.isoformat(),
        "period": period,
        "label": label,
        "signal_to_order_latency": compute_signal_to_order_latency(events),
        "order_to_fill_latency": compute_order_to_fill_latency(events),
        "fill_to_close_duration": compute_fill_to_close_duration(trades),
        "slippage_distribution": compute_slippage_distribution(trades),
        "spread_distribution": compute_spread_distribution(events),
        "execution_failures": compute_execution_failures(events),
        "reconnect_during_trade": compute_reconnect_during_trade(trades, disconnects),
        "duplicate_signal_attempts": compute_duplicate_signal_attempts(events),
        "data_sources": {
            "trade_log": str(_TRADE_LOG),
            "bot_log": str(_BOT_LOG),
        },
        "total_events_in_period": len(events),
    }


# ── Console output ────────────────────────────────────────────────────────────


def _f(v: Optional[float], d: int = 1) -> str:
    return f"{v:.{d}f}" if v is not None else "—"


def print_execution_summary(s: dict) -> None:
    sep = "=" * 64
    print()
    print(sep)
    print(f"  EXECUTION QUALITY — {s['period'].upper()} — {s['label']}")
    print(f"  generated {s['generated_at'][:19]} UTC")
    print(sep)

    def _hdr(name: str) -> None:
        print()
        print(f"  [{name}]")

    _hdr("Signal → Order Latency (includes async spread + position check)")
    sig = s["signal_to_order_latency"]
    if sig.get("samples", 0):
        print(
            f"  avg={_f(sig['avg_ms'])}ms  p50={_f(sig['p50_ms'])}ms  "
            f"p95={_f(sig['p95_ms'])}ms  max={_f(sig['max_ms'])}ms  "
            f"(n={sig['samples']}, dry={sig['dry_run_samples']})"
        )
        if sig.get("warning"):
            print(f"  ⚠  {sig['warning']}")
    else:
        print("  no submitted signals yet")

    _hdr("Order → Fill Latency (broker round-trip)")
    fill = s["order_to_fill_latency"]
    if fill.get("samples", 0):
        print(
            f"  avg={_f(fill['avg_ms'])}ms  p50={_f(fill['p50_ms'])}ms  "
            f"p95={_f(fill['p95_ms'])}ms  max={_f(fill['max_ms'])}ms  "
            f"(n={fill['samples']}, dry={fill['dry_run_samples']})"
        )
        if fill.get("dry_run_note"):
            print(f"  note: {fill['dry_run_note'][:80]}...")
    else:
        print("  no fills yet")

    _hdr("Fill → Close Duration")
    dur = s["fill_to_close_duration"]
    if dur.get("samples", 0):
        print(
            f"  avg={_f(dur['avg_minutes'])}min  "
            f"p25={_f(dur['p25_minutes'])}  p50={_f(dur['p50_minutes'])}  "
            f"p75={_f(dur['p75_minutes'])}  max={_f(dur['max_minutes'])}min  "
            f"(n={dur['samples']})"
        )
        for reason, d in dur["by_exit_reason"].items():
            print(
                f"    {reason:<18} : {d['count']} trades  "
                f"avg={_f(d['avg_minutes'])}min"
            )
    else:
        print("  no closed trades yet")

    _hdr("Slippage Distribution")
    slip = s["slippage_distribution"]
    if slip.get("samples", 0):
        print(
            f"  avg={_f(slip['avg_pips'])}pip  "
            f"p50={_f(slip['p50_pips'])}  p95={_f(slip['p95_pips'])}  "
            f"max_adverse={_f(slip['max_adverse_pips'])}pip  (n={slip['samples']})"
        )
        print(
            f"  adverse={slip['adverse_count']}  "
            f"favourable={slip['favourable_count']}  zero={slip['zero_count']}"
        )
        for sym, d in slip.get("by_symbol", {}).items():
            print(
                f"    {sym:<10}  avg={_f(d['avg_pips'])}pip  "
                f"p95={_f(d['p95_pips'])}pip  adverse={d['adverse_count']}"
            )
    else:
        print("  no fill data yet")

    _hdr("Spread Distribution")
    spread = s["spread_distribution"]
    print(f"  fills: {spread['fills']['status']}")
    rej_sym = spread.get("rejections_by_symbol", {})
    if rej_sym:
        for sym, d in rej_sym.items():
            print(
                f"    {sym} rejections: count={d['count']}  "
                f"avg={_f(d['avg_pip'], 2)}pip  max={_f(d['max_pip'], 2)}pip"
            )
    sess_rates = spread.get("rejection_rate_by_session", {})
    if sess_rates:
        print("  rejection_rate_by_session:")
        for sess, d in sess_rates.items():
            rate_str = (
                f"{d['reject_rate'] * 100:.1f}%"
                if d["reject_rate"] is not None
                else "—"
            )
            print(
                f"    {sess:<12}  signals={d['signals']}  "
                f"spread_rejects={d['spread_rejects']}  rate={rate_str}"
            )

    _hdr("Execution Failures")
    fail = s["execution_failures"]
    fill_rate = (
        f"{fail['fill_rate'] * 100:.1f}%" if fail["fill_rate"] is not None else "—"
    )
    print(
        f"  signals={fail['signals_processed']}  fills={fail['orders_filled']}  "
        f"rejects={fail['orders_rejected']}  fill_rate={fill_rate}"
    )
    for k, v in fail.get("by_reason", {}).items():
        pct = (
            f"{v['pct_of_signals'] * 100:.1f}%"
            if v["pct_of_signals"] is not None
            else "—"
        )
        print(f"    {k:<30}  count={v['count']}  ({pct} of signals)")
    errs = fail.get("errors", {})
    print(f"  errors: {errs.get('count', 0)}")
    if errs.get("by_context"):
        for ctx, cnt in errs["by_context"].items():
            print(f"    [{ctx}]: {cnt}")

    _hdr("Reconnect During Trade")
    rc = s["reconnect_during_trade"]
    print(
        f"  trades_checked={rc['trades_checked']}  "
        f"trades_with_disconnect={rc['trades_with_disconnect']}  "
        f"total_disconnects={rc['total_disconnects_in_period']}"
    )
    for d in rc.get("details", []):
        print(
            f"    {d['symbol']} | {d['disconnect_count']} disconnect(s) | "
            f"fill={d['fill_ts'][:16]}"
        )

    _hdr("Duplicate Signal Attempts")
    dup = s["duplicate_signal_attempts"]
    print(f"  detected={dup['detected']}")
    for d in dup.get("details", []):
        print(
            f"    {d['symbol']} {d['side']} entry={d['entry']}  "
            f"Δ={d['delta_seconds']}s"
        )

    print()
    print(sep)


# ── Main ──────────────────────────────────────────────────────────────────────


def run(
    write_daily: bool = True,
    write_weekly: bool = True,
    log_file: Path = _TRADE_LOG,
    bot_log: Path = _BOT_LOG,
    now: Optional[datetime] = None,
    quiet: bool = False,
) -> tuple:
    """
    Compute and write daily + weekly execution summaries.
    Returns (daily_dict, weekly_dict). Callable from tests via import.
    """
    if now is None:
        now = datetime.now(_UTC)

    events = load_events(log_file)
    all_trades = build_trades(events)
    disconnects = load_bot_log_disconnects(bot_log)

    daily: dict = {}
    weekly: dict = {}

    if write_daily:
        d_start, d_end = daily_window(now)
        d_trades, d_events = filter_period(all_trades, events, d_start, d_end)
        d_disconnects = [d for d in disconnects if d_start <= d < d_end]
        daily = compute_execution_summary(
            d_trades, d_events, d_disconnects, "daily", now.strftime("%Y-%m-%d"), now
        )
        _DAILY_OUT.parent.mkdir(parents=True, exist_ok=True)
        _DAILY_OUT.write_text(
            json.dumps(daily, indent=2, default=str), encoding="utf-8"
        )
        if not quiet:
            print_execution_summary(daily)
            print(f"→ {_DAILY_OUT}")

    if write_weekly:
        w_start, w_end = weekly_window(now)
        w_trades, w_events = filter_period(all_trades, events, w_start, w_end)
        w_disconnects = [d for d in disconnects if w_start <= d < w_end]
        iso_year, iso_week, _ = now.isocalendar()
        weekly = compute_execution_summary(
            w_trades,
            w_events,
            w_disconnects,
            "weekly",
            f"{iso_year}-W{iso_week:02d}",
            now,
        )
        _WEEKLY_OUT.parent.mkdir(parents=True, exist_ok=True)
        _WEEKLY_OUT.write_text(
            json.dumps(weekly, indent=2, default=str), encoding="utf-8"
        )
        if not quiet:
            print_execution_summary(weekly)
            print(f"→ {_WEEKLY_OUT}")

    return daily, weekly


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="RESEARCH-05 Execution Quality Analyzer"
    )
    parser.add_argument("--daily", action="store_true", help="Daily summary only")
    parser.add_argument("--weekly", action="store_true", help="Weekly summary only")
    parser.add_argument(
        "--log",
        type=Path,
        default=_TRADE_LOG,
        metavar="PATH",
        help="JSONL trade log (default: logs/trades.jsonl)",
    )
    parser.add_argument(
        "--botlog",
        type=Path,
        default=_BOT_LOG,
        metavar="PATH",
        help="Bot log file (default: logs/bot.log)",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress console output")
    args = parser.parse_args()

    both = not args.daily and not args.weekly
    run(
        write_daily=args.daily or both,
        write_weekly=args.weekly or both,
        log_file=args.log,
        bot_log=args.botlog,
        quiet=args.quiet,
    )

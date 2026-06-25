#!/usr/bin/env python3
"""
OPS-03 Live Trade Analyzer.

Reads logs/trades.jsonl and emits:
    logs/daily_trade_summary.json   — events in the current UTC calendar day
    logs/weekly_trade_summary.json  — events in the current ISO week (Mon–now)

Usage:
    python3 research/live_trade_analyzer.py            # both summaries
    python3 research/live_trade_analyzer.py --daily    # daily only
    python3 research/live_trade_analyzer.py --weekly   # weekly only
    python3 research/live_trade_analyzer.py --log <path>  # custom JSONL file
    python3 research/live_trade_analyzer.py --quiet    # suppress console output

No imports from bot modules. Read-only on the log file. No strategy changes.

Trade lifecycle correlation
---------------------------
SIGNAL_CREATED events are keyed to ORDER_FILLED events per symbol by temporal
order (most recent signal before each fill). ORDER_FILLED events are matched FIFO
to POSITION_CLOSED events per symbol. This is valid because MAX_OPEN_TRADES=1
guarantees at most one open position per symbol at any time.

spread_at_entry
---------------
The spread at fill time is checked in OrderManager.check_spread() but is NOT
written to ORDER_SUBMITTED. This field is reported as NOT_LOGGED_FOR_FILLS.
Spreads at rejection time are recoverable from ORDER_REJECTED.reason strings
(SPREAD_TOO_WIDE:X.Xpip) and are surfaced in the rejected_spreads_by_symbol field.

slippage
--------
slippage_pips = (entry_fill − entry_signal) × 10000
Positive: bought above / sold below signal price (adverse for LONG, favourable SHORT).
"""

import argparse
import json
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).parent.parent
_TRADE_LOG = _ROOT / "logs" / "trades.jsonl"
_DAILY_SUMMARY = _ROOT / "logs" / "daily_trade_summary.json"
_WEEKLY_SUMMARY = _ROOT / "logs" / "weekly_trade_summary.json"
_UTC = timezone.utc

# EURUSD and GBPUSD are both 4-decimal currency pairs → 1 pip = 0.0001
_PIP_MUL: dict = {"EURUSD": 10_000.0, "GBPUSD": 10_000.0}


# ── JSONL loading ─────────────────────────────────────────────────────────────

def load_events(log_file: Path = _TRADE_LOG) -> list:
    """
    Load all events from trades.jsonl, sorted by timestamp.
    Attaches '_ts' (parsed datetime, UTC-aware) to each event dict.
    Skips malformed lines without raising.
    """
    if not log_file.exists():
        return []
    events = []
    for line in log_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
            ev["_ts"] = datetime.fromisoformat(ev["ts"])
            events.append(ev)
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    return sorted(events, key=lambda e: e["_ts"])


# ── Trade lifecycle correlation ───────────────────────────────────────────────

def build_trades(events: list) -> list:
    """
    Correlate SIGNAL_CREATED → ORDER_FILLED → POSITION_CLOSED into trade records.

    Returns a flat list of trade dicts. Trades that are filled but not yet closed
    (still open) are included with result_r=None. Rejected signals are not included
    as trades; their data appears only in rejection_reasons.

    Trade dict keys:
        symbol, session, side, dry_run,
        signal_ts, fill_ts, close_ts,
        entry_signal, entry_fill, sl, tp, sl_pips, lots, order_id,
        result_r, exit_reason, hold_minutes, slippage_pips
    """
    last_signal: dict = {}             # symbol → most recent SIGNAL_CREATED event
    open_fills: dict = defaultdict(list)  # symbol → [trade dicts awaiting POSITION_CLOSED]
    trades: list = []

    for ev in events:
        sym = ev.get("symbol", "")
        etype = ev.get("event", "")

        if etype == "SIGNAL_CREATED":
            last_signal[sym] = ev

        elif etype == "ORDER_FILLED":
            sig = last_signal.get(sym)
            trade = {
                "symbol": sym,
                "session": sig.get("session", "unknown") if sig else "unknown",
                "side": sig.get("side", "unknown") if sig else "unknown",
                "dry_run": ev.get("dry_run", False),
                "signal_ts": sig["_ts"] if sig else None,
                "fill_ts": ev["_ts"],
                "close_ts": None,
                "entry_signal": sig.get("entry") if sig else None,
                "entry_fill": ev.get("entry_price"),
                "sl": ev.get("sl"),
                "tp": ev.get("tp"),
                "sl_pips": sig.get("sl_pips") if sig else None,
                "lots": ev.get("volume"),
                "order_id": ev.get("order_id"),
                "result_r": None,
                "exit_reason": None,
                "hold_minutes": None,
                "slippage_pips": _compute_slippage_pips(
                    sig, ev.get("entry_price"), sym
                ),
            }
            open_fills[sym].append(trade)
            last_signal.pop(sym, None)   # consumed — next signal for this symbol is fresh

        elif etype == "POSITION_CLOSED":
            if open_fills[sym]:
                trade = open_fills[sym].pop(0)  # FIFO: oldest open fill for this symbol
                trade["close_ts"] = ev["_ts"]
                trade["result_r"] = ev.get("result_r", 0.0)
                trade["exit_reason"] = ev.get("exit_reason", "")
                if trade["fill_ts"] and trade["close_ts"]:
                    delta = (trade["close_ts"] - trade["fill_ts"]).total_seconds()
                    trade["hold_minutes"] = round(delta / 60.0, 1)
                trades.append(trade)

    # Append any fills not yet closed (still open positions)
    for sym_queue in open_fills.values():
        trades.extend(sym_queue)

    return trades


def _compute_slippage_pips(
    signal: Optional[dict], fill_price: Optional[float], symbol: str
) -> Optional[float]:
    """
    Slippage = (fill_price − signal_entry) × pip_multiplier.
    Returns None when either price is unavailable.
    """
    if signal is None or fill_price is None:
        return None
    entry_sig = signal.get("entry")
    if entry_sig is None:
        return None
    mul = _PIP_MUL.get(symbol, 10_000.0)
    return round((fill_price - entry_sig) * mul, 1)


# ── Period filtering ──────────────────────────────────────────────────────────

def filter_period(
    all_trades: list,
    all_events: list,
    start: datetime,
    end: datetime,
) -> tuple:
    """
    Filter trades by fill_ts and events by ts to the half-open interval [start, end).
    """
    def _in(ts: Optional[datetime]) -> bool:
        return ts is not None and start <= ts < end

    trades = [t for t in all_trades if _in(t.get("fill_ts"))]
    events = [e for e in all_events if _in(e.get("_ts"))]
    return trades, events


def daily_window(now: datetime) -> tuple:
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, now


def weekly_window(now: datetime) -> tuple:
    monday = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return monday, now


# ── Metric helpers ────────────────────────────────────────────────────────────

def _mean(values: list) -> Optional[float]:
    return round(statistics.mean(values), 4) if values else None


def _pf(r_values: list) -> Optional[float]:
    """
    Profit factor = gross_wins / gross_losses.
    Returns None when there are no losses (not infinite — undefined at this sample size).
    """
    gross_win = sum(r for r in r_values if r > 0)
    gross_loss = abs(sum(r for r in r_values if r < 0))
    if gross_loss == 0:
        return None
    return round(gross_win / gross_loss, 4) if gross_win > 0 else 0.0


# ── Breakdown builders ────────────────────────────────────────────────────────

def session_breakdown(trades: list, events: list) -> dict:
    """
    Per-session aggregate. Signal counts sourced from SIGNAL_CREATED events;
    performance metrics from matched closed trades.
    """
    sig_counts: dict = defaultdict(int)
    for ev in events:
        if ev.get("event") == "SIGNAL_CREATED":
            sig_counts[ev.get("session", "unknown")] += 1

    agg: dict = defaultdict(lambda: {"fills": 0, "wins": 0, "losses": 0, "R": []})
    for t in trades:
        sess = t.get("session") or "unknown"
        agg[sess]["fills"] += 1
        if t.get("result_r") is not None:
            r = t["result_r"]
            agg[sess]["R"].append(r)
            if r > 0:
                agg[sess]["wins"] += 1
            else:
                agg[sess]["losses"] += 1

    result = {}
    for sess in sorted(set(sig_counts) | set(agg)):
        d = agg[sess]
        r_vals = d["R"]
        closed = len(r_vals)
        result[sess] = {
            "signals": sig_counts.get(sess, 0),
            "fills": d["fills"],
            "closed": closed,
            "wins": d["wins"],
            "losses": d["losses"],
            "win_rate": round(d["wins"] / closed, 4) if closed else None,
            "avg_R": _mean(r_vals),
            "PF": _pf(r_vals),
        }
    return result


def symbol_breakdown(trades: list, events: list) -> dict:
    """Per-symbol aggregate including slippage stats."""
    sig_counts: dict = defaultdict(int)
    for ev in events:
        if ev.get("event") == "SIGNAL_CREATED":
            sig_counts[ev.get("symbol", "unknown")] += 1

    agg: dict = defaultdict(lambda: {
        "fills": 0, "wins": 0, "losses": 0, "R": [], "slippage": []
    })
    for t in trades:
        sym = t.get("symbol") or "unknown"
        agg[sym]["fills"] += 1
        if t.get("slippage_pips") is not None:
            agg[sym]["slippage"].append(t["slippage_pips"])
        if t.get("result_r") is not None:
            r = t["result_r"]
            agg[sym]["R"].append(r)
            if r > 0:
                agg[sym]["wins"] += 1
            else:
                agg[sym]["losses"] += 1

    result = {}
    for sym in sorted(set(sig_counts) | set(agg)):
        d = agg[sym]
        r_vals = d["R"]
        slip = d["slippage"]
        closed = len(r_vals)
        result[sym] = {
            "signals": sig_counts.get(sym, 0),
            "fills": d["fills"],
            "closed": closed,
            "wins": d["wins"],
            "losses": d["losses"],
            "win_rate": round(d["wins"] / closed, 4) if closed else None,
            "avg_R": _mean(r_vals),
            "PF": _pf(r_vals),
            "slippage_avg_pips": _mean(slip),
            "slippage_max_pips": round(max(slip, key=abs), 1) if slip else None,
            "slippage_samples": len(slip),
        }
    return result


def rejection_breakdown(events: list) -> dict:
    """
    Count ORDER_REJECTED reasons. SPREAD_TOO_WIDE pip values are aggregated
    separately; other multi-value reasons are normalised to their prefix.
    """
    counts: dict = defaultdict(int)
    spread_pips: list = []

    for ev in events:
        if ev.get("event") != "ORDER_REJECTED":
            continue
        reason = ev.get("reason", "UNKNOWN")
        if reason.startswith("SPREAD_TOO_WIDE:"):
            counts["SPREAD_TOO_WIDE"] += 1
            try:
                spread_pips.append(float(reason.split(":")[1].replace("pip", "").strip()))
            except (IndexError, ValueError):
                pass
        else:
            # Normalise reasons like "MAX_OPEN_TRADES:1/1" → "MAX_OPEN_TRADES"
            key = reason.split(":")[0] if ":" in reason else reason
            counts[key] += 1

    out: dict = dict(counts)
    if spread_pips:
        out["SPREAD_TOO_WIDE_avg_pip"] = round(statistics.mean(spread_pips), 2)
        out["SPREAD_TOO_WIDE_max_pip"] = max(spread_pips)
        out["SPREAD_TOO_WIDE_values"] = sorted(spread_pips)
    return out


def slippage_summary(trades: list) -> dict:
    """Aggregate slippage across all fills in the period."""
    slips = [t["slippage_pips"] for t in trades if t.get("slippage_pips") is not None]
    if not slips:
        return {
            "status": "no_fills_yet",
            "samples": 0,
            "note": "slippage = (entry_fill - entry_signal) × 10000 pips",
        }
    return {
        "avg_pips": _mean(slips),
        "max_pips": round(max(slips), 1),
        "min_pips": round(min(slips), 1),
        "max_adverse_pips": round(max(slips, key=abs), 1),
        "samples": len(slips),
        "note": "positive = bought above / sold below signal entry (LONG adverse)",
    }


def spread_at_entry_summary(events: list) -> dict:
    """
    The spread at fill time is NOT written to ORDER_SUBMITTED.
    This function recovers spread values observed at rejection time from
    ORDER_REJECTED.reason (SPREAD_TOO_WIDE:X.Xpip) as a proxy.
    """
    rejected_spreads: dict = defaultdict(list)
    for ev in events:
        if ev.get("event") != "ORDER_REJECTED":
            continue
        reason = ev.get("reason", "")
        if not reason.startswith("SPREAD_TOO_WIDE:"):
            continue
        sym = ev.get("symbol", "unknown")
        try:
            rejected_spreads[sym].append(
                float(reason.split(":")[1].replace("pip", "").strip())
            )
        except (IndexError, ValueError):
            pass

    return {
        "status": "NOT_LOGGED_FOR_FILLS",
        "note": (
            "Spread is checked in OrderManager.check_spread() but is not written to "
            "ORDER_SUBMITTED. To enable: add spread_pips kwarg to "
            "trade_logger.order_submitted() and log it in order_manager.py Step 3."
        ),
        "rejected_spreads_by_symbol": {
            sym: {
                "count": len(vals),
                "avg_pip": round(statistics.mean(vals), 2),
                "max_pip": round(max(vals), 2),
                "values": sorted(vals),
            }
            for sym, vals in rejected_spreads.items()
        },
    }


# ── Summary assembler ─────────────────────────────────────────────────────────

def compute_summary(
    trades: list,
    events: list,
    period: str,
    label: str,
    now: datetime,
) -> dict:
    """
    Compute all analytics metrics for the given trade and event lists.
    Trades are those with fill_ts in the reporting period.
    Events are those with ts in the reporting period.
    """
    closed = [t for t in trades if t.get("result_r") is not None]
    still_open = [t for t in trades if t.get("result_r") is None]
    r_vals = [t["result_r"] for t in closed]
    wins = [r for r in r_vals if r > 0]
    losses = [r for r in r_vals if r < 0]
    hold_times = [t["hold_minutes"] for t in closed if t.get("hold_minutes") is not None]
    n = len(closed)

    signals_total = sum(1 for e in events if e.get("event") == "SIGNAL_CREATED")
    fills_total = sum(1 for e in events if e.get("event") == "ORDER_FILLED")
    rejects_total = sum(1 for e in events if e.get("event") == "ORDER_REJECTED")
    errors_total = sum(1 for e in events if e.get("event") == "ERROR")

    return {
        "generated_at": now.isoformat(),
        "period": period,
        "label": label,

        # Signal pipeline
        "signals_generated": signals_total,
        "orders_filled": fills_total,
        "orders_rejected": rejects_total,
        "errors": errors_total,
        "trades_closed": len(closed),
        "trades_still_open": len(still_open),

        # Performance (from POSITION_CLOSED events)
        "trade_count": n,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / n, 4) if n else None,
        "average_R": _mean(r_vals),
        "total_R": round(sum(r_vals), 4) if r_vals else None,
        "PF": _pf(r_vals),
        "best_trade_R": round(max(r_vals), 4) if r_vals else None,
        "worst_trade_R": round(min(r_vals), 4) if r_vals else None,

        # Execution: hold time
        "average_hold_time_minutes": _mean(hold_times),
        "min_hold_time_minutes": round(min(hold_times), 1) if hold_times else None,
        "max_hold_time_minutes": round(max(hold_times), 1) if hold_times else None,

        # Execution: slippage
        "slippage": slippage_summary(trades),

        # Execution: spread (partially recovered)
        "spread_at_entry": spread_at_entry_summary(events),

        # Breakdowns
        "session_breakdown": session_breakdown(trades, events),
        "symbol_breakdown": symbol_breakdown(trades, events),

        # Rejection analysis
        "rejection_reasons": rejection_breakdown(events),

        # Meta
        "data_source": str(_TRADE_LOG),
        "total_events_in_period": len(events),
        "low_sample_warning": (
            "ST-A2 expected frequency: ~34 trades/yr (~3/month). "
            "win_rate and PF are not statistically meaningful until n≥30."
        ) if n < 30 else None,
    }


# ── Console output ────────────────────────────────────────────────────────────

def _f(v: Optional[float], d: int = 3) -> str:
    return f"{v:.{d}f}" if v is not None else "—"


def _pct(v: Optional[float]) -> str:
    return f"{v * 100:.1f}%" if v is not None else "—"


def print_summary(s: dict) -> None:
    sep = "=" * 62
    print()
    print(sep)
    print(f"  {s['period'].upper()} — {s['label']}")
    print(f"  generated {s['generated_at'][:19]} UTC")
    print(sep)

    print()
    print("  [Pipeline]")
    print(f"  signals_generated  : {s['signals_generated']}")
    print(f"  orders_filled      : {s['orders_filled']}")
    print(f"  orders_rejected    : {s['orders_rejected']}")
    print(f"  errors             : {s['errors']}")
    print(f"  trades_closed      : {s['trades_closed']}")
    print(f"  trades_still_open  : {s['trades_still_open']}")

    print()
    print("  [Performance]")
    print(f"  trade_count        : {s['trade_count']}")
    print(f"  win_rate           : {_pct(s['win_rate'])}  ({s['wins']}W / {s['losses']}L)")
    print(f"  average_R          : {_f(s['average_R'])}")
    print(f"  total_R            : {_f(s['total_R'])}")
    pf_str = _f(s["PF"]) if s["PF"] is not None else "— (no losses yet)"
    print(f"  PF                 : {pf_str}")
    print(f"  best / worst R     : {_f(s['best_trade_R'])} / {_f(s['worst_trade_R'])}")

    print()
    print("  [Hold Time]")
    print(f"  avg_hold_time      : {_f(s['average_hold_time_minutes'], 1)} min")
    print(f"  min_hold_time      : {_f(s['min_hold_time_minutes'], 1)} min")
    print(f"  max_hold_time      : {_f(s['max_hold_time_minutes'], 1)} min")

    print()
    print("  [Execution Quality]")
    slip = s.get("slippage", {})
    if slip.get("samples", 0) > 0:
        print(
            f"  slippage           : avg={_f(slip.get('avg_pips'), 1)} pip  "
            f"max_adverse={_f(slip.get('max_adverse_pips'), 1)} pip  "
            f"(n={slip['samples']})"
        )
    else:
        print("  slippage           : no fill data yet")

    spread = s.get("spread_at_entry", {})
    print(f"  spread_at_entry    : {spread.get('status', 'unknown')}")
    for sym, d in (spread.get("rejected_spreads_by_symbol") or {}).items():
        print(f"    [{sym}] {d['count']} rejections  avg={d['avg_pip']} pip  max={d['max_pip']} pip")

    print()
    print("  [Session Breakdown]")
    for sess, d in (s.get("session_breakdown") or {}).items():
        print(
            f"    {sess:<10}  sigs={d['signals']}  fills={d['fills']}  "
            f"closed={d['closed']}  {d['wins']}W/{d['losses']}L  "
            f"wr={_pct(d['win_rate'])}  avg_R={_f(d['avg_R'], 2)}  PF={_f(d['PF'], 2)}"
        )

    print()
    print("  [Symbol Breakdown]")
    for sym, d in (s.get("symbol_breakdown") or {}).items():
        slip_str = (
            f"  slip={_f(d['slippage_avg_pips'], 1)}pip"
            if (d.get("slippage_samples") or 0) > 0 else ""
        )
        print(
            f"    {sym:<10}  sigs={d['signals']}  fills={d['fills']}  "
            f"closed={d['closed']}  {d['wins']}W/{d['losses']}L  "
            f"wr={_pct(d['win_rate'])}  avg_R={_f(d['avg_R'], 2)}{slip_str}"
        )

    rej = s.get("rejection_reasons") or {}
    display_rej = {k: v for k, v in rej.items()
                   if not k.endswith(("_avg_pip", "_max_pip", "_values"))}
    if display_rej:
        print()
        print("  [Rejection Reasons]")
        for k, v in display_rej.items():
            print(f"    {k}: {v}")

    if s.get("low_sample_warning"):
        print()
        print(f"  ! {s['low_sample_warning']}")

    print(sep)


# ── Main ──────────────────────────────────────────────────────────────────────

def run(
    write_daily: bool = True,
    write_weekly: bool = True,
    log_file: Path = _TRADE_LOG,
    now: Optional[datetime] = None,
    quiet: bool = False,
) -> tuple:
    """
    Compute and write daily + weekly summaries. Returns (daily_dict, weekly_dict).
    Callable from tests or other scripts via import.
    """
    if now is None:
        now = datetime.now(_UTC)

    events = load_events(log_file)
    all_trades = build_trades(events)

    daily: dict = {}
    weekly: dict = {}

    if write_daily:
        d_start, d_end = daily_window(now)
        d_trades, d_events = filter_period(all_trades, events, d_start, d_end)
        daily = compute_summary(d_trades, d_events, "daily", now.strftime("%Y-%m-%d"), now)
        _DAILY_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
        _DAILY_SUMMARY.write_text(json.dumps(daily, indent=2, default=str), encoding="utf-8")
        if not quiet:
            print_summary(daily)
            print(f"→ {_DAILY_SUMMARY}")

    if write_weekly:
        w_start, w_end = weekly_window(now)
        w_trades, w_events = filter_period(all_trades, events, w_start, w_end)
        iso_year, iso_week, _ = now.isocalendar()
        weekly = compute_summary(
            w_trades, w_events, "weekly", f"{iso_year}-W{iso_week:02d}", now
        )
        _WEEKLY_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
        _WEEKLY_SUMMARY.write_text(json.dumps(weekly, indent=2, default=str), encoding="utf-8")
        if not quiet:
            print_summary(weekly)
            print(f"→ {_WEEKLY_SUMMARY}")

    return daily, weekly


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OPS-03 Live Trade Analyzer")
    parser.add_argument("--daily", action="store_true", help="Daily summary only")
    parser.add_argument("--weekly", action="store_true", help="Weekly summary only")
    parser.add_argument("--log", type=Path, default=_TRADE_LOG, metavar="PATH",
                        help=f"JSONL log file (default: logs/trades.jsonl)")
    parser.add_argument("--quiet", action="store_true", help="Suppress console output")
    args = parser.parse_args()

    both = not args.daily and not args.weekly
    run(
        write_daily=args.daily or both,
        write_weekly=args.weekly or both,
        log_file=args.log,
        quiet=args.quiet,
    )

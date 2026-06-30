#!/usr/bin/env python3
"""
Live-vs-Backtest Validator — RESEARCH layer only.

Reads logs/trades.jsonl and compares live execution against the ST-A2
backtest expectations. Answers the core paper-trade question:

    Is live execution behaving like the backtest?

Metrics produced:
    signal_frequency_ratio   — live signals/month vs backtest baseline
    session_distribution     — actual London/NY split vs backtest 70/30 split
    sl_pips_distribution     — actual SL distance vs backtest distribution
    entry_vs_fill_drift      — entry_signal price vs fill price (slippage)
    spread_cost_ratio        — implied spread from actual SL vs backtest model
    win_rate                 — live vs backtest 32.0%
    avg_r                    — live vs backtest 0.108
    pf                       — live vs backtest 1.151 (std spread)
    drift_flags              — WARN if any metric deviates > threshold

Usage:
    python3 research/live_vs_backtest_validator.py
    python3 research/live_vs_backtest_validator.py --since 2026-06-21
    python3 research/live_vs_backtest_validator.py --json
    python3 research/live_vs_backtest_validator.py --out reports/lvb_YYYYMMDD.md

Output: human-readable markdown + optional JSON.

Read-only on all inputs. No execution, strategy, or MetaAPI code touched.
"""

import argparse
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).parent.parent
_TRADE_LOG = _ROOT / "logs" / "trades.jsonl"
_REPORTS_DIR = _ROOT / "reports"
_UTC = timezone.utc

# ── ST-A2 Backtest Benchmarks (locked — do not change) ───────────────────────

_BACKTEST = {
    "strategy": "ST-A2",
    "run_id": "20260621T100458-183aaa",
    "rr": 5,
    "pairs": ["EURUSD", "GBPUSD"],
    "data_years": 4.9,
    "total_trades": 169,
    "trades_per_year": 34.5,
    "trades_per_month": 2.9,
    "win_rate": 0.320,
    "avg_r": 0.108,
    "gross_pf": 1.299,
    "net_pf_std": 1.151,
    "net_pf_2x": 1.025,
    "max_dd_r": 18.72,
    "min_sl_pips": 5.0,
    "session_london_pct": 0.70,   # 118/169
    "session_ny_pct": 0.30,       # 51/169
    "eurusd_trade_pct": 0.62,     # 105/169
    "gbpusd_trade_pct": 0.38,     # 64/169
    "spread_eurusd_pips": 1.4,    # std + commission RT
    "spread_gbpusd_pips": 1.8,
    # Per-session net PF (std)
    "london_net_pf_std": 0.949,
    "ny_net_pf_std": 1.731,
    # Per-symbol net PF (std)
    "eurusd_net_pf_std": 1.059,
    "gbpusd_net_pf_std": 1.313,
    # Risk flags from ST_A2_CONFIRMATION.md
    "eurusd_net_pf_2x": 0.945,    # fails alone — monitor closely
    "gbpusd_net_pf_2x": 1.168,
}

# ── Drift thresholds ──────────────────────────────────────────────────────────
# When live metrics deviate beyond these thresholds, a WARNING is emitted.
# Thresholds are generous to account for small sample sizes.

_THRESHOLDS = {
    "win_rate_min": 0.20,          # WARN if below 20% over n≥10
    "win_rate_max": 0.60,          # WARN if above 60% over n≥10 (data error?)
    "avg_r_min": -1.0,             # WARN if average R < -1.0
    "slippage_warn_pips": 1.0,     # WARN if avg slippage > 1 pip
    "slippage_critical_pips": 2.0, # CRITICAL if avg slippage > 2 pip
    "sl_floor_pips": 5.0,          # WARN if any actual SL < 5.0 pips
    "session_london_max_pct": 0.85,# WARN if London > 85% (NY crowded out)
    "frequency_drift_pct": 0.50,   # WARN if actual frequency < 50% of expected
    "min_n_for_win_rate": 10,      # Only flag win_rate if n >= this
    "min_n_for_pf": 20,            # Only flag PF if n >= this
}

_PIP_MUL: dict[str, float] = {"EURUSD": 10_000.0, "GBPUSD": 10_000.0}


# ── Data loading ──────────────────────────────────────────────────────────────

def _load_events(since: Optional[datetime] = None) -> list[dict]:
    if not _TRADE_LOG.exists():
        return []
    events = []
    for line in _TRADE_LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
            ev["_ts"] = datetime.fromisoformat(ev["ts"])
            if since and ev["_ts"] < since:
                continue
            events.append(ev)
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    return sorted(events, key=lambda e: e["_ts"])


# ── Analysis functions ────────────────────────────────────────────────────────

def _signal_frequency(events: list[dict], since: datetime, now: datetime) -> dict:
    """Compare actual signal frequency to backtest baseline."""
    signals = [e for e in events if e.get("event") == "SIGNAL_CREATED"]
    days_elapsed = max(1, (now - since).days)
    months_elapsed = max(0.01, days_elapsed / 30.44)

    actual_per_month = len(signals) / months_elapsed
    expected_per_month = _BACKTEST["trades_per_month"]
    ratio = actual_per_month / expected_per_month if expected_per_month > 0 else 0.0

    return {
        "n_signals": len(signals),
        "days_elapsed": days_elapsed,
        "actual_per_month": round(actual_per_month, 2),
        "expected_per_month": expected_per_month,
        "ratio": round(ratio, 2),
        "warn": ratio < _THRESHOLDS["frequency_drift_pct"] and days_elapsed >= 30,
    }


def _session_distribution(events: list[dict]) -> dict:
    """Check London/NY split vs backtest 70/30 ratio."""
    signals = [e for e in events if e.get("event") == "SIGNAL_CREATED"]
    if not signals:
        return {
            "n": 0, "london_count": 0, "ny_count": 0,
            "london_pct": None, "ny_pct": None,
            "backtest_london_pct": round(_BACKTEST["session_london_pct"] * 100, 1),
            "backtest_ny_pct": round(_BACKTEST["session_ny_pct"] * 100, 1),
            "warn": False,
        }

    by_session: dict[str, int] = defaultdict(int)
    for s in signals:
        sess = s.get("session", "unknown").lower()
        by_session[sess] += 1

    n = len(signals)
    london = by_session.get("london", 0) / n if n else 0
    ny = by_session.get("new_york", by_session.get("ny", 0)) / n if n else 0

    return {
        "n": n,
        "london_count": by_session.get("london", 0),
        "ny_count": by_session.get("new_york", by_session.get("ny", 0)),
        "london_pct": round(london * 100, 1),
        "ny_pct": round(ny * 100, 1),
        "backtest_london_pct": round(_BACKTEST["session_london_pct"] * 100, 1),
        "backtest_ny_pct": round(_BACKTEST["session_ny_pct"] * 100, 1),
        "warn": london > _THRESHOLDS["session_london_max_pct"] and n >= 10,
    }


def _sl_distribution(events: list[dict]) -> dict:
    """Check SL pip distances against min_sl_pips gate and expected distribution."""
    signals = [e for e in events if e.get("event") == "SIGNAL_CREATED" and "sl_pips" in e]
    if not signals:
        return {"n": 0, "min_sl": None, "max_sl": None, "avg_sl": None,
                "below_floor": 0, "warn": False}

    sl_vals = [s["sl_pips"] for s in signals]
    below_floor = sum(1 for v in sl_vals if v < _THRESHOLDS["sl_floor_pips"])

    return {
        "n": len(sl_vals),
        "min_sl_pips": round(min(sl_vals), 2),
        "max_sl_pips": round(max(sl_vals), 2),
        "avg_sl_pips": round(statistics.mean(sl_vals), 2),
        "median_sl_pips": round(statistics.median(sl_vals), 2),
        "below_5pip_floor": below_floor,
        "warn": below_floor > 0,
    }


def _slippage_analysis(events: list[dict]) -> dict:
    """
    Compare SIGNAL_CREATED entry price vs ORDER_FILLED entry_price.

    Slippage (pips) = (fill_price - signal_price) × pip_multiplier × direction_sign
    Positive = adverse (bought above / sold below signal price).
    """
    signals = {e.get("symbol"): e for e in events if e.get("event") == "SIGNAL_CREATED"}
    fills = [e for e in events if e.get("event") == "ORDER_FILLED" and not e.get("dry_run", False)]

    slippages = []
    for fill in fills:
        sym = fill.get("symbol", "")
        fill_price = fill.get("entry_price")
        if not fill_price or sym not in signals:
            continue
        signal = signals[sym]
        signal_entry = signal.get("entry")
        side = signal.get("side", "long")
        mul = _PIP_MUL.get(sym, 10_000.0)
        if signal_entry and fill_price:
            raw = (fill_price - signal_entry) * mul
            signed = raw if side == "long" else -raw
            slippages.append({"symbol": sym, "slippage_pips": round(signed, 2), "side": side})

    if not slippages:
        return {"n": 0, "avg_slippage_pips": None, "max_slippage_pips": None,
                "pct_adverse": None, "warn": False, "critical": False, "samples": []}

    vals = [s["slippage_pips"] for s in slippages]
    avg = statistics.mean(vals)
    adverse_pct = sum(1 for v in vals if v > 0) / len(vals) * 100

    return {
        "n": len(vals),
        "avg_slippage_pips": round(avg, 3),
        "max_slippage_pips": round(max(vals), 3),
        "min_slippage_pips": round(min(vals), 3),
        "pct_adverse": round(adverse_pct, 1),
        "warn": avg > _THRESHOLDS["slippage_warn_pips"],
        "critical": avg > _THRESHOLDS["slippage_critical_pips"],
        "samples": slippages,
    }


def _spread_analysis(events: list[dict]) -> dict:
    """
    Estimate live spread from ORDER_REJECTED events with SPREAD_TOO_WIDE reason.
    Also reports on ORDER_SUBMITTED vs SIGNAL_CREATED price to infer spread at entry.
    """
    rejections = [e for e in events if e.get("event") == "ORDER_REJECTED"
                  and "SPREAD" in e.get("reason", "").upper()]
    spread_pips: dict[str, list] = defaultdict(list)
    for r in rejections:
        m_val = None
        import re
        m = re.search(r"SPREAD_TOO_WIDE[:\s]*([\d.]+)", r.get("reason", ""), re.I)
        if m:
            try:
                m_val = float(m.group(1))
                spread_pips[r.get("symbol", "?")].append(m_val)
            except ValueError:
                pass

    result = {
        "spread_rejections": len(rejections),
        "by_symbol": {},
    }
    for sym, vals in spread_pips.items():
        result["by_symbol"][sym] = {
            "count": len(vals),
            "avg_pips": round(statistics.mean(vals), 2),
            "max_pips": round(max(vals), 2),
            "expected_pips": _BACKTEST.get(f"spread_{sym.lower()}_pips", "?"),
        }
    return result


def _trade_performance(events: list[dict]) -> dict:
    """Compute live win rate, avg R, PF from POSITION_CLOSED events."""
    closed = [e for e in events if e.get("event") == "POSITION_CLOSED"]
    if not closed:
        return {"n": 0, "win_rate": None, "avg_r": None, "total_r": None,
                "pf": None, "wins": 0, "losses": 0, "gross_profit_r": 0.0,
                "gross_loss_r": 0.0, "warn": False, "low_sample_warning": True}

    results = [e.get("result_r", 0.0) for e in closed]
    wins = [r for r in results if r > 0]
    losses = [r for r in results if r < 0]
    n = len(results)
    win_rate = len(wins) / n if n else None
    avg_r = statistics.mean(results) if results else None
    total_r = sum(results)
    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0
    pf = (gross_profit / gross_loss) if gross_loss > 0 else (float("inf") if gross_profit > 0 else None)

    warn = False
    if n >= _THRESHOLDS["min_n_for_win_rate"] and win_rate is not None:
        warn = win_rate < _THRESHOLDS["win_rate_min"] or win_rate > _THRESHOLDS["win_rate_max"]

    return {
        "n": n,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 3) if win_rate is not None else None,
        "avg_r": round(avg_r, 3) if avg_r is not None else None,
        "total_r": round(total_r, 2),
        "gross_profit_r": round(gross_profit, 2),
        "gross_loss_r": round(gross_loss, 2),
        "pf": round(pf, 3) if pf is not None and not math.isinf(pf) else None,
        "warn": warn,
        "low_sample_warning": n < _THRESHOLDS["min_n_for_pf"],
    }


def _symbol_breakdown(events: list[dict]) -> dict:
    """Per-symbol breakdown of signals and closed trades."""
    signals_by_sym: dict[str, int] = defaultdict(int)
    for e in events:
        if e.get("event") == "SIGNAL_CREATED":
            signals_by_sym[e.get("symbol", "?")] += 1

    closed_by_sym: dict[str, list] = defaultdict(list)
    for e in events:
        if e.get("event") == "POSITION_CLOSED":
            closed_by_sym[e.get("symbol", "?")].append(e.get("result_r", 0.0))

    result = {}
    for sym in set(list(signals_by_sym) + list(closed_by_sym)):
        rets = closed_by_sym.get(sym, [])
        wins = [r for r in rets if r > 0]
        losses = [r for r in rets if r < 0]
        result[sym] = {
            "signals": signals_by_sym.get(sym, 0),
            "closed_trades": len(rets),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / len(rets), 3) if rets else None,
            "avg_r": round(statistics.mean(rets), 3) if rets else None,
            "backtest_win_rate": _BACKTEST.get(f"{sym.lower()[:3]}usd_net_pf_std"),
        }
    return result


# ── Report renderer ───────────────────────────────────────────────────────────

def _fmt(val, suffix: str = "", na: str = "—", decimals: int = 3) -> str:
    if val is None:
        return na
    if isinstance(val, float):
        return f"{val:.{decimals}f}{suffix}"
    return f"{val}{suffix}"


def _badge(warn: bool, critical: bool = False) -> str:
    if critical:
        return " 🔴"
    if warn:
        return " ⚠️"
    return " ✅"


def generate_report(since: Optional[datetime], now: datetime) -> tuple[str, dict]:
    since_dt = since or datetime(2021, 1, 1, tzinfo=_UTC)
    events = _load_events(since)

    freq = _signal_frequency(events, since_dt, now)
    sess = _session_distribution(events)
    sl_dist = _sl_distribution(events)
    slip = _slippage_analysis(events)
    spread = _spread_analysis(events)
    perf = _trade_performance(events)
    sym_bd = _symbol_breakdown(events)

    n_signals = freq["n_signals"]
    n_closed = perf["n"]

    lines: list[str] = []
    a = lines.append

    since_str = since_dt.strftime("%Y-%m-%d") if since else "all-time"
    a("# Live vs Backtest Validation Report")
    a(f"# Generated: {now.strftime('%Y-%m-%dT%H:%M UTC')}")
    a(f"# Period: {since_str} → now | Strategy: ST-A2 | Run: {_BACKTEST['run_id']}")
    a("")
    a("---")
    a("")

    # ── Sample size warning ───────────────────────────────────────────────────
    a("## Sample Size")
    a("")
    a("| Metric | Value |")
    a("|---|---|")
    a(f"| Signals generated | {n_signals} |")
    a(f"| Trades closed | {n_closed} |")
    a(f"| Days monitored | {freq['days_elapsed']} |")
    a(f"| Expected monthly frequency | {_BACKTEST['trades_per_month']} trades/month |")
    a("")
    if n_closed < 10:
        a("> **LOW SAMPLE WARNING:** Statistical metrics (win rate, PF) are not meaningful")
        a(f"> until n ≥ 10 closed trades. Currently {n_closed}/{10}.")
        a("> Continue collecting data. No strategy conclusions can be drawn yet.")
        a("")

    # ── 1. Signal Frequency ───────────────────────────────────────────────────
    a("## 1. Signal Frequency")
    a("")
    a("| Metric | Live | Backtest | Status |")
    a("|---|---|---|---|")
    a(f"| Signals/month | {_fmt(freq['actual_per_month'])} | {_fmt(freq['expected_per_month'])} | "
      f"{'⚠️ Below 50% of expected' if freq['warn'] else '✅ OK (or too early to judge)'} |")
    a(f"| Total signals | {n_signals} | ~{round(_BACKTEST['trades_per_month'] * freq['days_elapsed'] / 30.44, 1)} expected | — |")
    a("")
    if freq["days_elapsed"] < 30:
        a(f"> Too early to judge frequency (only {freq['days_elapsed']} days elapsed).")
        a(f"> Backtest baseline: {_BACKTEST['trades_per_month']:.1f}/month.")
        a("> A full judgment requires ≥30 days of data.")
        a("")

    # ── 2. Session Distribution ────────────────────────────────────────────────
    a("## 2. Session Distribution")
    a("")
    a("| Session | Live Count | Live % | Backtest % | Status |")
    a("|---|---|---|---|---|")
    if sess["n"] > 0:
        a(f"| London | {sess['london_count']} | {_fmt(sess['london_pct'], '%')} | "
          f"{sess['backtest_london_pct']}% | {'⚠️ Unusually high' if sess['warn'] else '✅'} |")
        a(f"| New York | {sess['ny_count']} | {_fmt(sess['ny_pct'], '%')} | "
          f"{sess['backtest_ny_pct']}% | ✅ |")
    else:
        a(f"| London | 0 | — | {sess['backtest_london_pct']}% | — |")
        a(f"| New York | 0 | — | {sess['backtest_ny_pct']}% | — |")
    a("")
    a("> **Note:** NY session is the primary edge driver (PF 1.731 vs London 0.949).")
    a("> If NY trades drop below 20% of total, edge deterioration risk is HIGH.")
    a("")

    # ── 3. SL Distribution ────────────────────────────────────────────────────
    a("## 3. Stop-Loss Distance Distribution")
    a("")
    a("| Metric | Live | Backtest Gate | Status |")
    a("|---|---|---|---|")
    a(f"| Avg SL (pips) | {_fmt(sl_dist.get('avg_sl_pips'))} | ≥5.0 pip floor | "
      f"{'⚠️ Check' if sl_dist.get('warn') else '✅'} |")
    a(f"| Min SL (pips) | {_fmt(sl_dist.get('min_sl_pips'))} | ≥5.0 | "
      f"{'🔴 VIOLATION' if sl_dist.get('below_5pip_floor', 0) > 0 else '✅'} |")
    a(f"| Max SL (pips) | {_fmt(sl_dist.get('max_sl_pips'))} | — | — |")
    a(f"| Trades below 5-pip floor | {sl_dist.get('below_5pip_floor', 0)} | 0 | "
      f"{'🔴 CRITICAL' if sl_dist.get('below_5pip_floor', 0) > 0 else '✅'} |")
    a("")
    if sl_dist.get("below_5pip_floor", 0) > 0:
        a("> **CRITICAL:** Trades with SL < 5 pips should have been filtered by ST-A2 gate.")
        a("> This indicates a code regression in the min_sl_pips filter. Investigate immediately.")
        a("")

    # ── 4. Slippage ───────────────────────────────────────────────────────────
    a("## 4. Entry Slippage (Signal vs Fill)")
    a("")
    if slip["n"] == 0:
        a("No ORDER_FILLED events yet (no trades have been placed on live account).")
        a("")
        a("| Metric | Backtest Assumption | Status |")
        a("|---|---|---|")
        a("| Slippage | 0 pips (bar-close execution) | — pending data — |")
    else:
        a("| Metric | Value | Threshold | Status |")
        a("|---|---|---|---|")
        a(f"| Samples | {slip['n']} | — | — |")
        a(f"| Avg slippage | {_fmt(slip['avg_slippage_pips'], ' pips')} | < 1.0 pip | "
          f"{_badge(slip['warn'], slip['critical'])} |")
        a(f"| Max slippage | {_fmt(slip['max_slippage_pips'], ' pips')} | — | — |")
        a(f"| % adverse fills | {_fmt(slip['pct_adverse'], '%')} | — | — |")
    a("")
    a("> **Note:** Backtest uses bar-close entry price. Live fills may differ due to spread")
    a("> at execution time. Slippage > 1 pip consistently suggests a timing or broker issue.")
    a("")

    # ── 5. Spread Analysis ────────────────────────────────────────────────────
    a("## 5. Spread at Execution")
    a("")
    a("| Pair | Backtest Model | Live Rejections | Max Live Spread |")
    a("|---|---|---|---|")
    for sym in ["EURUSD", "GBPUSD"]:
        key = f"spread_{sym.lower()}_pips"
        expected = _BACKTEST.get(key, "?")
        sym_data = spread["by_symbol"].get(sym, {})
        a(f"| {sym} | {expected} pip | {sym_data.get('count', 0)} rejections | "
          f"{_fmt(sym_data.get('max_pips'))} pips |")
    a("")
    a(f"Total spread rejections: {spread['spread_rejections']}")
    a("")
    a("> Spread rejections indicate the bot correctly filtered high-spread conditions.")
    a("> Monitor for patterns: news-time spikes, pre-open widening, session rollover.")
    a("")

    # ── 6. Trade Performance ─────────────────────────────────────────────────
    a("## 6. Trade Performance (Closed Trades)")
    a("")
    a("| Metric | Live | Backtest (ST-A2) | Status |")
    a("|---|---|---|---|")
    a(f"| Closed trades | {n_closed} | 169 (5yr) | "
      f"{'⚠️ Low sample' if perf['low_sample_warning'] else '—'} |")
    a(f"| Win rate | {_fmt(perf['win_rate'], '%', decimals=1) if perf['win_rate'] else '—'} | "
      f"32.0% | {'⚠️ Deviation' if perf['warn'] else ('— (need n≥10)' if n_closed < 10 else '✅')} |")
    a(f"| Average R | {_fmt(perf['avg_r'])} | 0.108 | "
      f"{'⚠️' if perf['avg_r'] is not None and perf['avg_r'] < _THRESHOLDS['avg_r_min'] else '—'} |")
    a(f"| Total R | {_fmt(perf['total_r'])} | — | — |")
    a(f"| Profit Factor | {_fmt(perf['pf'])} | 1.151 (std) | "
      f"{'— (need n≥20)' if n_closed < 20 else '✅' if perf['pf'] and perf['pf'] > 1.0 else '⚠️'} |")
    a("")
    if perf["low_sample_warning"]:
        a(f"> **Low sample warning:** Need ≥{_THRESHOLDS['min_n_for_pf']} closed trades for")
        a(f"> statistically meaningful PF. Currently {n_closed}.")
        a("")

    # ── 7. Symbol Breakdown ───────────────────────────────────────────────────
    if sym_bd:
        a("## 7. Symbol Breakdown")
        a("")
        a("| Symbol | Signals | Trades | Win% | Avg R |")
        a("|---|---|---|---|---|")
        for sym, d in sorted(sym_bd.items()):
            a(f"| {sym} | {d['signals']} | {d['closed_trades']} | "
              f"{_fmt(d['win_rate'], '%', decimals=1) if d['win_rate'] else '—'} | "
              f"{_fmt(d['avg_r']) if d['avg_r'] is not None else '—'} |")
        a("")

    # ── 8. Drift Summary ─────────────────────────────────────────────────────
    a("## 8. Drift Summary")
    a("")
    flags = []
    if freq["warn"]:
        flags.append("🟡 SIGNAL_FREQUENCY: below 50% of expected rate (check session classification)")
    if sess["warn"]:
        flags.append("🟡 SESSION_DIST: London > 85% — NY signals may be missed")
    if sl_dist.get("below_5pip_floor", 0) > 0:
        flags.append("🔴 SL_FLOOR_VIOLATION: trades with SL < 5 pip detected (ST-A2 filter regression)")
    if slip["n"] > 0 and slip.get("critical"):
        flags.append("🔴 SLIPPAGE_CRITICAL: average slippage > 2 pip — broker execution issue")
    elif slip["n"] > 0 and slip.get("warn"):
        flags.append("🟡 SLIPPAGE_HIGH: average slippage > 1 pip — monitor")
    if perf["warn"]:
        flags.append("🟡 WIN_RATE_DEVIATION: outside 20-60% band over n≥10 trades")

    if not flags:
        a("✅ No drift flags. All metrics within expected bands.")
        a("")
        if n_signals == 0:
            a("> No signals yet — all checks are in PENDING state (no data to compare).")
        a("")
    else:
        a("| # | Flag | Severity |")
        a("|---|---|---|")
        for i, f in enumerate(flags, 1):
            sev = "🔴 CRITICAL" if f.startswith("🔴") else "🟡 WARNING"
            a(f"| {i} | {f} | {sev} |")
        a("")

    # ── Footer ────────────────────────────────────────────────────────────────
    a("---")
    a("")
    a("## Reference: ST-A2 Backtest Benchmarks")
    a("")
    a("| Metric | Value |")
    a("|---|---|")
    a("| Strategy | ST-A2 (min_sl_pips=5.0) |")
    a(f"| Run ID | {_BACKTEST['run_id']} |")
    a("| Pairs | EURUSD + GBPUSD |")
    a("| Data period | 4.9 years |")
    a("| Trade count | 169 |")
    a("| Win rate | 32.0% |")
    a("| Net PF (std) | 1.151 |")
    a("| Net PF (2×) | 1.025 |")
    a("| Max DD | 18.72 R |")
    a("| London PF (std) | 0.949 |")
    a("| NY PF (std) | 1.731 |")
    a("| EURUSD PF (2×) | 0.945 ⚠️ |")
    a("| GBPUSD PF (2×) | 1.168 ✅ |")
    a("")
    a(f"*Generated by `research/live_vs_backtest_validator.py` at {now.strftime('%Y-%m-%dT%H:%M UTC')}*")
    a("")

    result_dict = {
        "generated_at": now.isoformat(),
        "period_since": since_dt.isoformat(),
        "n_signals": n_signals,
        "n_closed_trades": n_closed,
        "frequency": freq,
        "session_distribution": sess,
        "sl_distribution": sl_dist,
        "slippage": {k: v for k, v in slip.items() if k != "samples"},
        "spread": spread,
        "performance": perf,
        "symbol_breakdown": sym_bd,
        "drift_flags": flags,
        "backtest_reference": _BACKTEST,
    }
    return "\n".join(lines), result_dict


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Live vs Backtest Validator")
    parser.add_argument("--since", default=None,
                        help="Start date for analysis (YYYY-MM-DD), default: all-time")
    parser.add_argument("--out", default=None,
                        help="Markdown output path (default: reports/live_vs_backtest.md)")
    parser.add_argument("--json", action="store_true", dest="emit_json",
                        help="Also print JSON summary to stdout")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress markdown stdout output")
    args = parser.parse_args()

    now = datetime.now(_UTC)
    since: Optional[datetime] = None
    if args.since:
        since = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=_UTC)

    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out) if args.out else _REPORTS_DIR / "live_vs_backtest.md"

    report_md, report_json = generate_report(since, now)
    out_path.write_text(report_md, encoding="utf-8")

    if not args.quiet:
        print(report_md)

    if args.emit_json:
        print(json.dumps(report_json, indent=2, default=str))

    import sys
    print(f"\n✅  Report written → {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()

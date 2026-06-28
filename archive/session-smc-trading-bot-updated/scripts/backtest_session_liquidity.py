#!/usr/bin/env python3
"""
SA-08 — Phase-0 backtest for Strategy A (Session Liquidity Reversal).

Usage:
    python3 scripts/backtest_session_liquidity.py
    python3 scripts/backtest_session_liquidity.py --costs-json config/costs.json

--costs-json FILE
    Load spread costs from FILE (a costs.json with active_profile set).
    If omitted, the hardcoded SPREAD_PIPS defaults are used (original Phase-0 run).
    Used by the E6 cost revalidation pipeline (run_e6_revalidation.sh).

Outputs:
    docs/BACKTEST_RESULTS.md          — summary + per-year + per-session tables
    docs/BACKTEST_FAILURE_ANALYSIS.md — only if gate fails
    research/backtest_runs.csv        — appended
    research/trades.csv               — appended

Phase-0 gate (must ALL pass in same RR variant, combined EURUSD + GBPUSD):
    Trades ≥ 100  AND  Net PF (std) > 1.0  AND  Net PF (2×) > 1.0

Measures only. No broker execution. No live trading.
"""

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from strategy.session_liquidity.session_strategy import run_strategy
from research.logger import (
    BacktestRun, TradeRecord,
    log_backtest_run, log_trade, generate_run_id, new_trade_id,
)

# ── Constants ─────────────────────────────────────────────────────────────────

RR_VARIANTS = [2.0, 3.0, 4.0, 5.0]
MAX_TRADE_BARS = 96        # 24 hours at M15
_PIP = 0.0001              # both EURUSD and GBPUSD are 4-decimal pip pairs

SPREAD_PIPS = {
    "EURUSD": {"standard": 1.4, "2x": 2.8},
    "GBPUSD": {"standard": 1.8, "2x": 3.6},
}
SYMBOLS = ["EURUSD", "GBPUSD"]

CSV_FILES = {
    "EURUSD": {"m15": "EUR_USD_M15.csv", "h4": "EUR_USD_H4.csv"},
    "GBPUSD": {"m15": "GBP_USD_M15.csv", "h4": "GBP_USD_H4.csv"},
}

PHASE0_MIN_TRADES = 100
PHASE0_MIN_PF     = 1.0


# ── Pure simulation functions (importable for tests) ──────────────────────────

def simulate_trade(entry, sl, side, rr, future_bars, max_bars=MAX_TRADE_BARS):
    """
    Walk M15 bars forward and determine trade outcome.

    Rules (per BACKTEST_SPEC):
    - SL is checked BEFORE TP within the same bar.
    - Entry at close of displacement candle; first checked bar is the next one.
    - Max 96 bars (24 hours); timeout = close at last bar.

    Returns:
        outcome    : "win" | "loss" | "timeout"
        gross_r    : +rr (win) | -1.0 (loss) | fractional (timeout)
        exit_price : float
        exit_time  : bar["time"] string (or "" on empty timeout)
        bars_held  : int
    """
    risk = abs(entry - sl)
    if risk == 0:
        return "timeout", 0.0, entry, "", 0

    tp = (entry + risk * rr) if side == "long" else (entry - risk * rr)
    bars = future_bars[:max_bars]

    for i, bar in enumerate(bars):
        h = float(bar["high"])
        lo = float(bar["low"])
        if side == "long":
            if lo <= sl:
                return "loss", -1.0, sl, bar["time"], i + 1
            if h >= tp:
                return "win", rr, tp, bar["time"], i + 1
        else:
            if h >= sl:
                return "loss", -1.0, sl, bar["time"], i + 1
            if lo <= tp:
                return "win", rr, tp, bar["time"], i + 1

    if bars:
        last = bars[-1]
        exit_p = float(last["close"])
        raw = (exit_p - entry) / risk if side == "long" else (entry - exit_p) / risk
        return "timeout", raw, exit_p, last["time"], len(bars)

    return "timeout", 0.0, entry, "", 0


def spread_cost_r(spread_pips_rt, sl_pips):
    """Return spread cost expressed as a fraction of 1R."""
    if sl_pips <= 0:
        return 0.0
    return spread_pips_rt / sl_pips


def compute_metrics(net_rs):
    """
    Compute backtest statistics from a list of net-R trade outcomes.

    Returns a dict with: trade_count, win_count, loss_count,
    win_rate, avg_r, net_pf, total_net_r, max_dd.
    """
    if not net_rs:
        return {
            "trade_count": 0, "win_count": 0, "loss_count": 0,
            "win_rate": 0.0, "avg_r": 0.0, "net_pf": 0.0,
            "total_net_r": 0.0, "max_dd": 0.0,
        }

    wins   = [r for r in net_rs if r > 0]
    losses = [r for r in net_rs if r <= 0]

    gross_wins   = sum(wins)
    gross_losses = abs(sum(losses))

    if gross_losses == 0:
        net_pf = float("inf") if gross_wins > 0 else 1.0
    elif gross_wins == 0:
        net_pf = 0.0
    else:
        net_pf = gross_wins / gross_losses

    return {
        "trade_count": len(net_rs),
        "win_count":   len(wins),
        "loss_count":  len(losses),
        "win_rate":    len(wins) / len(net_rs),
        "avg_r":       sum(net_rs) / len(net_rs),
        "net_pf":      net_pf,
        "total_net_r": sum(net_rs),
        "max_dd":      max_drawdown(net_rs),
    }


def max_drawdown(net_rs):
    """Peak-to-trough drawdown expressed in R units."""
    peak = running = max_dd = 0.0
    for r in net_rs:
        running += r
        if running > peak:
            peak = running
        dd = peak - running
        if dd > max_dd:
            max_dd = dd
    return max_dd


# ── Data helpers ──────────────────────────────────────────────────────────────

def load_csv(path):
    """Load OHLCV CSV into list of dicts. OHLCV values are floats; time stays string."""
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append({
                "time":   row["time"],
                "open":   float(row["open"]),
                "high":   float(row["high"]),
                "low":    float(row["low"]),
                "close":  float(row["close"]),
                "volume": float(row.get("volume", 0.0)),
            })
    return rows


def build_time_index(bars):
    """Map time string → position index in bars list."""
    return {b["time"]: i for i, b in enumerate(bars)}


# ── Debug event parsing ───────────────────────────────────────────────────────

def extract_contexts(events):
    """
    Parse run_strategy() debug events to extract per-trade context:
    asian range, sweep bar time, and htf bias.

    Returns:
        asian  : dict  date_str → {high, low, range_pips}
        sweeps : dict  (date_str, session) → {time_iso, bias}
                 Uses the LAST sweep before a signal (overwrites earlier timeouts).
    """
    asian  = {}
    sweeps = {}

    for ev in events:
        date    = ev["date"]
        etype   = ev["event"]
        detail  = ev["detail"]

        if etype == "ASIAN_RANGE":
            m = re.search(r"H=([\d.]+) L=([\d.]+) range=([\d.]+)pip", detail)
            if m:
                asian[date] = {
                    "high":       float(m.group(1)),
                    "low":        float(m.group(2)),
                    "range_pips": float(m.group(3)),
                }

        elif etype == "SWEEP":
            m_sess = re.search(r"\] (\w+) side=", detail)
            m_bias = re.search(r"bias=(\w+)", detail)
            m_time = re.search(r"\[(\d{2}:\d{2}) UTC\]", detail)
            if m_sess and m_bias:
                session  = m_sess.group(1)
                bias     = m_bias.group(1)
                bar_hhmm = m_time.group(1) if m_time else "00:00"
                time_iso = f"{date}T{bar_hhmm}:00Z"
                sweeps[(date, session)] = {"time_iso": time_iso, "bias": bias}

    return asian, sweeps


# ── Trade simulation loop ─────────────────────────────────────────────────────

def _run_rr(signals_by_sym, bars_by_sym, time_idx_by_sym, rr):
    """
    Simulate all signals for a given RR variant across all symbols.

    Returns list of trade dicts, one per signal that can be indexed.
    Each dict contains: sym, sig, rr, outcome, gross_r, std_net_r,
    stress_net_r, exit_price, exit_time, bars_held, sl_pips,
    std_spread, stress_spread, std_cost_r, stress_cost_r.
    """
    trades = []

    for sym in SYMBOLS:
        signals  = signals_by_sym[sym]
        bars     = bars_by_sym[sym]
        time_idx = time_idx_by_sym[sym]
        std_sp   = SPREAD_PIPS[sym]["standard"]
        stress_sp = SPREAD_PIPS[sym]["2x"]

        for sig in signals:
            sig_time = sig.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
            idx = time_idx.get(sig_time)
            if idx is None:
                print(f"  WARN: signal bar not found in index: {sig_time} ({sym})")
                continue

            future_bars = bars[idx + 1:]
            outcome, gross_r, exit_p, exit_t, n_bars = simulate_trade(
                sig.entry, sig.stop_loss, sig.side, rr, future_bars
            )

            sl_pips = abs(sig.entry - sig.stop_loss) / _PIP
            cost_std    = spread_cost_r(std_sp,    sl_pips)
            cost_stress = spread_cost_r(stress_sp, sl_pips)

            trades.append({
                "sym":          sym,
                "sig":          sig,
                "rr":           rr,
                "outcome":      outcome,
                "gross_r":      gross_r,
                "std_net_r":    gross_r - cost_std,
                "stress_net_r": gross_r - cost_stress,
                "exit_price":   exit_p,
                "exit_time":    exit_t,
                "bars_held":    n_bars,
                "sl_pips":      sl_pips,
                "std_spread":   std_sp,
                "stress_spread": stress_sp,
                "std_cost_r":   cost_std,
                "stress_cost_r": cost_stress,
            })

    return trades


# ── Per-breakdown helpers ─────────────────────────────────────────────────────

def _year_rows(trades, rs_key="std_net_r"):
    """Return list of (year, count, win_rate, net_pf, flag) tuples sorted by year."""
    by_year = {}
    for t in trades:
        yr = t["sig"].timestamp.year
        by_year.setdefault(yr, []).append(t[rs_key])
    rows = []
    for yr in sorted(by_year):
        m = compute_metrics(by_year[yr])
        flag = " ⚠" if m["net_pf"] < PHASE0_MIN_PF and m["trade_count"] >= 5 else ""
        rows.append((yr, m["trade_count"], m["win_rate"], m["net_pf"], flag))
    return rows


def _session_rows(trades, rs_key="std_net_r"):
    """Return list of (session, count, win_rate, net_pf) tuples."""
    by_sess = {}
    for t in trades:
        sess = t["sig"].session
        by_sess.setdefault(sess, []).append(t[rs_key])
    rows = []
    for sess in sorted(by_sess):
        m = compute_metrics(by_sess[sess])
        rows.append((sess, m["trade_count"], m["win_rate"], m["net_pf"]))
    return rows


def _sym_metrics(trades, sym, rs_key):
    rs = [t[rs_key] for t in trades if t["sym"] == sym]
    return compute_metrics(rs)


# ── Report writers ────────────────────────────────────────────────────────────

def _pct(v):
    return f"{v * 100:.1f}%"


def _pf(v):
    if v == float("inf"):
        return "∞"
    return f"{v:.3f}"


def write_results(run_id, all_rr_data, best_rr, today_utc):
    """Generate docs/BACKTEST_RESULTS.md."""
    lines = [
        "# BACKTEST_RESULTS.md",
        "# Strategy A — Session Liquidity Reversal — Phase-0 Gate",
        f"# Run: {run_id}  |  Date: {today_utc}",
        "",
        "---",
        "",
        "## Summary Table",
        "(ranked by Net PF std, then Trade Count)",
        "",
        "| RR | Trades | Win% | Avg R | Gross PF | Net PF (std) | Net PF (2×) | Max DD (R) | Verdict |",
        "|---|---|---|---|---|---|---|---|---|",
    ]

    sorted_rrs = sorted(
        all_rr_data.keys(),
        key=lambda r: (
            -all_rr_data[r]["std_metrics"]["net_pf"],
            -all_rr_data[r]["std_metrics"]["trade_count"],
        )
    )

    for rr in sorted_rrs:
        d   = all_rr_data[rr]
        sm  = d["std_metrics"]
        verdict = "**PASS**" if d["gate"] else "FAIL"
        lines.append(
            f"| {rr:.0f} | {sm['trade_count']} | {_pct(sm['win_rate'])} "
            f"| {sm['avg_r']:.3f} | {_pf(d['gross_pf'])} "
            f"| {_pf(sm['net_pf'])} | {_pf(d['stress_metrics']['net_pf'])} "
            f"| {sm['max_dd']:.2f} | {verdict} |"
        )

    # Gate verdict
    any_pass = any(d["gate"] for d in all_rr_data.values())
    lines += [
        "",
        "---",
        "",
        "## Phase-0 Gate",
        f"Condition: Trades ≥ {PHASE0_MIN_TRADES} AND Net PF (std) > {PHASE0_MIN_PF} "
        f"AND Net PF (2×) > {PHASE0_MIN_PF}",
        "",
        "| RR | Trades | Net PF (std) | Net PF (2×) | Gate |",
        "|---|---|---|---|---|",
    ]
    for rr in RR_VARIANTS:
        d   = all_rr_data[rr]
        sm  = d["std_metrics"]
        stm = d["stress_metrics"]
        g   = "✅ PASS" if d["gate"] else "❌ FAIL"
        lines.append(
            f"| {rr:.0f} | {sm['trade_count']} "
            f"| {_pf(sm['net_pf'])} | {_pf(stm['net_pf'])} | {g} |"
        )

    verdict_str = "✅ PASS — demo trading unlocked (subject to Phase-1 paper trade)" \
                  if any_pass else "❌ FAIL — strategy does not meet Phase-0 gate"
    lines += ["", f"### FINAL VERDICT: {verdict_str}", "", "---", ""]

    # Per-symbol breakdown for best (or first) RR
    ref_rr = best_rr if best_rr in all_rr_data else RR_VARIANTS[0]
    ref_trades = all_rr_data[ref_rr]["trades"]

    lines += [f"## Per-Symbol Breakdown (RR {ref_rr:.0f})", ""]
    for sym in SYMBOLS:
        sm_std    = _sym_metrics(ref_trades, sym, "std_net_r")
        sm_stress = _sym_metrics(ref_trades, sym, "stress_net_r")
        lines += [
            f"### {sym}",
            "",
            "| Metric | Standard | 2× Stress |",
            "|---|---|---|",
            f"| Trades | {sm_std['trade_count']} | {sm_stress['trade_count']} |",
            f"| Win Rate | {_pct(sm_std['win_rate'])} | {_pct(sm_stress['win_rate'])} |",
            f"| Avg R | {sm_std['avg_r']:.3f} | {sm_stress['avg_r']:.3f} |",
            f"| Net PF | {_pf(sm_std['net_pf'])} | {_pf(sm_stress['net_pf'])} |",
            f"| Max DD | {sm_std['max_dd']:.2f}R | {sm_stress['max_dd']:.2f}R |",
            f"| Total R | {sm_std['total_net_r']:.2f} | {sm_stress['total_net_r']:.2f} |",
            "",
        ]

    # Per-year
    yr_rows = _year_rows(ref_trades, "std_net_r")
    lines += [
        f"## Per-Year Breakdown (combined, RR {ref_rr:.0f}, standard spread)",
        "",
        "| Year | Trades | Win% | Net PF |",
        "|---|---|---|---|",
    ]
    for yr, cnt, wr, pf_val, flag in yr_rows:
        lines.append(f"| {yr} | {cnt} | {_pct(wr)} | {_pf(pf_val)}{flag} |")

    # Per-session
    sess_rows = _session_rows(ref_trades, "std_net_r")
    lines += [
        "",
        f"## Per-Session Breakdown (combined, RR {ref_rr:.0f}, standard spread)",
        "",
        "| Session | Trades | Win% | Net PF |",
        "|---|---|---|---|",
    ]
    for sess, cnt, wr, pf_val in sess_rows:
        lines += [f"| {sess} | {cnt} | {_pct(wr)} | {_pf(pf_val)} |"]

    lines += ["", "---", "", f"*Data: {today_utc}*"]

    out = _ROOT / "docs" / "BACKTEST_RESULTS.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"[+] Written: {out.relative_to(_ROOT)}")


def write_failure_analysis(run_id, all_rr_data, today_utc):
    """Generate docs/BACKTEST_FAILURE_ANALYSIS.md — only written if gate fails."""
    lines = [
        "# BACKTEST_FAILURE_ANALYSIS.md",
        "# Strategy A — Phase-0 FAIL — Root Cause Analysis",
        f"# Run: {run_id}  |  Date: {today_utc}",
        "",
        "---",
        "",
        "## Failure Summary",
        "",
        "No RR variant passed the Phase-0 gate "
        f"(Trades ≥ {PHASE0_MIN_TRADES} AND Net PF (std+2×) > {PHASE0_MIN_PF}).",
        "",
        "| RR | Trades | Net PF (std) | Net PF (2×) | Failure reason |",
        "|---|---|---|---|---|",
    ]
    for rr in RR_VARIANTS:
        d   = all_rr_data[rr]
        sm  = d["std_metrics"]
        stm = d["stress_metrics"]
        reasons = []
        if sm["trade_count"] < PHASE0_MIN_TRADES:
            reasons.append(f"trade_count={sm['trade_count']} < {PHASE0_MIN_TRADES}")
        if sm["net_pf"] <= PHASE0_MIN_PF:
            reasons.append(f"Net PF std={_pf(sm['net_pf'])} ≤ {PHASE0_MIN_PF}")
        if stm["net_pf"] <= PHASE0_MIN_PF:
            reasons.append(f"Net PF 2×={_pf(stm['net_pf'])} ≤ {PHASE0_MIN_PF}")
        lines.append(
            f"| {rr:.0f} | {sm['trade_count']} "
            f"| {_pf(sm['net_pf'])} | {_pf(stm['net_pf'])} | {'; '.join(reasons)} |"
        )

    # Diagnostic breakdown — pick RR with best net PF for digging deeper
    best_rr = max(all_rr_data, key=lambda r: all_rr_data[r]["std_metrics"]["net_pf"])
    ref_trades = all_rr_data[best_rr]["trades"]

    lines += [
        "",
        f"## Diagnostic: Best RR = {best_rr:.0f}",
        "",
        "### Per-Year (standard spread)",
        "",
        "| Year | Trades | Win% | Net PF |",
        "|---|---|---|---|",
    ]
    for yr, cnt, wr, pf_val, flag in _year_rows(ref_trades, "std_net_r"):
        lines.append(f"| {yr} | {cnt} | {_pct(wr)} | {_pf(pf_val)}{flag} |")

    lines += [
        "",
        "### Per-Session (standard spread)",
        "",
        "| Session | Trades | Win% | Net PF |",
        "|---|---|---|---|",
    ]
    for sess, cnt, wr, pf_val in _session_rows(ref_trades, "std_net_r"):
        lines += [f"| {sess} | {cnt} | {_pct(wr)} | {_pf(pf_val)} |"]

    lines += [
        "",
        "---",
        "",
        "## Next Steps",
        "",
        "1. Review per-year and per-session breakdowns above for regime dependency.",
        "2. If trade count < 100: check data coverage in `docs/DATA_AUDIT.md`.",
        "3. Review `docs/VERDICT_LOG.md` for similar prior failures.",
        "4. A parameter change = new trial. Do NOT re-run on same trial ID.",
        "",
        f"*Generated: {today_utc}*",
    ]

    out = _ROOT / "docs" / "BACKTEST_FAILURE_ANALYSIS.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"[+] Written: {out.relative_to(_ROOT)}")


# ── Research CSV logging ──────────────────────────────────────────────────────

def _log_trades(run_id, rr, trades, contexts_by_sym):
    """Append one TradeRecord per trade (std spread) to research/trades.csv."""
    for t in trades:
        sig  = t["sig"]
        sym  = t["sym"]
        date_str = str(sig.timestamp.date())
        ctx_asian, ctx_sweeps = contexts_by_sym[sym]
        ar   = ctx_asian.get(date_str, {})
        sw   = ctx_sweeps.get((date_str, sig.session), {})

        exit_reason = {"win": "tp", "loss": "sl", "timeout": "timeout"}[t["outcome"]]

        rec = TradeRecord(
            trade_id              = new_trade_id(),
            run_id                = run_id,
            timestamp_utc         = sig.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            symbol                = sym,
            session               = sig.session,
            side                  = sig.side,
            entry                 = round(sig.entry, 5),
            stop_loss             = round(sig.stop_loss, 5),
            take_profit           = round(
                sig.entry + abs(sig.entry - sig.stop_loss) * rr
                if sig.side == "long"
                else sig.entry - abs(sig.entry - sig.stop_loss) * rr,
                5,
            ),
            sl_pips               = round(t["sl_pips"], 2),
            rr                    = rr,
            exit_price            = round(t["exit_price"], 5),
            exit_reason           = exit_reason,
            bars_held             = t["bars_held"],
            gross_r               = round(t["gross_r"], 4),
            spread_cost_r         = round(t["std_cost_r"], 4),
            net_r                 = round(t["std_net_r"], 4),
            asian_high            = round(ar.get("high", 0.0), 5),
            asian_low             = round(ar.get("low", 0.0), 5),
            asian_range_pips      = round(ar.get("range_pips", 0.0), 1),
            htf_bias              = sw.get("bias", ""),
            sweep_bar_time        = sw.get("time_iso", ""),
            displacement_bar_time = sig.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            notes                 = f"2x_net_r={t['stress_net_r']:.4f}",
        )
        log_trade(rec)


def _log_runs(run_id, rr, trades, all_rr_data, gate, today_utc, data_start, data_end):
    """Append one BacktestRun per symbol to research/backtest_runs.csv."""
    for sym in SYMBOLS:
        sym_trades = [t for t in trades if t["sym"] == sym]
        sm_std    = _sym_metrics(sym_trades, sym, "std_net_r")
        sm_stress = _sym_metrics(sym_trades, sym, "stress_net_r")
        sm_gross  = _sym_metrics(sym_trades, sym, "gross_r")

        rec = BacktestRun(
            run_id           = run_id,
            timestamp_utc    = today_utc,
            strategy_id      = "SA",
            strategy_version = "1.0.0",
            symbol           = sym,
            timeframe        = "M15",
            start_date       = data_start.get(sym, ""),
            end_date         = data_end.get(sym, ""),
            rr               = rr,
            spread_model     = "combined",
            spread_pips      = SPREAD_PIPS[sym]["standard"],
            trade_count      = sm_std["trade_count"],
            win_count        = sm_std["win_count"],
            loss_count       = sm_std["loss_count"],
            gross_pf         = round(sm_gross["net_pf"], 4)
                               if sm_gross["net_pf"] != float("inf") else 99.99,
            net_pf_std       = round(sm_std["net_pf"], 4)
                               if sm_std["net_pf"] != float("inf") else 99.99,
            net_pf_2x        = round(sm_stress["net_pf"], 4)
                               if sm_stress["net_pf"] != float("inf") else 99.99,
            win_rate_pct     = round(sm_std["win_rate"] * 100, 1),
            avg_r            = round(sm_std["avg_r"], 4),
            max_dd_r         = round(sm_std["max_dd"], 4),
            total_net_r      = round(sm_std["total_net_r"], 4),
            gate_passed      = gate,
            notes            = f"combined_gate={'PASS' if gate else 'FAIL'}",
        )
        log_backtest_run(rec)


# ── Main ──────────────────────────────────────────────────────────────────────

def _load_costs_from_json(path):
    """
    Load SPREAD_PIPS overrides from a costs.json file.

    Reads active_profile → profiles[profile][sym] → {standard, stress2x}.
    Mutates the module-level SPREAD_PIPS dict in place.
    Aborts if any required symbol has null values (vantage_measured not yet filled).
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    profile_name = data.get("active_profile")
    if not profile_name:
        print("[ERROR] costs.json missing 'active_profile' key.")
        raise SystemExit(1)
    profile = data.get("profiles", {}).get(profile_name)
    if profile is None:
        print(f"[ERROR] Profile '{profile_name}' not found in costs.json.")
        raise SystemExit(1)

    print(f"[+] Cost profile: {profile_name}  (from {path})")
    for sym in SYMBOLS:
        sym_costs = profile.get(sym)
        if sym_costs is None:
            print(f"[ERROR] Symbol '{sym}' not in profile '{profile_name}'.")
            raise SystemExit(1)
        std_val    = sym_costs.get("standard")
        stress_val = sym_costs.get("stress2x")
        if std_val is None or stress_val is None:
            print(
                f"[ERROR] {sym} in profile '{profile_name}' has null costs. "
                f"Run export_spread_limits.py first."
            )
            raise SystemExit(1)
        SPREAD_PIPS[sym]["standard"] = float(std_val)
        SPREAD_PIPS[sym]["2x"]       = float(stress_val)
        print(f"    {sym}: std={SPREAD_PIPS[sym]['standard']} pip, 2x={SPREAD_PIPS[sym]['2x']} pip")


def main():
    parser = argparse.ArgumentParser(description="SA-08 Phase-0 backtest")
    parser.add_argument(
        "--costs-json", metavar="FILE",
        help="Path to costs.json — overrides hardcoded SPREAD_PIPS using active_profile",
    )
    args = parser.parse_args()

    if args.costs_json:
        _load_costs_from_json(args.costs_json)

    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id    = generate_run_id()
    data_dir  = _ROOT / "data" / "historical"

    print(f"\n=== SA-08 Phase-0 Backtest | run_id={run_id} ===\n")

    # ── Load data ──────────────────────────────────────────────────────────────
    bars_by_sym    = {}
    time_idx_by_sym = {}
    h4_by_sym      = {}
    data_start     = {}
    data_end       = {}

    for sym in SYMBOLS:
        m15_path = data_dir / CSV_FILES[sym]["m15"]
        h4_path  = data_dir / CSV_FILES[sym]["h4"]

        if not m15_path.exists():
            print(f"  ERROR: missing {m15_path}")
            sys.exit(1)
        if not h4_path.exists():
            print(f"  ERROR: missing {h4_path}")
            sys.exit(1)

        print(f"[+] Loading {sym} M15 ...", end=" ", flush=True)
        m15_bars = load_csv(m15_path)
        m15_bars.sort(key=lambda b: b["time"])
        bars_by_sym[sym]     = m15_bars
        time_idx_by_sym[sym] = build_time_index(m15_bars)
        data_start[sym]      = m15_bars[0]["time"][:10]  if m15_bars else ""
        data_end[sym]        = m15_bars[-1]["time"][:10] if m15_bars else ""
        print(f"{len(m15_bars):,} bars  ({data_start[sym]} → {data_end[sym]})")

        print(f"[+] Loading {sym} H4  ...", end=" ", flush=True)
        h4_bars = load_csv(h4_path)
        h4_bars.sort(key=lambda b: b["time"])
        h4_by_sym[sym] = h4_bars
        print(f"{len(h4_bars):,} bars")

    # ── Generate signals (RR-independent; run once per symbol) ────────────────
    print("\n[+] Running strategy signal generation ...")
    signals_by_sym   = {}
    contexts_by_sym  = {}  # sym → (asian_dict, sweeps_dict)

    for sym in SYMBOLS:
        print(f"    {sym} ...", end=" ", flush=True)
        sigs, events = run_strategy(
            bars_by_sym[sym],
            h4_by_sym[sym],
            sym,
            config={"rr": 2.0},   # RR here only affects sig.take_profit; we recompute per variant
            debug=True,
        )
        signals_by_sym[sym]  = sigs
        contexts_by_sym[sym] = extract_contexts(events)
        print(f"{len(sigs)} signals")

    total_signals = sum(len(v) for v in signals_by_sym.values())
    print(f"    Total signals: {total_signals}")

    # ── Simulate for each RR variant ──────────────────────────────────────────
    print("\n[+] Simulating trades ...")
    all_rr_data = {}

    for rr in RR_VARIANTS:
        print(f"    RR={rr:.0f} ...", end=" ", flush=True)
        trades = _run_rr(signals_by_sym, bars_by_sym, time_idx_by_sym, rr)

        std_rs    = [t["std_net_r"]    for t in trades]
        stress_rs = [t["stress_net_r"] for t in trades]
        gross_rs  = [t["gross_r"]      for t in trades]

        std_m    = compute_metrics(std_rs)
        stress_m = compute_metrics(stress_rs)
        gross_m  = compute_metrics(gross_rs)

        gate = (
            std_m["trade_count"] >= PHASE0_MIN_TRADES
            and std_m["net_pf"]    > PHASE0_MIN_PF
            and stress_m["net_pf"] > PHASE0_MIN_PF
        )

        all_rr_data[rr] = {
            "trades":         trades,
            "std_metrics":    std_m,
            "stress_metrics": stress_m,
            "gross_pf":       gross_m["net_pf"],
            "gate":           gate,
        }
        verdict = "PASS" if gate else "FAIL"
        print(
            f"{len(trades)} trades | PF_std={_pf(std_m['net_pf'])} "
            f"PF_2x={_pf(stress_m['net_pf'])} → {verdict}"
        )

    # ── Determine best RR (for report focus) ─────────────────────────────────
    passing = [rr for rr in RR_VARIANTS if all_rr_data[rr]["gate"]]
    any_pass = bool(passing)
    if passing:
        best_rr = max(passing, key=lambda r: all_rr_data[r]["std_metrics"]["net_pf"])
    else:
        best_rr = max(RR_VARIANTS, key=lambda r: all_rr_data[r]["std_metrics"]["net_pf"])

    # ── Write reports ─────────────────────────────────────────────────────────
    print("\n[+] Writing reports ...")
    write_results(run_id, all_rr_data, best_rr, today_utc)
    if not any_pass:
        write_failure_analysis(run_id, all_rr_data, today_utc)

    # ── Log to research CSVs ──────────────────────────────────────────────────
    print("[+] Logging to research CSVs ...")
    for rr in RR_VARIANTS:
        d = all_rr_data[rr]
        _log_trades(run_id, rr, d["trades"], contexts_by_sym)
        _log_runs(run_id, rr, d["trades"], all_rr_data, d["gate"],
                  today_utc, data_start, data_end)

    # ── Final summary ─────────────────────────────────────────────────────────
    print("\n=== Phase-0 Gate Summary ===\n")
    for rr in RR_VARIANTS:
        d  = all_rr_data[rr]
        sm = d["std_metrics"]
        st = d["stress_metrics"]
        g  = "✅ PASS" if d["gate"] else "❌ FAIL"
        print(
            f"  RR={rr:.0f}  trades={sm['trade_count']:3d}  "
            f"PF_std={_pf(sm['net_pf'])}  PF_2x={_pf(st['net_pf'])}  {g}"
        )

    print()
    if any_pass:
        print(f"FINAL: ✅ PASS — best RR={best_rr:.0f}")
        print("       Next step: Phase-1 paper trade (MetaAPI demo, 30 days, ≥50 trades)")
    else:
        print("FINAL: ❌ FAIL")
        print("       See docs/BACKTEST_FAILURE_ANALYSIS.md for root cause.")
        print("       Any parameter change = new trial row in docs/VERDICT_LOG.md.")

    print("\nResults: docs/BACKTEST_RESULTS.md")
    print(f"Run ID:  {run_id}\n")


if __name__ == "__main__":
    main()

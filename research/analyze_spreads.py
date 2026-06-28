#!/usr/bin/env python3
"""
E6 — Step 1: Comprehensive spread analysis.

Reads  : research/spread_samples.csv
Outputs: docs/SPREAD_RESEARCH_FINAL_REPORT.md  (populates the template)
         stdout: session coverage + hourly breakdown

Run after check_phase2_completion.py exits 0.
"""

import csv
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SRC  = _ROOT / "research" / "spread_samples.csv"
_OUT  = _ROOT / "docs" / "SPREAD_RESEARCH_FINAL_REPORT.md"

KILLZONE_SESSIONS = ("london", "new_york")
STRATEGY_SYMBOLS  = ("EURUSD", "GBPUSD")
PLACEHOLDERS      = {"EURUSD": 1.40, "GBPUSD": 1.80}

# Session-hour label mapping (UTC, summer EDT)
SESSION_HOURS = {
    "london":   ["06:xx", "07:xx", "08:xx"],
    "new_york": ["11:xx", "12:xx", "13:xx"],
}


def _percentile(data, p):
    if not data:
        return None
    s = sorted(data)
    k = (len(s) - 1) * p / 100
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def _stats(values):
    if not values:
        return {}
    return {
        "n":      len(values),
        "avg":    statistics.mean(values),
        "median": statistics.median(values),
        "p90":    _percentile(values, 90),
        "p95":    _percentile(values, 95),
        "p99":    _percentile(values, 99),
        "min":    min(values),
        "max":    max(values),
    }


def _fmt(v, decimals=2):
    return f"{v:.{decimals}f}" if v is not None else "—"


def main():
    if not _SRC.exists():
        print(f"[ERROR] {_SRC} not found.")
        raise SystemExit(1)

    # Accumulators
    by_sym_sess  = defaultdict(list)          # (sym, sess) → [pips]
    by_sym_hour  = defaultdict(list)          # (sym, sess, hour) → [pips]
    sessions_seen = defaultdict(set)          # sym → {dates where london/ny appeared}
    meta = {"start": None, "end": None, "total_rows": 0, "skipped": 0,
            "gaps_over_90s": 0, "dropouts": 0}

    rows = []
    with _SRC.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            meta["total_rows"] += 1
            sym     = row.get("symbol", "").strip()
            session = row.get("session", "").strip()
            raw     = row.get("spread_pips", "")
            ts      = row.get("time_utc", "").strip()
            try:
                pips = float(raw)
                hour = int(row.get("hour", -1))
            except (ValueError, TypeError):
                meta["skipped"] += 1
                continue
            if not sym or not session or not ts:
                meta["skipped"] += 1
                continue

            rows.append((ts, sym, session, hour, pips))
            by_sym_sess[(sym, session)].append(pips)
            by_sym_hour[(sym, session, hour)].append(pips)

            date_str = ts[:10]
            if session in KILLZONE_SESSIONS:
                sessions_seen[(sym, session)].add(date_str)

            if meta["start"] is None or ts < meta["start"]:
                meta["start"] = ts
            if meta["end"] is None or ts > meta["end"]:
                meta["end"] = ts

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Count unique session days per symbol (use first strategy symbol as reference)
    london_days = len(sessions_seen.get(("EURUSD", "london"), set()))
    ny_days     = len(sessions_seen.get(("EURUSD", "new_york"), set()))

    # Estimate poll efficiency: expected = rows per 30s interval
    symbols_in_csv = sorted({k[0] for k in by_sym_sess})

    # Build the report
    lines = [
        "# SPREAD_RESEARCH_FINAL_REPORT.md",
        "# Vantage Spread Research — Final Report",
        f"# Status: POPULATED — generated {now_str}",
        f"# Source: {_SRC.relative_to(_ROOT)}",
        "",
        "---",
        "",
        "## 1 — Collection Summary",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Collection start | {meta['start'][:19].replace('T', ' ')} UTC |",
        f"| Collection end   | {meta['end'][:19].replace('T', ' ')} UTC |",
        f"| London sessions  | {london_days}/5 |",
        f"| NY sessions      | {ny_days}/5 |",
        f"| Total rows       | {meta['total_rows']:,} |",
        "| Poll interval    | ~30 s (target) |",
        "| Symbol dropouts  | see Section 2 |",
        "",
        "---",
        "",
        "## 2 — Sample Counts by Symbol and Session",
        "",
        "| Symbol | Session | n | Notes |",
        "|---|---|---|---|",
    ]
    all_syms = sorted({k[0] for k in by_sym_sess})
    for sym in all_syms:
        for sess in ["london", "new_york", "off"]:
            n = len(by_sym_sess.get((sym, sess), []))
            note = "killzone" if sess in KILLZONE_SESSIONS else "off-session"
            lines.append(f"| {sym} | {sess} | {n:,} | {note} |")

    lines += [
        "",
        "---",
        "",
        "## 3 — Average Spread by Symbol and Session",
        "",
        "| Symbol | Session | Avg (pip) | Median (pip) | P95 (pip) | Min | Max |",
        "|---|---|---|---|---|---|---|",
    ]
    for sym in all_syms:
        for sess in ["london", "new_york"]:
            st = _stats(by_sym_sess.get((sym, sess), []))
            if not st:
                lines.append(f"| {sym} | {sess} | — | — | — | — | — |")
                continue
            lines.append(
                f"| {sym} | {sess} | {_fmt(st['avg'])} | {_fmt(st['median'])} "
                f"| {_fmt(st['p95'])} | {_fmt(st['min'])} | {_fmt(st['max'])} |"
            )

    lines += [
        "",
        "---",
        "",
        "## 4 — Hourly Breakdown Within Sessions (EURUSD and GBPUSD)",
        "",
    ]
    for sym in STRATEGY_SYMBOLS:
        for sess, label_hours in SESSION_HOURS.items():
            lines.append(f"### {sym} — {sess.replace('_', ' ').title()}")
            lines += [
                "",
                "| Hour UTC | n | Avg | Median | Max |",
                "|---|---|---|---|---|",
            ]
            for h_label in label_hours:
                hour_int = int(h_label.split(":")[0])
                vals = by_sym_hour.get((sym, sess, hour_int), [])
                if not vals:
                    lines.append(f"| {h_label} | 0 | — | — | — |")
                    continue
                st = _stats(vals)
                lines.append(
                    f"| {h_label} | {st['n']} | {_fmt(st['avg'])} "
                    f"| {_fmt(st['median'])} | {_fmt(st['max'])} |"
                )
            lines.append("")

    # Combined killzone stats
    kz_by_sym = {}
    for sym in STRATEGY_SYMBOLS:
        combined = []
        for sess in KILLZONE_SESSIONS:
            combined.extend(by_sym_sess.get((sym, sess), []))
        kz_by_sym[sym] = _stats(combined)

    lines += [
        "---",
        "",
        "## 5 — Recommended Standard and Stress-2× Costs",
        "",
        "Methodology: combined killzone average (london + new_york), P95 rounded",
        "up to next 0.05 pip = standard. Standard × 2 = stress.",
        "",
        "| Symbol | KZ avg (pip) | KZ P95 (pip) | Recommended standard | Recommended stress 2× | vs Placeholder |",
        "|---|---|---|---|---|---|",
    ]
    import math
    for sym in STRATEGY_SYMBOLS:
        st = kz_by_sym.get(sym, {})
        if not st:
            lines.append(f"| {sym} | — | — | — | — | — |")
            continue
        p95 = st["p95"]
        standard = math.ceil(round(p95 / 0.05, 8)) * 0.05
        stress2x = standard * 2
        placeholder = PLACEHOLDERS.get(sym, "?")
        delta = standard - placeholder
        lines.append(
            f"| {sym} | {_fmt(st['avg'])} | {_fmt(p95)} "
            f"| {standard:.2f} pip | {stress2x:.2f} pip "
            f"| {delta:+.2f} vs {placeholder} |"
        )

    lines += [
        "",
        "---",
        "",
        "## 6 — Comparison Against Placeholder Assumptions",
        "",
        "| Symbol | Measured KZ avg | Placeholder std | Delta | Delta % |",
        "|---|---|---|---|---|",
    ]
    for sym in STRATEGY_SYMBOLS:
        st = kz_by_sym.get(sym, {})
        if not st:
            continue
        placeholder = PLACEHOLDERS.get(sym, 0)
        delta = st["avg"] - placeholder
        delta_pct = delta / placeholder * 100 if placeholder else 0
        lines.append(
            f"| {sym} | {_fmt(st['avg'])} | {placeholder:.2f} "
            f"| {delta:+.2f} | {delta_pct:+.1f}% |"
        )

    # Preliminary trend (always from interim doc if data < 5 sessions)
    lines += [
        "",
        "---",
        "",
        "## 7 — Preliminary Trend",
        "",
        "From `research/SPREAD_CAPTURE_INTERIM.md` (1 London session, 2026-06-24):",
        "",
        "| Symbol | Preliminary avg | Placeholder | Signal |",
        "|---|---|---|---|",
        "| EURUSD | 1.35 pip | 1.40 pip | Lower |",
        "| GBPUSD | 1.55 pip | 1.80 pip | Lower |",
        "",
        f"This report supersedes the preliminary reading with {meta['total_rows']:,} rows.",
        "",
        "---",
        "",
        "## 8 — Estimated Impact on ST-A2 PF_2x",
        "",
        "| Metric | Placeholder costs | Direction |",
        "|---|---|---|",
        "| PF_std  | 1.151 | See BACKTEST_RESULTS.md post-E6 run |",
        "| PF_2x   | 1.025 | See BACKTEST_RESULTS.md post-E6 run |",
        "",
        "Run `python3 scripts/backtest_session_liquidity.py --costs-json config/costs.json`",
        "after export_spread_limits.py updates the active_profile.",
        "",
        "---",
        "",
        "## 9 — Conclusion and Recommendation",
        "",
        "See `docs/BACKTEST_COST_REVALIDATION_REPORT.md` for the E6 verdict",
        "(populated after the backtest re-run with measured costs).",
        "",
        f"*Generated: {now_str}*",
    ]

    _OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"[+] Written: {_OUT.relative_to(_ROOT)}")

    # Stdout summary
    print(f"\n{'='*60}")
    print("  Spread Analysis Summary")
    print(f"{'='*60}")
    print(f"  Rows:    {meta['total_rows']:,}  |  London: {london_days}/5  |  NY: {ny_days}/5")
    print(f"\n  {'Symbol':<10} {'Session':<12} {'n':>6} {'Avg':>6} {'P95':>6}")
    print(f"  {'-'*45}")
    for sym in STRATEGY_SYMBOLS:
        for sess in ["london", "new_york"]:
            st = _stats(by_sym_sess.get((sym, sess), []))
            if not st:
                continue
            print(f"  {sym:<10} {sess:<12} {st['n']:>6} {st['avg']:>6.2f} {st['p95']:>6.2f}")
    print("\nNext: python3 scripts/build_cost_model.py")


if __name__ == "__main__":
    main()

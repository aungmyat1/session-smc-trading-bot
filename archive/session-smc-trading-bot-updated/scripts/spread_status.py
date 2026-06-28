#!/usr/bin/env python3
"""
spread_status.py — quick status check for the running spread capture.

Usage:
    python3 scripts/spread_status.py

Prints: session coverage, sample counts, current averages, and collection health.
Read-only — does not modify any files.
"""
import csv
import statistics
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
CSV = _ROOT / "research" / "spread_samples.csv"
LOG = _ROOT / "logs" / "spread_capture.log"


def main() -> None:
    now = datetime.now(timezone.utc)
    print(f"Spread Capture Status — {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print()

    # ── tmux session ─────────────────────────────────────────────────────────
    try:
        result = subprocess.run(["tmux", "ls"], capture_output=True, text=True)
        running = "spreads" in result.stdout
    except FileNotFoundError:
        running = False
    print(f"  tmux 'spreads': {'✅ RUNNING' if running else '❌ NOT FOUND'}")

    # ── CSV state ─────────────────────────────────────────────────────────────
    if not CSV.exists():
        print(f"  CSV: ❌ not found at {CSV}")
        return

    rows = list(csv.DictReader(CSV.open()))
    print(f"  CSV rows: {len(rows)}")

    if not rows:
        print("  No data yet.")
        return

    times = sorted(set(r["time_utc"] for r in rows))
    first = times[0]
    last = times[-1]
    print(f"  Span: {first} → {last}")

    # Poll interval health
    parsed = [datetime.fromisoformat(t) for t in times]
    if len(parsed) > 1:
        gaps = [(parsed[i] - parsed[i - 1]).total_seconds() for i in range(1, len(parsed))]
        avg_gap = statistics.mean(gaps)
        max_gap = max(gaps)
        bad = sum(1 for g in gaps if g > 90)
        print(f"  Poll interval: avg={avg_gap:.0f}s  max={max_gap:.0f}s  "
              f"gaps>90s: {bad} {'✅' if bad == 0 else '⚠️'}")

    print()

    # ── Session coverage ──────────────────────────────────────────────────────
    sess_days: dict[str, set] = defaultdict(set)
    for r in rows:
        if r["session"] != "off":
            sess_days[r["session"]].add(r["time_utc"][:10])

    london_n = len(sess_days["london"])
    ny_n = len(sess_days["new_york"])
    gate_met = london_n >= 5 and ny_n >= 5

    print("  Session coverage:")
    print(f"    London:   {london_n}/5  {sorted(sess_days['london'])}")
    print(f"    New York: {ny_n}/5  {sorted(sess_days['new_york'])}")
    print(f"    Gate (5+5): {'✅ MET' if gate_met else f'⏳ {5 - london_n}L + {5 - ny_n}NY remaining'}")
    print()

    # ── Spread averages by symbol/session ─────────────────────────────────────
    agg: dict[tuple, list] = defaultdict(list)
    for r in rows:
        if r["session"] != "off":
            agg[(r["symbol"], r["session"])].append(float(r["spread_pips"]))

    placeholders = {"EURUSD": (1.4, 1.8), "GBPUSD": (1.8, 3.6)}  # (std, 2x)
    symbols = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
    sessions = ["london", "new_york"]

    print("  Killzone spread averages (pip):")
    print(f"  {'Symbol':<8} {'Session':<10} {'n':>5} {'Avg':>6} {'Med':>6} "
          f"{'P95':>6} {'Max':>6}  vs placeholder")
    for sym in symbols:
        for sess in sessions:
            vals = agg.get((sym, sess), [])
            if not vals:
                continue
            avg = statistics.mean(vals)
            med = statistics.median(vals)
            p95 = sorted(vals)[int(len(vals) * 0.95)]
            mx = max(vals)
            ph_std = placeholders.get(sym, (None, None))[0]
            note = ""
            if ph_std is not None:
                delta = avg - ph_std
                note = f"ph={ph_std:.2f}  Δ={delta:+.2f} {'✅' if delta < 0 else '⚠️'}"
            print(f"  {sym:<8} {sess:<10} {len(vals):>5} {avg:>6.2f} {med:>6.2f} "
                  f"{p95:>6.2f} {mx:>6.2f}  {note}")

    print()

    # ── PF_2x projection (if we have London + NY EURUSD + GBPUSD data) ───────
    eur_vals = agg.get(("EURUSD", "london"), []) + agg.get(("EURUSD", "new_york"), [])
    gbp_vals = agg.get(("GBPUSD", "london"), []) + agg.get(("GBPUSD", "new_york"), [])
    if eur_vals and gbp_vals:
        eur_avg = statistics.mean(eur_vals)
        gbp_avg = statistics.mean(gbp_vals)
        eur_trades, gbp_trades, total = 105, 64, 169
        ph_w = (2.8 * eur_trades + 3.6 * gbp_trades) / total
        meas_w = (eur_avg * 2 * eur_trades + gbp_avg * 2 * gbp_trades) / total
        ratio = meas_w / ph_w
        drag_ph = 0.126  # PF_std - PF_2x at placeholder (from ST_A2_CONFIRMATION.md)
        pf_std = 1.151
        est_pf_2x = pf_std - drag_ph * ratio
        tag = "✅ projected PASS" if est_pf_2x >= 1.0 else "❌ projected FAIL"
        print("  PF_2x projection (linear approx, preliminary):")
        print(f"    Measured EURUSD avg: {eur_avg:.2f}pip  GBPUSD avg: {gbp_avg:.2f}pip")
        print(f"    Weighted 2× cost: measured={meas_w:.3f}  placeholder=3.103")
        print(f"    Estimated PF_2x: {est_pf_2x:.3f}  {tag}")
        print(f"    {'⚠️  PRELIMINARY — do not update costs.json until gate met (5+5 sessions)' if not gate_met else '✅ Gate met — ready for full analysis'}")
        print()

    # ── Expected completion ───────────────────────────────────────────────────
    if not gate_met:
        sessions_left = max(5 - london_n, 5 - ny_n)
        print(f"  Estimated gate completion: ~{sessions_left} more trading day(s)")
        print("  No action needed. Run: python3 scripts/spread_status.py each morning.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
E6 — Step 2: Build cost model from collected spread samples.

Reads  : research/spread_samples.csv
Outputs: research/cost_model.json

Computes avg / median / P90 / P95 / P99 per symbol and session (london,
new_york, off) plus a combined_killzone view (london + new_york together).
The combined_killzone stats are what export_spread_limits.py uses to set
the vantage_measured cost profile.

Run after check_phase2_completion.py exits 0.
"""

import csv
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "research" / "spread_samples.csv"
_OUT = _ROOT / "research" / "cost_model.json"

KILLZONE_SESSIONS = {"london", "new_york"}


def _percentile(data, p):
    """Return the p-th percentile of a list of numbers (0 ≤ p ≤ 100)."""
    if not data:
        return None
    s = sorted(data)
    k = (len(s) - 1) * p / 100
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def _stats(values):
    if not values:
        return {
            "n": 0,
            "avg": None,
            "median": None,
            "p90": None,
            "p95": None,
            "p99": None,
            "min": None,
            "max": None,
        }
    return {
        "n": len(values),
        "avg": round(statistics.mean(values), 4),
        "median": round(statistics.median(values), 4),
        "p90": round(_percentile(values, 90), 4),
        "p95": round(_percentile(values, 95), 4),
        "p99": round(_percentile(values, 99), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def main():
    if not _SRC.exists():
        print(f"[ERROR] {_SRC} not found. Run capture_spreads.py first.")
        raise SystemExit(1)

    buckets = defaultdict(list)  # (symbol, session) → [spread_pips]
    total_rows = 0
    skipped = 0

    with _SRC.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_rows += 1
            sym = row.get("symbol", "").strip()
            session = row.get("session", "").strip()
            raw = row.get("spread_pips", "")
            try:
                pips = float(raw)
            except (ValueError, TypeError):
                skipped += 1
                continue
            if not sym or not session:
                skipped += 1
                continue
            buckets[(sym, session)].append(pips)

    symbols = sorted({k[0] for k in buckets})
    sessions = sorted({k[1] for k in buckets})

    model = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": str(_SRC.relative_to(_ROOT)),
        "row_count": total_rows,
        "skipped_rows": skipped,
        "symbols": {},
    }

    for sym in symbols:
        sym_data = {}
        kz_combined = []
        for sess in sessions:
            vals = buckets.get((sym, sess), [])
            sym_data[sess] = _stats(vals)
            if sess in KILLZONE_SESSIONS:
                kz_combined.extend(vals)
        sym_data["combined_killzone"] = _stats(kz_combined)
        model["symbols"][sym] = sym_data

    _OUT.write_text(json.dumps(model, indent=2), encoding="utf-8")
    print(f"[+] Written: {_OUT.relative_to(_ROOT)}")

    hdr = f"\n{'Symbol':<10} {'Session':<18} {'n':>6} {'Avg':>6} {'Med':>6} {'P90':>6} {'P95':>6} {'Max':>6}"
    print(hdr)
    print("-" * len(hdr))
    for sym in symbols:
        for sess in list(sessions) + ["combined_killzone"]:
            s = model["symbols"][sym].get(sess, {})
            if not s or s["n"] == 0:
                continue
            label = sess.upper() if sess == "combined_killzone" else sess
            print(
                f"{sym:<10} {label:<18} {s['n']:>6} "
                f"{s['avg']:>6.2f} {s['median']:>6.2f} "
                f"{s['p90']:>6.2f} {s['p95']:>6.2f} {s['max']:>6.2f}"
            )
        print()

    print(f"Total rows: {total_rows:,}  |  Skipped: {skipped}")
    print("Next: python3 scripts/export_spread_limits.py")


if __name__ == "__main__":
    main()

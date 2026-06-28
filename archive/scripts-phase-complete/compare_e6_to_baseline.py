#!/usr/bin/env python3
"""
E6 Comparison Utility — compare post-E6 backtest results to the PRE_E6_BASELINE.

Usage:
    python3 scripts/compare_e6_to_baseline.py

Reads:  docs/BACKTEST_RESULTS.md  (updated by run_e6_revalidation.sh)
Output: docs/E6_COMPARISON_REPORT.md
        stdout summary

Exits 0 on success. Exits 1 if E6 has not yet been run (BACKTEST_RESULTS.md
still contains a baseline run ID).

Run only after bash scripts/run_e6_revalidation.sh completes.
"""

import re
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_RESULTS = _ROOT / "docs" / "BACKTEST_RESULTS.md"
_OUT     = _ROOT / "docs" / "E6_COMPARISON_REPORT.md"

# ── Locked baseline (PRE_E6_BASELINE.md | run 20260621T100458-183aaa) ─────────

BASELINE = {
    "run_id":      "20260621T100458-183aaa",
    "trades":      169,
    "win_rate":    32.0,    # %
    "gross_pf":    1.299,
    "net_pf_std":  1.151,
    "net_pf_2x":   1.025,
    "expectancy":  0.108,   # avg R per trade
    "max_dd":      18.72,   # R
}

# All run IDs that are known non-E6 runs (placeholder cost runs)
BASELINE_RUN_IDS = {
    "20260621T100458-183aaa",  # canonical ST-A2 production run
    "20260621T102303-daefa9",  # later run at same placeholder costs (identical results)
}

# ── Thresholds ────────────────────────────────────────────────────────────────

# (lower_bound_for_IMPROVED, upper_bound_for_IMPROVED)
# Metric is IMPROVED if delta > threshold, DEGRADED if delta < -threshold, else UNCHANGED
# For max_dd: direction is inverted (lower = better)
THRESHOLDS = {
    "trades":     0,      # must match exactly
    "win_rate":   0.5,    # pp
    "gross_pf":   0.005,
    "net_pf_std": 0.005,
    "net_pf_2x":  0.005,
    "expectancy": 0.005,
    "max_dd":     0.2,    # R
}


def _classify(key, baseline_val, e6_val):
    """Return (delta, direction) where direction is IMPROVED / UNCHANGED / DEGRADED."""
    delta = e6_val - baseline_val
    thr   = THRESHOLDS[key]

    if key == "max_dd":
        # lower DD is better
        if delta < -thr:
            return delta, "IMPROVED"
        if delta > thr:
            return delta, "DEGRADED"
        return delta, "UNCHANGED"

    if key == "trades":
        if delta == 0:
            return delta, "UNCHANGED"
        return delta, "⚠ CHANGED"      # should never change

    if delta > thr:
        return delta, "IMPROVED"
    if delta < -thr:
        return delta, "DEGRADED"
    return delta, "UNCHANGED"


def _parse_results(text):
    """
    Extract run_id and the RR=5 summary row from BACKTEST_RESULTS.md.

    Expected row format (columns separated by ' | '):
    | 5 | 169 | 32.0% | 0.108 | 1.299 | 1.151 | 1.025 | 18.72 | ...
    RR | Trades | Win% | Avg R | Gross PF | Net PF(std) | Net PF(2×) | Max DD | Verdict
    """
    run_id = None
    m = re.search(r"#\s*Run:\s*([\w-]+)", text)
    if m:
        run_id = m.group(1).strip()

    rr5 = None
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip().strip("*") for c in line.split("|")[1:-1]]
        if len(cells) < 8:
            continue
        try:
            if float(cells[0]) == 5.0:
                rr5 = {
                    "trades":     int(cells[1]),
                    "win_rate":   float(cells[2].rstrip("%")),
                    "expectancy": float(cells[3]),
                    "gross_pf":   float(cells[4]),
                    "net_pf_std": float(cells[5]),
                    "net_pf_2x":  float(cells[6]),
                    "max_dd":     float(cells[7]),
                }
                break
        except (ValueError, IndexError):
            continue

    return run_id, rr5


def main():
    if not _RESULTS.exists():
        print(f"[ERROR] {_RESULTS} not found. Run the backtest first.")
        raise SystemExit(1)

    text   = _RESULTS.read_text(encoding="utf-8")
    run_id, e6 = _parse_results(text)

    if run_id is None:
        print(f"[ERROR] Could not extract run ID from {_RESULTS}.")
        raise SystemExit(1)

    if run_id in BASELINE_RUN_IDS:
        print(f"[INFO]  BACKTEST_RESULTS.md still contains baseline run ({run_id}).")
        print("        E6 has not yet been executed.")
        print("        Run:  bash scripts/run_e6_revalidation.sh")
        print("        Then: python3 scripts/compare_e6_to_baseline.py")
        raise SystemExit(1)

    if e6 is None:
        print(f"[ERROR] Could not parse RR=5 row from {_RESULTS}.")
        raise SystemExit(1)

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ── Classify each metric ──────────────────────────────────────────────────

    metrics = [
        ("Trade count",   "trades",     BASELINE["trades"],     e6["trades"],     "",   "{:.0f}"),
        ("Win rate",      "win_rate",   BASELINE["win_rate"],   e6["win_rate"],   "%",  "{:.1f}"),
        ("Gross PF",      "gross_pf",   BASELINE["gross_pf"],   e6["gross_pf"],   "",   "{:.3f}"),
        ("Net PF (std)",  "net_pf_std", BASELINE["net_pf_std"], e6["net_pf_std"], "",   "{:.3f}"),
        ("Net PF (2×)",   "net_pf_2x",  BASELINE["net_pf_2x"],  e6["net_pf_2x"],  "",   "{:.3f}"),
        ("Expectancy",    "expectancy", BASELINE["expectancy"], e6["expectancy"], "R",  "{:.3f}"),
        ("Max DD",        "max_dd",     BASELINE["max_dd"],     e6["max_dd"],     "R",  "{:.2f}"),
    ]

    rows = []
    for label, key, b_val, e_val, unit, fmt in metrics:
        delta, direction = _classify(key, b_val, e_val)
        rows.append({
            "label":     label,
            "key":       key,
            "baseline":  fmt.format(b_val) + unit,
            "e6":        fmt.format(e_val) + unit,
            "delta":     f"{delta:+.3f}{unit}",
            "direction": direction,
        })

    # ── Overall verdict ───────────────────────────────────────────────────────
    pf_2x_e6  = e6["net_pf_2x"]
    if pf_2x_e6 >= 1.05:
        overall = "✅ PASS — PF_2x ≥ 1.05, comfortable margin. Proceed to E1–E4."
        verdict_code = "PASS"
    elif pf_2x_e6 >= 1.00:
        overall = "⚠️  REVIEW — PF_2x 1.00–1.05, thin margin. Proceed with GBPUSD monitoring."
        verdict_code = "REVIEW"
    else:
        overall = "❌ REJECT — PF_2x < 1.00. Strategy does not survive measured costs."
        verdict_code = "REJECT"

    # ── Print to stdout ───────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  E6 vs PRE_E6_BASELINE Comparison")
    print(f"  Baseline run:  {BASELINE['run_id']}")
    print(f"  E6 run:        {run_id}")
    print(f"{'='*60}")
    print(f"\n  {'Metric':<18} {'Baseline':>10} {'E6':>10} {'Delta':>10}  Direction")
    print(f"  {'-'*62}")
    for r in rows:
        print(f"  {r['label']:<18} {r['baseline']:>10} {r['e6']:>10} {r['delta']:>10}  {r['direction']}")
    print(f"\n  Overall: {overall}")

    # ── Write E6_COMPARISON_REPORT.md ─────────────────────────────────────────
    lines = [
        "# E6_COMPARISON_REPORT.md",
        "# ST-A2 — E6 vs PRE_E6_BASELINE Comparison",
        f"# Generated: {now_str}",
        f"# Baseline run: {BASELINE['run_id']}",
        f"# E6 run:       {run_id}",
        "",
        "---",
        "",
        "## Run Identity",
        "",
        "| Field | Baseline | E6 |",
        "|---|---|---|",
        f"| Run ID | `{BASELINE['run_id']}` | `{run_id}` |",
        "| Cost profile | PLACEHOLDER_vt_markets_assumption | vantage_measured |",
        "| EURUSD cost (std) | 1.4 pip | from measured data |",
        "| GBPUSD cost (std) | 1.8 pip | from measured data |",
        f"| Generated | 2026-06-21 | {now_str[:10]} |",
        "",
        "---",
        "",
        "## Metric Comparison (RR 5, Combined EURUSD + GBPUSD)",
        "",
        "| Metric | Baseline | E6 | Delta | Direction |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['label']} | {r['baseline']} | {r['e6']} | {r['delta']} | **{r['direction']}** |"
        )

    lines += [
        "",
        "---",
        "",
        "## Overall E6 Verdict",
        "",
        f"**{overall}**",
        "",
        "See full decision rationale: `docs/E6_DECISION_MATRIX.md`",
        "",
        "---",
        "",
        "## Integrity Check",
        "",
        "Trade count and win rate must be unchanged — costs affect P&L, not signal generation.",
        "",
        "| Check | Expected | Actual | Status |",
        "|---|---|---|---|",
    ]
    tc_row = next(r for r in rows if r["key"] == "trades")
    wr_row = next(r for r in rows if r["key"] == "win_rate")
    tc_ok  = "✅ OK" if tc_row["direction"] == "UNCHANGED" else "❌ FAIL — investigate"
    wr_ok  = "✅ OK" if wr_row["direction"] in ("UNCHANGED", "IMPROVED") else "⚠️  CHECK"
    lines += [
        f"| Trade count unchanged | 169 | {e6['trades']} | {tc_ok} |",
        f"| Win rate stable       | 32.0% | {e6['win_rate']:.1f}% | {wr_ok} |",
        "",
        "---",
        "",
        "## Post-Comparison Actions",
        "",
    ]
    if verdict_code == "PASS":
        lines += [
            "1. ✅ Populate `docs/BACKTEST_COST_REVALIDATION_REPORT.md` with E6 results",
            "2. ✅ Add E6 sub-entry to `docs/VERDICT_LOG.md` under ST-A2",
            "3. ✅ Proceed to E1: enable `LIVE_TRADING=true` and start 7-day execution gate",
        ]
    elif verdict_code == "REVIEW":
        lines += [
            "1. ⚠️  Populate `docs/BACKTEST_COST_REVALIDATION_REPORT.md`",
            "2. ⚠️  Add E6 sub-entry to `docs/VERDICT_LOG.md` under ST-A2 with REVIEW flag",
            "3. ⚠️  Proceed to E1 but monitor GBPUSD spread tightly during demo run",
            "4. ⚠️  Consider running with London-only restriction if GBPUSD spread widens",
        ]
    else:
        lines += [
            "1. ❌ Do NOT proceed to demo or live",
            "2. ❌ Write `docs/ST_A3_RECOVERY_OPTIONS.md`",
            "3. ❌ Register ST-A3 in VERDICT_LOG.md with revised spec",
        ]

    lines += [
        "",
        "---",
        "",
        f"*E6_COMPARISON_REPORT.md | Generated {now_str}*",
    ]

    _OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[+] Written: {_OUT.relative_to(_ROOT)}")

    return 0 if verdict_code in ("PASS", "REVIEW") else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Phase-1 Research Experiments - post-hoc filter testing on ST-A trade log.

This is a light-weight port of the archived experiment runner kept in
`archive/scripts-phase-complete/run_experiments.py`.  The tests import the
pure helpers here, and the CLI can still be used to regenerate the report.
"""

from __future__ import annotations

import csv
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

BASE_RUN_ID = "20260621T060745-f6ac57"
RR_VARIANTS = [2.0, 3.0, 4.0, 5.0]
PHASE0_N = 100
PHASE0_PF = 1.0

BASELINE = {"n": 181, "pf_std": 1.126, "pf_2x": 0.965, "rr": 5.0}

EXPERIMENTS = [
    {
        "id": "EXP-01",
        "name": "Minimum SL Floor",
        "hypothesis": "Narrow-SL setups have spread_cost_R >= 1.08R - removing them improves net PF.",
        "variants": [
            {"label": "≥ 5 pip", "fn": lambda t: t["sl_pips"] >= 5.0},
            {"label": "≥ 7 pip", "fn": lambda t: t["sl_pips"] >= 7.0},
            {"label": "≥ 10 pip", "fn": lambda t: t["sl_pips"] >= 10.0},
        ],
    },
    {
        "id": "EXP-02",
        "name": "Minimum Asian Range",
        "hypothesis": "Wider ranges produce larger sweeps and reduce spread_cost_R on SL.",
        "variants": [
            {"label": "≥ 10 pip", "fn": lambda t: t["asian_range_pips"] >= 10.0},
            {"label": "≥ 15 pip", "fn": lambda t: t["asian_range_pips"] >= 15.0},
            {"label": "≥ 20 pip", "fn": lambda t: t["asian_range_pips"] >= 20.0},
        ],
    },
    {
        "id": "EXP-03",
        "name": "NY Session Only",
        "hypothesis": "NY win rate and PF 2x dominate vs London.",
        "variants": [
            {"label": "NY only", "fn": lambda t: t["session"] == "new_york"},
        ],
    },
    {
        "id": "EXP-04",
        "name": "Exclude GBPUSD London",
        "hypothesis": "GBPUSD London is the single largest drag on combined PF.",
        "variants": [
            {
                "label": "Ex GBP/LON",
                "fn": lambda t: not (t["sym"] == "GBPUSD" and t["session"] == "london"),
            },
        ],
    },
]


def load_trades(trades_csv, run_id):
    rows = []
    with open(trades_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["run_id"] != run_id:
                continue
            m = re.search(r"2x_net_r=([-\d.]+)", row.get("notes", ""))
            net_r_2x = float(m.group(1)) if m else float(row["net_r"])
            rows.append(
                {
                    "sym": row["symbol"],
                    "session": row["session"],
                    "rr": float(row["rr"]),
                    "sl_pips": float(row["sl_pips"]),
                    "asian_range_pips": float(row["asian_range_pips"]),
                    "gross_r": float(row["gross_r"]),
                    "net_r_std": float(row["net_r"]),
                    "net_r_2x": net_r_2x,
                    "bars_held": int(row["bars_held"]),
                    "exit_reason": row["exit_reason"],
                    "year": row["timestamp_utc"][:4],
                }
            )
    return rows


def apply_filter(trades, filter_fn):
    return [t for t in trades if filter_fn(t)]


def compute_metrics(trades):
    if not trades:
        return {
            "n": 0,
            "win_rate": 0.0,
            "gross_pf": 0.0,
            "net_pf_std": 0.0,
            "net_pf_2x": 0.0,
            "max_dd": 0.0,
            "avg_dur_min": 0.0,
        }

    def _pf(rs):
        wins_r = [r for r in rs if r > 0]
        loss_r = [r for r in rs if r <= 0]
        gw = sum(wins_r)
        gl = abs(sum(loss_r))
        if gl == 0:
            return float("inf") if gw > 0 else 1.0
        if gw == 0:
            return 0.0
        return gw / gl

    def _max_dd(rs):
        peak = running = dd = 0.0
        for r in rs:
            running += r
            if running > peak:
                peak = running
            if peak - running > dd:
                dd = peak - running
        return dd

    n = len(trades)
    gross_rs = [t["gross_r"] for t in trades]
    std_rs = [t["net_r_std"] for t in trades]
    stress_rs = [t["net_r_2x"] for t in trades]

    return {
        "n": n,
        "win_rate": sum(1 for r in std_rs if r > 0) / n,
        "gross_pf": _pf(gross_rs),
        "net_pf_std": _pf(std_rs),
        "net_pf_2x": _pf(stress_rs),
        "max_dd": _max_dd(std_rs),
        "avg_dur_min": sum(t["bars_held"] for t in trades) * 15 / n,
    }


def gate_check(m):
    return (
        m["n"] >= PHASE0_N
        and m["net_pf_std"] > PHASE0_PF
        and m["net_pf_2x"] > PHASE0_PF
    )


def run_all_experiments(trades):
    results = []
    for exp in EXPERIMENTS:
        for variant in exp["variants"]:
            for rr in RR_VARIANTS:
                rr_trades = [t for t in trades if t["rr"] == rr]
                filtered = apply_filter(rr_trades, variant["fn"])
                m = compute_metrics(filtered)
                results.append(
                    {
                        "exp_id": exp["id"],
                        "exp_name": exp["name"],
                        "variant": variant["label"],
                        "rr": rr,
                        **m,
                        "gate": gate_check(m),
                    }
                )
    return results


def _pct(v):
    return f"{v * 100:.1f}%"


def _pf(v):
    if v == float("inf"):
        return "∞"
    return f"{v:.3f}"


def _delta(v, baseline):
    d = v - baseline
    sign = "+" if d >= 0 else ""
    return f"{sign}{d:.3f}"


def _best_rr(rows):
    return max(rows, key=lambda r: (r["net_pf_2x"], r["n"]))


def write_report(results, today_utc):
    groups = {}
    for r in results:
        key = (r["exp_id"], r["variant"])
        groups.setdefault(key, []).append(r)

    best_per_variant = {k: _best_rr(v) for k, v in groups.items()}
    summary_rows = sorted(
        best_per_variant.values(),
        key=lambda r: (-r["net_pf_2x"], -r["n"]),
    )

    lines = [
        "# EXPERIMENT_RESULTS.md",
        "# Strategy A - Phase-1 Research Experiments",
        f"# Base run: {BASE_RUN_ID}  |  Date: {today_utc}",
        "# Filters applied post-hoc. No production strategy modified.",
        "",
        "---",
        "",
        "## Baseline (ST-A, RR=5, combined)",
        "",
        "| Trades | Net PF (std) | Net PF (2x) | Gap to gate |",
        "|---|---|---|---|",
        f"| {BASELINE['n']} | {BASELINE['pf_std']:.3f} | {BASELINE['pf_2x']:.3f} |"
        f" +{1.0 - BASELINE['pf_2x']:.3f} needed |",
        "",
        "---",
        "",
        "## Executive Summary",
        "(Best RR per variant, ranked by Net PF 2x)",
        "",
        "| # | Exp | Variant | RR | Trades | Win% | Gross PF | Net PF (std) | Net PF (2x) | Delta vs baseline | Max DD | Gate |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]

    passing = []
    for i, r in enumerate(summary_rows, 1):
        d2x = _delta(r["net_pf_2x"], BASELINE["pf_2x"])
        gate = "PASS" if r["gate"] else "FAIL"
        if r["gate"]:
            passing.append(r)
        lines.append(
            f"| {i} | {r['exp_id']} | {r['variant']} | RR{r['rr']:.0f} "
            f"| {r['n']} | {_pct(r['win_rate'])} | {_pf(r['gross_pf'])} "
            f"| {_pf(r['net_pf_std'])} | {_pf(r['net_pf_2x'])} | {d2x} "
            f"| {r['max_dd']:.2f}R | {gate} |"
        )

    if passing:
        lines += [
            "",
            f"**{len(passing)} variant(s) pass Phase-0 gate.** See detailed sections below.",
        ]
    else:
        lines += [
            "",
            "**No variant passes Phase-0 gate in isolation.** See detailed sections for closest misses.",
        ]

    lines += ["", "---", ""]

    for exp in EXPERIMENTS:
        lines += [f"## {exp['id']} - {exp['name']}", ""]
        lines += [f"*Hypothesis:* {exp['hypothesis']}", ""]
        exp_variants = list(
            dict.fromkeys(r["variant"] for r in results if r["exp_id"] == exp["id"])
        )

        for variant_label in exp_variants:
            variant_rows = [
                r
                for r in results
                if r["exp_id"] == exp["id"] and r["variant"] == variant_label
            ]
            variant_rows.sort(key=lambda r: r["rr"])

            lines += [
                f"### {variant_label}",
                "",
                "| RR | Trades | Win% | Gross PF | Net PF (std) | Net PF (2x) | Delta 2x vs baseline | Max DD | Avg Dur | Gate |",
                "|---|---|---|---|---|---|---|---|---|---|",
            ]
            for r in variant_rows:
                d2x = _delta(r["net_pf_2x"], BASELINE["pf_2x"])
                gate = "PASS" if r["gate"] else "FAIL"
                lines.append(
                    f"| RR{r['rr']:.0f} | {r['n']} | {_pct(r['win_rate'])} "
                    f"| {_pf(r['gross_pf'])} | {_pf(r['net_pf_std'])} "
                    f"| {_pf(r['net_pf_2x'])} | {d2x} "
                    f"| {r['max_dd']:.2f}R | {r['avg_dur_min']:.0f}min | {gate} |"
                )
            lines.append("")

        baseline_n = BASELINE["n"]
        best_v = _best_rr([r for r in results if r["exp_id"] == exp["id"]])
        removed = baseline_n - best_v["n"]
        lines += [
            f"**Trades retained at best variant ({best_v['variant']}, RR{best_v['rr']:.0f}):** "
            f"{best_v['n']} / {baseline_n} ({removed} removed)",
            "",
        ]

    lines += ["---", "", "## Key Findings", ""]

    for i, r in enumerate(summary_rows[:3], 1):
        d2x = r["net_pf_2x"] - BASELINE["pf_2x"]
        sign = "+" if d2x >= 0 else ""
        lines.append(
            f"{i}. **{r['exp_id']} {r['variant']} @ RR{r['rr']:.0f}** - "
            f"PF 2x={_pf(r['net_pf_2x'])} ({sign}{d2x:.3f} vs {BASELINE['pf_2x']:.3f} baseline), "
            f"n={r['n']}"
        )

    lines += ["", "## Minimum Change That Reaches Gate", ""]

    if passing:
        min_change = max(passing, key=lambda r: (r["n"], r["net_pf_2x"]))
        removed = BASELINE["n"] - min_change["n"]
        lines += [
            f"**{min_change['exp_id']} - {min_change['exp_name']} / {min_change['variant']} @ RR{min_change['rr']:.0f}**",
            "",
            f"- Trades retained: {min_change['n']} / {BASELINE['n']} ({removed} removed = least invasive passing filter)",
            f"- Net PF (std): {_pf(min_change['net_pf_std'])}",
            f"- Net PF (2x): {_pf(min_change['net_pf_2x'])} PASS",
            f"- Max DD: {min_change['max_dd']:.2f}R",
            "",
            "Removes the fewest trades while crossing the gate.",
            "Register as new trial (ST-A2) in VERDICT_LOG.md before implementing.",
        ]
    else:
        closest = max(summary_rows, key=lambda r: r["net_pf_2x"])
        gap = 1.0 - closest["net_pf_2x"]
        lines += [
            "No single filter crosses the gate in isolation.",
            "",
            f"Closest miss: **{closest['exp_id']} {closest['variant']} @ RR{closest['rr']:.0f}** - "
            f"PF 2x={_pf(closest['net_pf_2x'])}, gap={gap:.3f}",
            "",
            "Consider: combining the two highest-impact experiments as a new trial (ST-A2).",
            "Register the combined spec in VERDICT_LOG.md before running.",
        ]

    lines += ["", "---", "", f"*Base run: {BASE_RUN_ID} | Generated: {today_utc}*"]

    out = _ROOT / "docs" / "EXPERIMENT_RESULTS.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"[+] Written: {out.relative_to(_ROOT)}")
    return out


def main():
    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    trades_csv = _ROOT / "research" / "trades.csv"
    if not trades_csv.exists():
        print(
            f"ERROR: {trades_csv} not found - run backtest_session_liquidity.py first"
        )
        sys.exit(1)

    print(f"[+] Loading trades (run={BASE_RUN_ID}) ...")
    trades = load_trades(trades_csv, BASE_RUN_ID)
    print(f"    {len(trades)} rows loaded")

    if not trades:
        print("ERROR: No trades found for this run_id")
        sys.exit(1)

    print("[+] Running experiments ...")
    results = run_all_experiments(trades)
    print(f"    {len(results)} result rows computed")

    groups = {}
    for r in results:
        groups.setdefault((r["exp_id"], r["variant"]), []).append(r)

    print(
        f"\n{'Exp':<8} {'Variant':<16} {'RR':<4} {'n':>5} {'PF std':>8} {'PF 2x':>8} {'Gate'}"
    )
    print("-" * 70)
    for (eid, vl), rows in sorted(groups.items()):
        best = _best_rr(rows)
        gate = "PASS" if best["gate"] else "fail"
        print(
            f"{eid:<8} {vl:<16} RR{best['rr']:.0f}  {best['n']:>5}  {best['net_pf_std']:>7.3f}  {best['net_pf_2x']:>7.3f}  {gate}"
        )

    print()
    write_report(results, today_utc)


if __name__ == "__main__":
    main()

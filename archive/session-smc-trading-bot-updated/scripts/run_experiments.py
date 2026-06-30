#!/usr/bin/env python3
"""
Phase-1 Research Experiments — post-hoc filter testing on ST-A trade log.

Reads research/trades.csv (run 20260621T060745-f6ac57).
Applies experimental filters WITHOUT touching production strategy code.
Each experiment is isolated — no filter stacking.

Experiments:
  EXP-01  Minimum SL Floor       (5 / 7 / 10 pip)
  EXP-02  Minimum Asian Range    (10 / 15 / 20 pip unified)
  EXP-03  NY Session Only        (EURUSD + GBPUSD)
  EXP-04  Exclude GBPUSD London  (all RR variants)

Output: docs/EXPERIMENT_RESULTS.md
"""

import csv
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

# ── Constants ─────────────────────────────────────────────────────────────────

BASE_RUN_ID = "20260621T060745-f6ac57"
RR_VARIANTS = [2.0, 3.0, 4.0, 5.0]
PHASE0_N = 100
PHASE0_PF = 1.0

# ST-A baseline (RR=5, combined)
BASELINE = {"n": 181, "pf_std": 1.126, "pf_2x": 0.965, "rr": 5.0}

EXPERIMENTS = [
    {
        "id": "EXP-01",
        "name": "Minimum SL Floor",
        "hypothesis": "Narrow-SL setups have spread_cost_R ≥ 1.08R — removing them improves net PF.",
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
        "hypothesis": "NY win rate (39.6%) and PF 2×=1.344 dominate vs London 28.1% / 0.819.",
        "variants": [
            {"label": "NY only", "fn": lambda t: t["session"] == "new_york"},
        ],
    },
    {
        "id": "EXP-04",
        "name": "Exclude GBPUSD London",
        "hypothesis": "GBPUSD London (PF 2×=0.701) is the single largest drag on combined PF.",
        "variants": [
            {
                "label": "Ex GBP/LON",
                "fn": lambda t: not (t["sym"] == "GBPUSD" and t["session"] == "london"),
            },
        ],
    },
]


# ── Pure functions (importable for tests) ─────────────────────────────────────


def load_trades(trades_csv, run_id):
    """
    Load trade rows for a specific run_id from trades.csv.

    Returns list of dicts with keys:
        sym, session, rr, sl_pips, asian_range_pips,
        gross_r, net_r_std, net_r_2x, bars_held, exit_reason, year.
    """
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
    """Return subset of trades where filter_fn(trade) is True."""
    return [t for t in trades if filter_fn(t)]


def compute_metrics(trades):
    """
    Compute all experiment metrics from a list of trade dicts.

    Returns dict:
        n, win_rate, gross_pf, net_pf_std, net_pf_2x, max_dd, avg_dur_min.
    """
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
    """Return True if metrics pass Phase-0 gate (n≥100 AND pf_std>1 AND pf_2x>1)."""
    return (
        m["n"] >= PHASE0_N
        and m["net_pf_std"] > PHASE0_PF
        and m["net_pf_2x"] > PHASE0_PF
    )


def run_all_experiments(trades):
    """
    Run all experiments across all RR variants.

    Returns list of result dicts:
        exp_id, exp_name, variant, rr, n, win_rate,
        gross_pf, net_pf_std, net_pf_2x, max_dd, avg_dur_min, gate.
    """
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


# ── Report helpers ─────────────────────────────────────────────────────────────


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
    """Return row with highest net_pf_2x (ties broken by n)."""
    return max(rows, key=lambda r: (r["net_pf_2x"], r["n"]))


# ── Report writer ─────────────────────────────────────────────────────────────


def write_report(results, today_utc):
    """Write docs/EXPERIMENT_RESULTS.md."""

    # Group by (exp_id, variant)
    groups = {}
    for r in results:
        key = (r["exp_id"], r["variant"])
        groups.setdefault(key, []).append(r)

    # Best RR per variant group
    best_per_variant = {k: _best_rr(v) for k, v in groups.items()}

    # Summary rows sorted by 2× PF desc, then n desc
    summary_rows = sorted(
        best_per_variant.values(),
        key=lambda r: (-r["net_pf_2x"], -r["n"]),
    )

    lines = [
        "# EXPERIMENT_RESULTS.md",
        "# Strategy A — Phase-1 Research Experiments",
        f"# Base run: {BASE_RUN_ID}  |  Date: {today_utc}",
        "# Filters applied post-hoc. No production strategy modified.",
        "",
        "---",
        "",
        "## Baseline (ST-A, RR=5, combined)",
        "",
        f"| Trades | Net PF (std) | Net PF (2×) | Gap to gate |",
        f"|---|---|---|---|",
        f"| {BASELINE['n']} | {BASELINE['pf_std']:.3f} | {BASELINE['pf_2x']:.3f} |"
        f" +{1.0 - BASELINE['pf_2x']:.3f} needed |",
        "",
        "---",
        "",
        "## Executive Summary",
        "(Best RR per variant, ranked by Net PF 2×)",
        "",
        "| # | Exp | Variant | RR | Trades | Win% | Gross PF | Net PF (std) | Net PF (2×) | Δ vs baseline | Max DD | Gate |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]

    passing = []
    for i, r in enumerate(summary_rows, 1):
        d2x = _delta(r["net_pf_2x"], BASELINE["pf_2x"])
        gate = "✅ PASS" if r["gate"] else "❌ FAIL"
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
            f"**{len(passing)} variant(s) pass Phase-0 gate.** "
            f"See detailed sections below.",
        ]
    else:
        lines += [
            "",
            "**No variant passes Phase-0 gate in isolation.** "
            "See detailed sections for closest misses.",
        ]

    # ── Per-experiment detail ─────────────────────────────────────────────────
    lines += ["", "---", ""]

    for exp in EXPERIMENTS:
        lines += [f"## {exp['id']} — {exp['name']}", ""]
        lines += [f"*Hypothesis:* {exp['hypothesis']}", ""]

        # Collect variants for this experiment
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
                "| RR | Trades | Win% | Gross PF | Net PF (std) | Net PF (2×) | Δ 2× vs baseline | Max DD | Avg Dur | Gate |",
                "|---|---|---|---|---|---|---|---|---|---|",
            ]
            for r in variant_rows:
                d2x = _delta(r["net_pf_2x"], BASELINE["pf_2x"])
                gate = "✅" if r["gate"] else "❌"
                lines.append(
                    f"| RR{r['rr']:.0f} | {r['n']} | {_pct(r['win_rate'])} "
                    f"| {_pf(r['gross_pf'])} | {_pf(r['net_pf_std'])} "
                    f"| {_pf(r['net_pf_2x'])} | {d2x} "
                    f"| {r['max_dd']:.2f}R | {r['avg_dur_min']:.0f}min | {gate} |"
                )
            lines.append("")

        # Trades removed / retained note
        baseline_n = BASELINE["n"]
        best_v = _best_rr([r for r in results if r["exp_id"] == exp["id"]])
        removed = baseline_n - best_v["n"]
        lines += [
            f"**Trades retained at best variant ({best_v['variant']}, RR{best_v['rr']:.0f}):** "
            f"{best_v['n']} / {baseline_n} ({removed} removed)",
            "",
        ]

    # ── Key findings ──────────────────────────────────────────────────────────
    lines += [
        "---",
        "",
        "## Key Findings",
        "",
    ]

    # Sort by 2× PF for findings
    top3 = summary_rows[:3]
    for i, r in enumerate(top3, 1):
        d2x = r["net_pf_2x"] - BASELINE["pf_2x"]
        sign = "+" if d2x >= 0 else ""
        lines.append(
            f"{i}. **{r['exp_id']} {r['variant']} @ RR{r['rr']:.0f}** — "
            f"PF 2×={_pf(r['net_pf_2x'])} ({sign}{d2x:.3f} vs {BASELINE['pf_2x']:.3f} baseline), "
            f"n={r['n']}"
        )

    lines += [
        "",
        "## Minimum Change That Reaches Gate",
        "",
    ]

    # Find passing variants
    if passing:
        # "Smallest change" = passing variant with most trades retained (fewest removed)
        min_change = max(passing, key=lambda r: (r["n"], r["net_pf_2x"]))
        removed = BASELINE["n"] - min_change["n"]
        lines += [
            f"**{min_change['exp_id']} — {min_change['exp_name']} / "
            f"{min_change['variant']} @ RR{min_change['rr']:.0f}**",
            "",
            f"- Trades retained: {min_change['n']} / {BASELINE['n']} "
            f"({removed} removed = least invasive passing filter)",
            f"- Net PF (std): {_pf(min_change['net_pf_std'])}",
            f"- Net PF (2×): {_pf(min_change['net_pf_2x'])} ✅",
            f"- Max DD: {min_change['max_dd']:.2f}R",
            "",
            "Removes the fewest trades while crossing the gate.",
            "Register as new trial (ST-A2) in VERDICT_LOG.md before implementing.",
        ]
    else:
        # Find closest miss
        closest = max(summary_rows, key=lambda r: r["net_pf_2x"])
        gap = 1.0 - closest["net_pf_2x"]
        lines += [
            "No single filter crosses the gate in isolation.",
            "",
            f"Closest miss: **{closest['exp_id']} {closest['variant']} @ RR{closest['rr']:.0f}** — "
            f"PF 2×={_pf(closest['net_pf_2x'])}, gap={gap:.3f}",
            "",
            "Consider: combining the two highest-impact experiments as a new trial (ST-A2).",
            "Register the combined spec in VERDICT_LOG.md before running.",
        ]

    lines += [
        "",
        "---",
        "",
        f"*Base run: {BASE_RUN_ID} | Generated: {today_utc}*",
    ]

    out = _ROOT / "docs" / "EXPERIMENT_RESULTS.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"[+] Written: {out.relative_to(_ROOT)}")
    return out


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    from datetime import datetime, timezone

    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    trades_csv = _ROOT / "research" / "trades.csv"
    if not trades_csv.exists():
        print(
            f"ERROR: {trades_csv} not found — run backtest_session_liquidity.py first"
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

    # Print console summary
    groups = {}
    for r in results:
        groups.setdefault((r["exp_id"], r["variant"]), []).append(r)

    print(
        f"\n{'Exp':<8} {'Variant':<16} {'RR':<4} {'n':>5} {'PF std':>8} {'PF 2×':>8} {'Gate'}"
    )
    print("-" * 70)
    for (eid, vl), rows in sorted(groups.items()):
        best = _best_rr(rows)
        gate = "PASS" if best["gate"] else "fail"
        print(
            f"{eid:<8} {vl:<16} RR{best['rr']:.0f}  {best['n']:>5}"
            f"  {best['net_pf_std']:>7.3f}  {best['net_pf_2x']:>7.3f}  {gate}"
        )

    print()
    write_report(results, today_utc)


if __name__ == "__main__":
    main()

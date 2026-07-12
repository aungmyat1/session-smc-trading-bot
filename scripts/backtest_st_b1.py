#!/usr/bin/env python3
"""
ST-B1 Phase-0 backtest CLI.

Loads H1 + M15 CSV data for EURUSD/GBPUSD from data/historical/ (same
directory convention as scripts/backtest_session_liquidity.py), runs
strategies.st_b1_backtest.run_backtest() per symbol, applies round-trip
spread cost from config/costs.json (standard and 2x stress), and writes:

    reports/st_b1_trade_ledger.parquet
    reports/st_b1_metrics.json
    reports/st_b1_validation_report.md

If the required CSV files are not present, exits with a clear error rather
than fabricating output — this script does not generate synthetic data for
a "real" run.

Not yet wired into research/research_queue.py or the experiment framework
(docs/audit/ST_B1_VALIDATION_REPORT.md notes this explicitly as unstarted,
not silently skipped) — this is a standalone CLI, matching
scripts/backtest_session_liquidity.py's own integration level today.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from strategies.st_b1_backtest import compute_metrics, run_backtest  # noqa: E402

SYMBOLS = ["EURUSD", "GBPUSD"]
CSV_FILES = {
    "EURUSD": {"h1": "EURUSD_H1.csv", "m15": "EURUSD_M15.csv"},
    "GBPUSD": {"h1": "GBPUSD_H1.csv", "m15": "GBPUSD_M15.csv"},
}
DEFAULT_COST_PIPS = {"EURUSD": {"standard": 1.4, "stress2x": 2.8}, "GBPUSD": {"standard": 1.8, "stress2x": 3.6}}


def load_csv(path: Path) -> list[dict]:
    with path.open() as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            rows.append({
                "timestamp": row.get("time") or row.get("timestamp"),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "session": row.get("session", ""),
            })
    return rows


def load_costs(costs_json: Path | None) -> dict:
    if costs_json is None or not costs_json.exists():
        return DEFAULT_COST_PIPS
    payload = json.loads(costs_json.read_text())
    profile = payload.get("profiles", {}).get(payload.get("active_profile", ""), {})
    if not profile:
        return DEFAULT_COST_PIPS
    return {sym: profile[sym] for sym in SYMBOLS if sym in profile}


def apply_spread_cost(outcomes, spread_pips: float, min_sl_pips: float = 5.0):
    """Subtracts round-trip spread cost (expressed as a fraction of 1R) from
    each outcome's net_r, matching scripts/backtest_session_liquidity.py's
    spread_cost_r() convention. Uses a fixed min_sl_pips floor to avoid
    dividing by a near-zero stop distance."""
    adjusted = []
    for o in outcomes:
        sl_pips = max(abs(o.entry - o.stop_loss) / 0.0001, min_sl_pips)
        cost_r = spread_pips / sl_pips
        adjusted.append(type(o)(**{**o.__dict__, "net_r": o.net_r - cost_r}))
    return adjusted


def main() -> None:
    parser = argparse.ArgumentParser(description="ST-B1 Phase-0 backtest")
    parser.add_argument("--costs-json", type=Path, default=_ROOT / "config" / "costs.json")
    parser.add_argument("--data-dir", type=Path, default=_ROOT / "data" / "historical")
    parser.add_argument("--reports-dir", type=Path, default=_ROOT / "reports")
    args = parser.parse_args()

    costs = load_costs(args.costs_json)
    all_outcomes_std = {}
    all_outcomes_2x = {}
    missing = []

    for sym in SYMBOLS:
        h1_path = args.data_dir / CSV_FILES[sym]["h1"]
        m15_path = args.data_dir / CSV_FILES[sym]["m15"]
        if not h1_path.exists() or not m15_path.exists():
            missing.append((sym, h1_path, m15_path))
            continue
        h1 = load_csv(h1_path)
        m15 = load_csv(m15_path)
        outcomes = run_backtest(h1, m15, symbol=sym)
        cost = costs.get(sym, DEFAULT_COST_PIPS[sym])
        all_outcomes_std[sym] = apply_spread_cost(outcomes, cost["standard"])
        all_outcomes_2x[sym] = apply_spread_cost(outcomes, cost["stress2x"])

    args.reports_dir.mkdir(exist_ok=True)

    if missing:
        report = ["# ST-B1 Backtest — BLOCKED\n", "\nMissing required data files:\n"]
        for sym, h1_path, m15_path in missing:
            report.append(f"- {sym}: {h1_path} exists={h1_path.exists()}, {m15_path} exists={m15_path.exists()}\n")
        report.append(
            "\nThis run did not execute. No metrics or trade ledger were produced. "
            "See docs/audit/ST_B1_VALIDATION_REPORT.md for the data-access blocker this "
            "traces back to.\n"
        )
        (args.reports_dir / "st_b1_validation_report.md").write_text("".join(report))
        print("BLOCKED: missing data files, see reports/st_b1_validation_report.md")
        sys.exit(2)

    combined_std = [o for outs in all_outcomes_std.values() for o in outs]
    combined_2x = [o for outs in all_outcomes_2x.values() for o in outs]
    metrics_std = compute_metrics(combined_std)
    metrics_2x = compute_metrics(combined_2x)

    metrics_out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "standard_cost": metrics_std,
        "stress_2x_cost": metrics_2x,
        "gate": {
            "minimum_trades": 200,
            "minimum_profit_factor": 1.25,
            "minimum_sharpe": 1.20,
            "maximum_drawdown_pct": 15.0,
        },
    }
    (args.reports_dir / "st_b1_metrics.json").write_text(json.dumps(metrics_out, indent=2, default=str))

    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
        rows = [o.__dict__ for o in combined_std]
        if rows:
            table = pa.Table.from_pylist(rows)
            pq.write_table(table, args.reports_dir / "st_b1_trade_ledger.parquet")
    except ImportError:
        print("pyarrow not available — skipping trade_ledger.parquet (metrics.json still written)")

    passed = (
        metrics_std["trade_count"] >= 200
        and metrics_std["profit_factor"] > 1.25
        and metrics_2x["profit_factor"] > 1.25
        and metrics_std["sharpe_ratio"] > 1.20
        and metrics_std["max_drawdown_r"] < 15.0
    )
    verdict = "PASS" if passed else "FAIL"
    report = f"""# ST-B1 Validation Report

Generated: {metrics_out['generated_at']}

## Verdict: {verdict}

| Metric | Standard cost | 2x stress | Gate |
|---|---|---|---|
| Trades | {metrics_std['trade_count']} | {metrics_2x['trade_count']} | >= 200 |
| Profit Factor | {metrics_std['profit_factor']:.3f} | {metrics_2x['profit_factor']:.3f} | > 1.25 |
| Sharpe | {metrics_std['sharpe_ratio']:.3f} | - | > 1.20 |
| Win rate | {metrics_std['win_rate']:.1%} | - | - |
| Expectancy (R) | {metrics_std['expectancy_r']:.3f} | - | - |
| Max Drawdown (R) | {metrics_std['max_drawdown_r']:.2f} | - | < 15.0 |
"""
    (args.reports_dir / "st_b1_validation_report.md").write_text(report)
    print(f"Verdict: {verdict}")


if __name__ == "__main__":
    main()

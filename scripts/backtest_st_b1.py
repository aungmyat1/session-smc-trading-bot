#!/usr/bin/env python3
"""Run ST-B1 historical and walk-forward validation on local market data."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from strategies.st_b1_backtest import (  # noqa: E402
    apply_costs,
    compute_metrics,
    gate_passed,
    normalize_bars,
    run_backtest,
)

SYMBOLS = ("EURUSD", "GBPUSD")
DEFAULT_COST_PIPS = {
    "EURUSD": {"standard": 1.4, "stress2x": 2.8},
    "GBPUSD": {"standard": 1.8, "stress2x": 3.6},
}


def load_costs(path: Path) -> dict[str, dict[str, float]]:
    if not path.exists():
        return DEFAULT_COST_PIPS
    payload = json.loads(path.read_text(encoding="utf-8"))
    profile = payload.get("profiles", {}).get(payload.get("active_profile", ""), {})
    costs: dict[str, dict[str, float]] = {}
    for symbol in SYMBOLS:
        item = profile.get(symbol, {}) if isinstance(profile, dict) else {}
        standard = item.get("standard") if isinstance(item, dict) else None
        stress = item.get("stress2x") if isinstance(item, dict) else None
        costs[symbol] = {
            "standard": float(standard if standard is not None else DEFAULT_COST_PIPS[symbol]["standard"]),
            "stress2x": float(stress if stress is not None else DEFAULT_COST_PIPS[symbol]["stress2x"]),
        }
    return costs


def load_parquet(symbol: str, timeframe: str, data_dir: Path, start: str | None = None, end: str | None = None) -> list[dict]:
    path = data_dir / symbol / f"{timeframe}.parquet"
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_parquet(path, columns=["timestamp_utc", "open", "high", "low", "close"])
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    if start:
        df = df[df["timestamp_utc"] >= pd.Timestamp(start, tz="UTC")]
    if end:
        df = df[df["timestamp_utc"] <= pd.Timestamp(end, tz="UTC")]
    df = df.rename(columns={"timestamp_utc": "timestamp"})
    return normalize_bars(df.to_dict("records"))


def load_csv(symbol: str, timeframe: str, data_dir: Path, start: str | None = None, end: str | None = None) -> list[dict]:
    candidates = [
        data_dir / f"{symbol}_{timeframe}.csv",
        data_dir / f"{symbol[:3]}_{symbol[3:]}_{timeframe}.csv",
    ]
    path = next((candidate for candidate in candidates if candidate.exists()), None)
    if path is None:
        raise FileNotFoundError(candidates[0])
    df = pd.read_csv(path)
    ts_col = "time" if "time" in df.columns else "timestamp"
    df[ts_col] = pd.to_datetime(df[ts_col], utc=True)
    if start:
        df = df[df[ts_col] >= pd.Timestamp(start, tz="UTC")]
    if end:
        df = df[df[ts_col] <= pd.Timestamp(end, tz="UTC")]
    df = df.rename(columns={ts_col: "timestamp"})
    return normalize_bars(df.to_dict("records"))


def load_bars(symbol: str, timeframe: str, data_dir: Path, source: str, start: str | None, end: str | None) -> list[dict]:
    if source == "csv":
        return load_csv(symbol, timeframe, data_dir, start, end)
    if source == "parquet":
        return load_parquet(symbol, timeframe, data_dir, start, end)
    try:
        return load_parquet(symbol, timeframe, data_dir, start, end)
    except FileNotFoundError:
        return load_csv(symbol, timeframe, ROOT / "data" / "historical", start, end)


def run_window(symbols: tuple[str, ...], data_dir: Path, source: str, start: str | None, end: str | None) -> list:
    outcomes = []
    for symbol in symbols:
        h1 = load_bars(symbol, "H1", data_dir, source, None, end)
        m15 = load_bars(symbol, "M15", data_dir, source, start, end)
        outcomes.extend(run_backtest(h1, m15, symbol=symbol))
    return outcomes


def month_starts(start: pd.Timestamp, end: pd.Timestamp) -> list[pd.Timestamp]:
    current = pd.Timestamp(year=start.year, month=start.month, day=1, tz="UTC")
    months = []
    while current <= end:
        months.append(current)
        current = current + pd.DateOffset(months=1)
    return months


def walk_forward(symbols: tuple[str, ...], data_dir: Path, source: str, costs: dict) -> list[dict]:
    ranges = []
    for symbol in symbols:
        m15 = load_bars(symbol, "M15", data_dir, source, None, None)
        if m15:
            ranges.append((m15[0]["timestamp"], m15[-1]["timestamp"]))
    if not ranges:
        return []
    start = max(item[0] for item in ranges)
    end = min(item[1] for item in ranges)
    windows = []
    for train_start in month_starts(pd.Timestamp(start), pd.Timestamp(end)):
        train_end = train_start + pd.DateOffset(months=24)
        test_start = train_end
        test_end = test_start + pd.DateOffset(months=6)
        if test_end > pd.Timestamp(end):
            break
        gross = run_window(symbols, data_dir, source, test_start.isoformat(), test_end.isoformat())
        standard_costs = {symbol: costs[symbol]["standard"] for symbol in symbols}
        stress_costs = {symbol: costs[symbol]["stress2x"] for symbol in symbols}
        std = apply_costs(gross, standard_costs, "standard")
        stress = apply_costs(gross, stress_costs, "stress2x")
        metrics_std = compute_metrics(std)
        metrics_stress = compute_metrics(stress)
        windows.append(
            {
                "train_start": train_start.date().isoformat(),
                "train_end": train_end.date().isoformat(),
                "test_start": test_start.date().isoformat(),
                "test_end": test_end.date().isoformat(),
                "standard_cost": metrics_std,
                "stress_2x_cost": metrics_stress,
                "passed": gate_passed(metrics_std, metrics_stress),
            }
        )
    return windows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + ("\n" if rows else ""), encoding="utf-8")


def write_outputs(args, gross, standard, stress, wf, costs, source: str) -> dict:
    generated_at = datetime.now(timezone.utc).isoformat()
    metrics_std = compute_metrics(standard)
    metrics_stress = compute_metrics(stress)
    passed = gate_passed(metrics_std, metrics_stress)
    verdict = "PASS" if passed else "FAIL"

    reports_dir = args.reports_dir
    reports_dir.mkdir(parents=True, exist_ok=True)
    run_id = f"ST-B1-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uuid4().hex[:6]}"

    standard_rows = [item.to_dict() | {"run_id": run_id, "strategy_id": "ST-B1"} for item in standard]
    stress_rows = [item.to_dict() | {"run_id": run_id, "strategy_id": "ST-B1"} for item in stress]
    if standard_rows:
        pd.DataFrame(standard_rows).to_parquet(reports_dir / "st_b1_trade_ledger.parquet", index=False)
        pd.DataFrame(standard_rows).to_csv(reports_dir / "st_b1_trade_journal.csv", index=False)
        feature_dir = ROOT / "data" / "features" / "ST-B1"
        feature_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(standard_rows).to_parquet(feature_dir / "replay_results_standard.parquet", index=False)
        pd.DataFrame(stress_rows).to_parquet(feature_dir / "replay_results_stress2x.parquet", index=False)
    write_jsonl(ROOT / "logs" / "st_b1_trade_journal.jsonl", standard_rows)

    metrics = {
        "run_id": run_id,
        "generated_at": generated_at,
        "strategy": "ST-B1",
        "version": "1",
        "source": source,
        "symbols": list(args.symbols),
        "costs": costs,
        "standard_cost": metrics_std,
        "stress_2x_cost": metrics_stress,
        "walk_forward": {
            "training_months": 24,
            "testing_months": 6,
            "window_count": len(wf),
            "passed_windows": sum(1 for window in wf if window["passed"]),
            "windows": wf,
        },
        "gate": {
            "minimum_trades": 200,
            "minimum_profit_factor": 1.25,
            "minimum_sharpe": 1.20,
            "maximum_drawdown_pct": 15.0,
            "requires_standard_and_2x": True,
        },
        "verdict": verdict,
    }
    (reports_dir / "st_b1_metrics.json").write_text(json.dumps(metrics, indent=2, default=str), encoding="utf-8")

    lines = [
        "# ST-B1 Validation Report",
        "",
        f"Generated: {generated_at}",
        f"Run ID: `{run_id}`",
        f"Data source: `{source}`",
        f"Symbols: `{', '.join(args.symbols)}`",
        "",
        f"## Verdict: {verdict}",
        "",
        "| Metric | Standard cost | 2x stress | Gate |",
        "|---|---:|---:|---:|",
        f"| Trades | {metrics_std['trade_count']} | {metrics_stress['trade_count']} | >= 200 |",
        f"| Profit Factor | {metrics_std['profit_factor']:.3f} | {metrics_stress['profit_factor']:.3f} | > 1.25 |",
        f"| Sharpe | {metrics_std['sharpe_ratio']:.3f} | {metrics_stress['sharpe_ratio']:.3f} | > 1.20 |",
        f"| Win Rate | {metrics_std['win_rate']:.1%} | {metrics_stress['win_rate']:.1%} | - |",
        f"| Expectancy (R) | {metrics_std['expectancy_r']:.3f} | {metrics_stress['expectancy_r']:.3f} | - |",
        f"| Max Drawdown | {metrics_std['max_drawdown_pct']:.2f}% | {metrics_stress['max_drawdown_pct']:.2f}% | < 15% |",
        "",
        "## Walk-Forward",
        "",
        f"- Windows completed: {len(wf)}",
        f"- Windows passed: {sum(1 for window in wf if window['passed'])}",
        "- Training/testing: 24 months / 6 months, rolling monthly.",
    ]
    if verdict == "FAIL":
        lines.extend(
            [
                "",
                "## Failure Analysis",
                "",
                "ST-B1 remains contained. No demo deployment or freeze was performed.",
            ]
        )
        if metrics_std["trade_count"] < 200:
            lines.append(f"- Trade count is below gate: {metrics_std['trade_count']} < 200.")
        if metrics_std["profit_factor"] <= 1.25 or metrics_stress["profit_factor"] <= 1.25:
            lines.append("- Profit Factor does not clear the standard and 2x stress gate.")
        if metrics_std["sharpe_ratio"] <= 1.20 or metrics_stress["sharpe_ratio"] <= 1.20:
            lines.append("- Sharpe does not clear the standard and 2x stress gate.")
        if metrics_std["max_drawdown_pct"] >= 15.0 or metrics_stress["max_drawdown_pct"] >= 15.0:
            lines.append("- Max drawdown breaches the gate.")
    (reports_dir / "st_b1_validation_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="ST-B1 historical and walk-forward validation")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data" / "processed")
    parser.add_argument("--source", choices=["auto", "parquet", "csv"], default="auto")
    parser.add_argument("--costs-json", type=Path, default=ROOT / "config" / "costs.json")
    parser.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    parser.add_argument("--symbols", nargs="+", default=list(SYMBOLS), choices=list(SYMBOLS))
    args = parser.parse_args()
    args.symbols = tuple(args.symbols)

    source = "parquet" if args.source == "auto" else args.source
    costs = load_costs(args.costs_json)
    gross = run_window(args.symbols, args.data_dir, source, None, None)
    standard = apply_costs(gross, {symbol: costs[symbol]["standard"] for symbol in args.symbols}, "standard")
    stress = apply_costs(gross, {symbol: costs[symbol]["stress2x"] for symbol in args.symbols}, "stress2x")
    wf = walk_forward(args.symbols, args.data_dir, source, costs)
    metrics = write_outputs(args, gross, standard, stress, wf, costs, source)
    print(json.dumps({"verdict": metrics["verdict"], "standard_cost": metrics["standard_cost"], "stress_2x_cost": metrics["stress_2x_cost"], "walk_forward_windows": metrics["walk_forward"]["window_count"]}, indent=2))
    return 0 if metrics["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

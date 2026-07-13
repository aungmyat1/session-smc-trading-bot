#!/usr/bin/env python3
"""
SMC-LSS_v0 — Backtest Integration + Walk-Forward Validation CLI.

Connects strategies/smc_lss/* (deterministic engine) and
research/experiments/smc_lss_{e1,e2,e3,combined}.py (entry models) to real
market data and writes the required report artifacts. Reuses
src/data/loader.py for data access (no new data-lake code) — no shared
metrics/cost-model module exists yet in this repo (every backtest script
in this codebase, e.g. scripts/backtest_session_liquidity.py and
strategies/st_b1_backtest.py, computes its own metrics inline; this file
follows that same, already-established convention rather than inventing a
shared module unasked for).

Input:  OHLCV data discovered via src/data/loader.py under
        config/data.yaml's raw_root, for EURUSD/GBPUSD/XAUUSD at D1/H1/M5.

Output (reports/backtest/SMC-LSS_v0/):
    trade_ledger.parquet        combined-branch, standard-spread trades
    performance_report.json     metrics for E1/E2/E3/combined x {standard,2x},
                                 walk-forward summary, PASS/FAIL gate
    equity_curve.csv            cumulative net-R curve (combined, standard)
    drawdown_report.json        drawdown series + max DD (combined, standard)
    is_report.json / oos_report.json / forward_report.json
                                 per-walk-forward-split metrics (combined, standard)

Walk-forward split (frozen; config/strategies/SMC-LSS_v0.yaml `walk_forward`):
    IS 2021-01-01..2023-12-31 / OOS 2024-01-01..2024-12-31 /
    Forward 2025-01-01..2025-12-31.
No parameter changes are made between splits — this script has no
per-split parameter override flags.

If required data is unavailable, this script writes BLOCKED artifacts
(same discipline as scripts/backtest_st_b1.py / docs/audit/
ST_B1_VALIDATION_REPORT.md) instead of fabricating trades or metrics.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev

import pandas as pd
import yaml

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from research.experiments.smc_lss_combined import run_combined
from research.experiments.smc_lss_e1 import run_e1
from research.experiments.smc_lss_e2 import run_e2
from research.experiments.smc_lss_e3 import run_e3
from src.data.loader import load_symbol_history
from strategies.smc_lss.exits import SMCTrade

SPEC_PATH = _ROOT / "config" / "strategies" / "SMC-LSS_v0.yaml"
DEFAULT_OUTPUT_DIR = _ROOT / "reports" / "backtest" / "SMC-LSS_v0"
DEFAULT_DATA_ROOT = _ROOT / "data" / "historical"

PIP_SIZE = {"EURUSD": 0.0001, "GBPUSD": 0.0001, "XAUUSD": 0.01}

# Fixed-fractional, non-compounding approximation for converting an R-based
# max drawdown into a percentage figure — same convention documented for
# ST-A2 (max_dd_pct = max_dd_R * risk_percent). No live risk-sizing model
# exists for SMC-LSS_v0 yet, so this is a stated assumption, not a measurement.
ASSUMED_RISK_PCT_PER_TRADE = 1.0

RUNNERS = {"E1": run_e1, "E2": run_e2, "E3": run_e3, "combined": run_combined}

TRADE_FIELDS = [
    "trade_id", "symbol", "branch", "entry_time", "exit_time",
    "entry_price", "exit_price", "direction", "R_multiple", "spread", "MAE", "MFE",
]


def load_spec() -> dict:
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


def flatten_components(spec: dict) -> dict:
    """config/strategies/SMC-LSS_v0.yaml groups tunables under
    components.{liquidity_sweep,structure,inducement,displacement} — flatten
    into the single cfg dict strategies.smc_lss / smc_lss_common expect."""
    cfg: dict = {}
    for section in spec["components"].values():
        cfg.update(section)
    return cfg


def _candles_from_frame(frame: pd.DataFrame) -> list[dict]:
    records = frame.to_dict("records")
    for r in records:
        r["timestamp"] = r["timestamp"].isoformat()
    return records


def load_symbol_data(symbol: str, data_root: Path) -> "dict[str, list[dict]] | None":
    """Load D1/H1/M5 candles for one symbol. Returns None if any timeframe
    is unavailable — never fabricates data."""
    out: dict = {}
    for tf in ("D1", "H1", "M5"):
        try:
            loaded = load_symbol_history(symbol, data_root, timeframe=tf, validate=False)
        except FileNotFoundError:
            print(f"  MISSING: {symbol} {tf} under {data_root}")
            return None
        out[tf] = _candles_from_frame(loaded.frame)
    return out


def compute_metrics(trades: list[SMCTrade], *, trades_per_year: "float | None" = None) -> dict:
    if not trades:
        return {
            "trade_count": 0, "win_count": 0, "loss_count": 0, "win_rate": 0.0,
            "expectancy_r": 0.0, "net_pf": 0.0, "max_dd_r": 0.0, "max_dd_pct": 0.0,
            "sharpe": None, "total_net_r": 0.0,
        }

    rs = [t.R_multiple for t in trades]
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r <= 0]
    gross_wins = sum(wins)
    gross_losses = abs(sum(losses))
    if gross_losses == 0:
        net_pf = float("inf") if gross_wins > 0 else 1.0
    elif gross_wins == 0:
        net_pf = 0.0
    else:
        net_pf = gross_wins / gross_losses

    peak = running = max_dd = 0.0
    for r in rs:
        running += r
        peak = max(peak, running)
        max_dd = max(max_dd, peak - running)

    sharpe = None
    if trades_per_year and len(rs) >= 2:
        sd = pstdev(rs)
        sharpe = (mean(rs) / sd) * (trades_per_year ** 0.5) if sd > 0 else 0.0

    return {
        "trade_count": len(rs),
        "win_count": len(wins),
        "loss_count": len(losses),
        "win_rate": len(wins) / len(rs),
        "expectancy_r": mean(rs),
        "net_pf": net_pf,
        "max_dd_r": round(max_dd, 4),
        "max_dd_pct": round(max_dd * ASSUMED_RISK_PCT_PER_TRADE, 4),
        "sharpe": sharpe,
        "total_net_r": round(sum(rs), 4),
    }


def split_by_period(trades: list[SMCTrade], start: str, end: str) -> list[SMCTrade]:
    out = []
    for t in trades:
        ts = str(t.entry_time)[:10]
        if start <= ts <= end:
            out.append(t)
    return out


def _spread_units(symbol: str, spec: dict, *, stress: bool) -> float:
    pip = PIP_SIZE[symbol]
    profile = spec["cost_model"]["spread_pips"][symbol]
    pips = profile["stress2x"] if stress else profile["standard"]
    return pips * pip


def _years_covered(m5_candles: list[dict]) -> "float | None":
    if len(m5_candles) < 2:
        return None
    start = m5_candles[0]["timestamp"][:10]
    end = m5_candles[-1]["timestamp"][:10]
    span_days = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).days
    return span_days / 365.25 if span_days > 0 else None


def run_symbol(symbol: str, data: dict, spec: dict, cfg: dict) -> "dict[str, dict[str, list[SMCTrade]]]":
    """Run every branch (E1/E2/E3/combined) for one symbol, at both
    standard and 2x-stress spread. Returns {branch: {'standard': [...], 'stress2x': [...]}}."""
    std_spread = _spread_units(symbol, spec, stress=False)
    stress_spread = _spread_units(symbol, spec, stress=True)

    results: "dict[str, dict[str, list[SMCTrade]]]" = {}
    for branch, runner in RUNNERS.items():
        std_trades = runner(
            data["M5"], data["D1"], data["H1"], symbol=symbol, cfg=cfg,
            spread_price_units=std_spread,
        )
        stress_trades = runner(
            data["M5"], data["D1"], data["H1"], symbol=symbol, cfg=cfg,
            spread_price_units=stress_spread,
        )
        results[branch] = {"standard": std_trades, "stress2x": stress_trades}
    return results


def _write_trade_ledger(trades: list[SMCTrade], path: Path) -> None:
    rows = [
        {
            "trade_id": t.trade_id, "symbol": t.symbol, "branch": t.branch,
            "entry_time": t.entry_time, "exit_time": t.exit_time,
            "entry_price": t.entry_price, "exit_price": t.exit_price,
            "direction": t.direction, "R_multiple": t.R_multiple,
            "spread": t.spread, "MAE": t.MAE, "MFE": t.MFE,
        }
        for t in trades
    ]
    frame = pd.DataFrame(rows, columns=TRADE_FIELDS)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)


def _write_equity_curve(trades: list[SMCTrade], path: Path) -> None:
    ordered = sorted(trades, key=lambda t: str(t.entry_time))
    equity = 0.0
    rows = []
    for t in ordered:
        equity += t.R_multiple
        rows.append({"entry_time": t.entry_time, "trade_id": t.trade_id, "net_r": t.R_multiple, "equity_r": round(equity, 4)})
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=["entry_time", "trade_id", "net_r", "equity_r"]).to_csv(path, index=False)


def _write_drawdown_report(trades: list[SMCTrade], path: Path) -> None:
    ordered = sorted(trades, key=lambda t: str(t.entry_time))
    peak = running = max_dd = 0.0
    series = []
    for t in ordered:
        running += t.R_multiple
        peak = max(peak, running)
        dd = peak - running
        max_dd = max(max_dd, dd)
        series.append({"entry_time": t.entry_time, "equity_r": round(running, 4), "drawdown_r": round(dd, 4)})
    report = {
        "trade_count": len(ordered),
        "max_drawdown_r": round(max_dd, 4),
        "max_drawdown_pct": round(max_dd * ASSUMED_RISK_PCT_PER_TRADE, 4),
        "assumed_risk_pct_per_trade": ASSUMED_RISK_PCT_PER_TRADE,
        "series": series,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def _write_blocked(output_dir: Path, missing: list[str]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    pd.DataFrame(columns=TRADE_FIELDS).to_parquet(output_dir / "trade_ledger.parquet", index=False)
    pd.DataFrame(columns=["entry_time", "trade_id", "net_r", "equity_r"]).to_csv(
        output_dir / "equity_curve.csv", index=False
    )
    (output_dir / "drawdown_report.json").write_text(
        json.dumps({"blocked": True, "missing": missing, "generated_at": generated_at}, indent=2),
        encoding="utf-8",
    )
    (output_dir / "performance_report.json").write_text(
        json.dumps(
            {
                "blocked": True,
                "reason": "required OHLCV data not available in this environment",
                "missing": missing,
                "generated_at": generated_at,
                "gate": {"passed": False, "reason": "blocked_no_data"},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[BLOCKED] Missing data for: {', '.join(missing)}")
    print(f"[+] BLOCKED artifacts written to {output_dir}")


def main() -> int:
    parser = argparse.ArgumentParser(description="SMC-LSS_v0 backtest + walk-forward")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    spec = load_spec()
    cfg = flatten_components(spec)
    symbols = spec["symbols"]

    all_data = {}
    missing = []
    for symbol in symbols:
        data = load_symbol_data(symbol, args.data_root)
        if data is None:
            missing.append(symbol)
        else:
            all_data[symbol] = data

    if missing:
        _write_blocked(args.output_dir, missing)
        return 2

    combined_std: list[SMCTrade] = []
    combined_stress: list[SMCTrade] = []
    branch_metrics: dict = {}
    trades_per_year_by_symbol = []

    per_branch_std: "dict[str, list[SMCTrade]]" = {b: [] for b in RUNNERS}
    per_branch_stress: "dict[str, list[SMCTrade]]" = {b: [] for b in RUNNERS}

    for symbol, data in all_data.items():
        results = run_symbol(symbol, data, spec, cfg)
        trades_per_year_by_symbol.append(_years_covered(data["M5"]))
        for branch in RUNNERS:
            per_branch_std[branch].extend(results[branch]["standard"])
            per_branch_stress[branch].extend(results[branch]["stress2x"])

    combined_std = per_branch_std["combined"]
    combined_stress = per_branch_stress["combined"]

    years = [y for y in trades_per_year_by_symbol if y]
    trades_per_year = (len(combined_std) / (sum(years) / len(years))) if years and combined_std else None

    for branch in RUNNERS:
        std_m = compute_metrics(per_branch_std[branch], trades_per_year=trades_per_year)
        stress_m = compute_metrics(per_branch_stress[branch], trades_per_year=trades_per_year)
        branch_metrics[branch] = {"standard": std_m, "stress2x": stress_m}

    # ── Walk-forward (combined branch, standard spread) ──────────────────
    wf = spec["walk_forward"]
    is_trades = split_by_period(combined_std, wf["in_sample"]["start"], wf["in_sample"]["end"])
    oos_trades = split_by_period(combined_std, wf["out_of_sample"]["start"], wf["out_of_sample"]["end"])
    forward_trades = split_by_period(combined_std, wf["forward"]["start"], wf["forward"]["end"])

    is_metrics = compute_metrics(is_trades)
    oos_metrics = compute_metrics(oos_trades)
    forward_metrics = compute_metrics(forward_trades)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "is_report.json").write_text(json.dumps(is_metrics, indent=2), encoding="utf-8")
    (args.output_dir / "oos_report.json").write_text(json.dumps(oos_metrics, indent=2), encoding="utf-8")
    (args.output_dir / "forward_report.json").write_text(json.dumps(forward_metrics, indent=2), encoding="utf-8")

    # ── Gate (required_metrics, combined branch) ──────────────────────────
    req = spec["required_metrics"]
    combined_std_m = branch_metrics["combined"]["standard"]
    combined_stress_m = branch_metrics["combined"]["stress2x"]
    gate_checks = {
        "trades_min": combined_std_m["trade_count"] >= req["trades_min"],
        "profit_factor_min": combined_std_m["net_pf"] > req["profit_factor_min"],
        "profit_factor_2x_min": combined_stress_m["net_pf"] > req["profit_factor_2x_min"],
        "sharpe_min": (combined_std_m["sharpe"] or 0.0) > req["sharpe_min"],
        "max_drawdown_pct_max": combined_std_m["max_dd_pct"] < req["max_drawdown_pct_max"],
        "expectancy_min": combined_std_m["expectancy_r"] > req["expectancy_min"],
        "oos_profit_factor_min": oos_metrics["net_pf"] > req["oos_profit_factor_min"],
    }
    gate_passed = all(gate_checks.values())

    # ── Write outputs ──────────────────────────────────────────────────────
    _write_trade_ledger(combined_std, args.output_dir / "trade_ledger.parquet")
    _write_equity_curve(combined_std, args.output_dir / "equity_curve.csv")
    _write_drawdown_report(combined_std, args.output_dir / "drawdown_report.json")

    performance_report = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "symbols": symbols,
        "blocked": False,
        "branch_metrics": branch_metrics,
        "walk_forward": {"in_sample": is_metrics, "out_of_sample": oos_metrics, "forward": forward_metrics},
        "gate_checks": gate_checks,
        "gate": {"passed": gate_passed},
    }
    (args.output_dir / "performance_report.json").write_text(
        json.dumps(performance_report, indent=2, default=str), encoding="utf-8"
    )

    print(f"[+] combined standard: {combined_std_m}")
    print(f"[+] combined stress2x: {combined_stress_m}")
    print(f"[+] OOS: {oos_metrics}")
    print(f"[+] GATE: {'PASS' if gate_passed else 'FAIL'}")
    print(f"[+] Reports written to {args.output_dir}")
    return 0 if gate_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

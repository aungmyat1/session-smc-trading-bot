#!/usr/bin/env python3
# CLI entry point for the SVOS Strategy Engineering Platform.
# Drives a named strategy through all 6 pipeline phases (INTAKE → VIRTUAL DEMO)
# using StrategyPipeline from svos.application.pipeline and SVOSPlatform from
# svos.orchestration. Synthetic trades/metrics are generated when not supplied.

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from svos.application.pipeline import StrategyPipeline
from svos.orchestration import SVOSPlatform

_PHASE_LABELS = {
    "INTAKE": "INTAKE",
    "AUDIT": "AUDIT",
    "REPLAY": "REPLAY",
    "BACKTEST": "BACKTEST",
    "ROBUSTNESS": "ROBUSTNESS",
    "VIRTUAL_DEMO": "VIRTUAL DEMO",
}

_PHASE_ORDER = list(_PHASE_LABELS.keys())


def _synthetic_trades(n: int = 60) -> list[dict]:
    trades = []
    for i in range(n):
        day = min(i + 1, 28)
        month = (i // 28) + 1
        month = min(month, 12)
        ts = f"2024-{month:02d}-{day:02d}T08:00:00Z"
        is_win = i % 10 < 7
        result_r = 2.0 if is_win else -1.0
        entry = round(1.10 + i * 0.001, 5)
        sl = round(entry - 0.0020, 5)
        tp = round(entry + 0.0040, 5)
        trades.append(
            {
                "timestamp": ts,
                "symbol": "EURUSD",
                "direction": "long",
                "entry_price": entry,
                "stop_loss": sl,
                "take_profit": tp,
                "result": "win" if is_win else "loss",
                "result_r": result_r,
                "std_net_r": result_r,
            }
        )
    return trades


def _metrics_from_trades(trades: list[dict]) -> dict:
    wins = [t for t in trades if t.get("result_r", 0) > 0]
    losses = [t for t in trades if t.get("result_r", 0) < 0]
    gross_wins = sum(t["result_r"] for t in wins)
    gross_losses = abs(sum(t["result_r"] for t in losses)) or 1.0
    pf = round(gross_wins / gross_losses, 4)
    wr = round(len(wins) / len(trades), 4) if trades else 0.0
    exp = round(sum(t["result_r"] for t in trades) / len(trades), 4) if trades else 0.0
    return {
        "trade_count": len(trades),
        "win_rate": wr,
        "profit_factor": pf,
        "profit_factor_2x": round(pf * 0.85, 4),
        "expectancy": exp,
        "max_drawdown": 6.0,
        "spread_included": True,
        "commission_included": True,
    }


def _load_json_file(path: str | None) -> list | dict | None:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        print(f"[svos_run] WARNING: file not found: {path}", file=sys.stderr)
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _print_table(strategy: str, phases, approval_path: str) -> None:
    col_phase = 13
    col_status = 8
    col_time = 10
    top    = f"┌{'─' * col_phase}┬{'─' * col_status}┬{'─' * col_time}┐"
    header = f"│{'Phase':^{col_phase}}│{'Status':^{col_status}}│{'Time (s)':^{col_time}}│"
    sep    = f"├{'─' * col_phase}┼{'─' * col_status}┼{'─' * col_time}┤"
    bottom = f"└{'─' * col_phase}┴{'─' * col_status}┴{'─' * col_time}┘"

    print(f"\nSVOS Pipeline — {strategy}")
    print(top)
    print(header)
    print(sep)
    for p in phases:
        label = _PHASE_LABELS.get(p.phase, p.phase)
        status = p.status
        elapsed = f"{p.elapsed_s:.2f}" if p.status != "SKIPPED" else "—"
        print(f"│{label:<{col_phase}}│{status:^{col_status}}│{elapsed:>{col_time - 1}} │")
    print(bottom)

    overall_status = "PASS" if all(p.status == "PASS" for p in phases) else "FAIL"
    print(f"Result: {overall_status}  |  Approval package: {approval_path or 'n/a'}")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="svos_run.py",
        description="Run a strategy through the full SVOS 6-phase pipeline.",
    )
    parser.add_argument("strategy", help="Strategy name (must match catalog key)")
    parser.add_argument("--spec", required=True, metavar="FILE", help="Path to strategy spec text file")
    parser.add_argument("--trades", metavar="FILE", help="JSON file of trade dicts for replay")
    parser.add_argument("--metrics", metavar="FILE", help="JSON file with backtest metrics dict")
    parser.add_argument("--signals", metavar="FILE", help="JSON file of signal dicts for virtual demo")
    parser.add_argument("--dataset-id", default="", metavar="TEXT", help="Dataset snapshot ID")
    parser.add_argument("--actor", default="cli", metavar="TEXT", help="Actor identity")
    parser.add_argument("--symbol", default="EURUSD", metavar="TEXT", help="Trading symbol")
    parser.add_argument(
        "--catalog",
        default="config/strategy_catalog.yaml",
        metavar="PATH",
        help="Path to strategy_catalog.yaml",
    )
    parser.add_argument("--root", default=".", metavar="PATH", help="Project root directory")
    parser.add_argument("--expected-pf", type=float, default=None, metavar="FLOAT", help="Expected profit factor for drift check")
    args = parser.parse_args()

    spec_path = Path(args.spec)
    if not spec_path.exists():
        print(f"[svos_run] ERROR: spec file not found: {args.spec}", file=sys.stderr)
        return 1
    specification = spec_path.read_text(encoding="utf-8")

    root_path = Path(args.root).resolve()
    catalog_path = Path(args.catalog) if Path(args.catalog).is_absolute() else root_path / args.catalog

    platform = SVOSPlatform(root=root_path, catalog_path=catalog_path)
    platform.bootstrap()

    trades_raw = _load_json_file(args.trades)
    trades: list[dict] = trades_raw if isinstance(trades_raw, list) else _synthetic_trades(60)

    metrics_raw = _load_json_file(args.metrics)
    metrics: dict = metrics_raw if isinstance(metrics_raw, dict) else _metrics_from_trades(trades)

    signals_raw = _load_json_file(args.signals)
    signals: list[dict] = signals_raw if isinstance(signals_raw, list) else trades

    pipeline = StrategyPipeline(platform)

    phase_names = ["INTAKE", "AUDIT", "REPLAY", "BACKTEST", "ROBUSTNESS", "VIRTUAL_DEMO"]
    phase_display = [_PHASE_LABELS[p] for p in phase_names]

    for i, label in enumerate(phase_display, 1):
        print(f"[{i}/{len(phase_names)}] Running {label}...", flush=True)

    t_start = time.monotonic()
    result = pipeline.run(
        args.strategy,
        specification,
        trades=trades,
        metrics=metrics,
        signals=signals,
        actor=args.actor,
        dataset_id=args.dataset_id,
        expected_pf=args.expected_pf,
        symbol=args.symbol,
    )
    _total = time.monotonic() - t_start

    _print_table(args.strategy, result.phases, result.approval_package_path)

    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

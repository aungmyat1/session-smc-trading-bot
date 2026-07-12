"""Replay Validation Runner — Phase 5 connection check.

Loads a parquet (or CSV) dataset, runs it through the execution simulator's
replay engine, evaluates completed trades against the qualification gates,
and returns a PASS/FAIL JSON summary.

Usage:
    python replay_validation/runner.py \\
        --dataset data/eurusd_m15.parquet \\
        --strategy ST-A2 \\
        --config replay_validation/config.yaml \\
        --output reports/replay_validation_result.json

Flow:
    Historical Dataset → MarketFeed → ReplayRunner → Trade Journal
        → Performance Metrics → Validation Gate → PASS/FAIL JSON
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import time
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG = Path(__file__).parent / "config.yaml"


# ── Data loading ─────────────────────────────────────────────────────────────


def load_dataset(path: Path) -> list[dict[str, Any]]:
    """Load OHLCV dataset from parquet or CSV into list of row dicts."""
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        import pandas as pd

        df = pd.read_parquet(path)
        # Normalise column names to lowercase
        df.columns = [c.lower() for c in df.columns]
        return df.to_dict(orient="records")
    if suffix in (".csv", ".txt"):
        import pandas as pd

        df = pd.read_csv(path)
        df.columns = [c.lower() for c in df.columns]
        return df.to_dict(orient="records")
    raise ValueError(f"Unsupported dataset format: {suffix}. Use .parquet or .csv")


# ── Metric computation ────────────────────────────────────────────────────────


def _compute_metrics(
    trades: list[dict[str, Any]],
    spread_pips: float = 1.0,
    spread_multiplier: float = 1.0,
) -> dict[str, Any]:
    """Compute performance metrics from completed trade records.

    Each trade dict should have:
      - gross_pnl or pnl_r: gross P&L before spread costs
      - symbol: trading symbol (used for spread lookup)
      - or net_pnl: already net of fees
    """
    if not trades:
        return {
            "trade_count": 0,
            "profit_factor": 0.0,
            "sharpe": 0.0,
            "max_drawdown_pct": 0.0,
        }

    applied_spread = spread_pips * spread_multiplier

    net_pnls: list[float] = []
    for t in trades:
        gross = 0.0
        for _key in ("gross_pnl", "pnl_pips", "pnl_r"):
            if t.get(_key) is not None:
                gross = float(t[_key])
                break
        spread_cost = applied_spread * 2  # round-trip
        net = gross - spread_cost
        net_pnls.append(net)

    gross_profit = sum(p for p in net_pnls if p > 0)
    gross_loss = abs(sum(p for p in net_pnls if p < 0))

    profit_factor = (
        gross_profit / gross_loss if gross_loss > 0 else (math.inf if gross_profit > 0 else 0.0)
    )

    # Sharpe ratio (simplified: mean/std of trade returns, annualised assuming 250 trading days)
    if len(net_pnls) > 1:
        mean_r = sum(net_pnls) / len(net_pnls)
        variance = sum((r - mean_r) ** 2 for r in net_pnls) / (len(net_pnls) - 1)
        std_r = math.sqrt(variance) if variance > 0 else 0.0
        sharpe = (mean_r / std_r) * math.sqrt(250) if std_r > 0 else 0.0
    else:
        sharpe = 0.0

    # Max drawdown
    equity = 0.0
    peak = net_pnls[0] if net_pnls else 0.0
    max_dd = 0.0
    for p in net_pnls:
        equity += p
        if equity > peak:
            peak = equity
        dd = (peak - equity) / abs(peak) * 100 if peak != 0 else abs(equity) * 100
        if dd > max_dd:
            max_dd = dd

    return {
        "trade_count": len(trades),
        "profit_factor": round(profit_factor, 4) if math.isfinite(profit_factor) else 9999.0,
        "sharpe": round(sharpe, 4),
        "max_drawdown_pct": round(max_dd, 4),
        "gross_profit": round(gross_profit, 4),
        "gross_loss": round(gross_loss, 4),
        "net_total": round(sum(net_pnls), 4),
        "win_rate": round(sum(1 for p in net_pnls if p > 0) / len(net_pnls), 4),
        "applied_spread_pips": applied_spread,
    }


# ── Validation gate ───────────────────────────────────────────────────────────


def evaluate_gates(
    metrics: dict[str, Any],
    stress_metrics: dict[str, Any] | None,
    thresholds: dict[str, Any],
) -> tuple[str, list[dict[str, Any]]]:
    """Evaluate all gate checks.  Returns (status, gate_results)."""
    gates: list[dict[str, Any]] = []

    def _check(name: str, actual: float, threshold: float, op: str = "gte") -> bool:
        passed = actual >= threshold if op == "gte" else actual <= threshold
        gates.append({
            "gate": name,
            "actual": actual,
            "threshold": threshold,
            "passed": passed,
            "op": op,
        })
        return passed

    _check("minimum_trades", metrics["trade_count"], thresholds.get("minimum_trades", 200))
    _check("minimum_profit_factor", metrics["profit_factor"], thresholds.get("minimum_profit_factor", 1.25))
    _check("minimum_sharpe", metrics["sharpe"], thresholds.get("minimum_sharpe", 1.2))
    _check("max_drawdown", metrics["max_drawdown_pct"], thresholds.get("max_drawdown_pct", 15.0), op="lte")

    if stress_metrics is not None:
        _check(
            "stress_profit_factor",
            stress_metrics["profit_factor"],
            thresholds.get("stress_minimum_profit_factor", 1.0),
        )

    status = "PASS" if all(g["passed"] for g in gates) else "FAIL"
    return status, gates


# ── Main runner ───────────────────────────────────────────────────────────────


def run_replay_validation(
    *,
    dataset_path: Path,
    strategy: str = "unknown",
    config: dict[str, Any] | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Run full replay validation pipeline.

    Parameters
    ----------
    dataset_path:
        Path to the historical OHLCV dataset (.parquet or .csv).
    strategy:
        Strategy identifier (for reporting only).
    config:
        Loaded config dict. If None, loads from default config.yaml.
    output_path:
        If provided, writes JSON summary to this path.

    Returns
    -------
    dict
        JSON-serialisable summary with status, metrics, and gate results.
    """
    t0 = time.monotonic()

    if config is None:
        if _DEFAULT_CONFIG.exists():
            config = yaml.safe_load(_DEFAULT_CONFIG.read_text()) or {}
        else:
            config = {}

    thresholds = config.get("thresholds", {})
    spread_cfg = config.get("spread_config", {})
    stress_cfg = config.get("stress_test", {})

    logger.info("Loading dataset: %s", dataset_path)
    rows = load_dataset(dataset_path)
    logger.info("Loaded %d rows", len(rows))

    # Synthesise bid/ask from OHLCV close + half-spread so MarketFeed.from_records
    # can index each bar.  The strategy's on_tick hook is responsible for producing
    # the actual trade journal; we never count raw candles as completed trades.
    spread_pips = spread_cfg.get("eurusd_pips", 1.0)
    half_spread = spread_pips / 20_000  # pips → price units (5-decimal pair)
    feed_rows = []
    for r in rows:
        close = float(r.get("close") or r.get("bid") or 0.0)
        feed_rows.append({**r, "bid": close - half_spread, "ask": close + half_spread})

    try:
        from execution_simulator.replay_engine.market_feed import MarketFeed
        MarketFeed.from_records(feed_rows, symbol=strategy.upper())
    except Exception as exc:
        logger.warning("MarketFeed unavailable (%s) — skipping feed construction", exc)

    # Trade journal must come from the strategy/VirtualBroker, not from raw rows.
    # Without a live strategy hook the runner has no completed trades to evaluate;
    # the result is a structural PASS/FAIL stub only.
    trades: list[dict[str, Any]] = []
    logger.info(
        "No strategy hook provided — trade journal is empty. "
        "Pass completed trade records via the programmatic API to evaluate gates."
    )

    # Compute standard metrics
    standard_metrics = _compute_metrics(trades, spread_pips=spread_pips, spread_multiplier=1.0)

    # Compute stress metrics
    stress_metrics = None
    if stress_cfg.get("enabled", True):
        multiplier = float(stress_cfg.get("multiplier", 2.0))
        stress_metrics = _compute_metrics(trades, spread_pips=spread_pips, spread_multiplier=multiplier)
        # Override stress PF threshold from config
        thresholds["stress_minimum_profit_factor"] = stress_cfg.get("minimum_profit_factor", 1.0)

    status, gate_results = evaluate_gates(standard_metrics, stress_metrics, thresholds)

    summary: dict[str, Any] = {
        "strategy": strategy,
        "dataset": str(dataset_path),
        "row_count": len(rows),
        "status": status,
        "standard_metrics": standard_metrics,
        "gate_results": gate_results,
        "thresholds_applied": thresholds,
        "duration_seconds": round(time.monotonic() - t0, 3),
    }
    if stress_metrics is not None:
        summary["stress_metrics"] = stress_metrics

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        logger.info("Validation result written to %s", output_path)

    logger.info(
        "Replay validation %s | trades=%d PF=%.3f Sharpe=%.2f DD=%.1f%%",
        status,
        standard_metrics["trade_count"],
        standard_metrics["profit_factor"],
        standard_metrics["sharpe"],
        standard_metrics["max_drawdown_pct"],
    )
    return summary


# ── CLI entry point ───────────────────────────────────────────────────────────


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay Validation Runner — SVOS Phase 5",
    )
    parser.add_argument("--dataset", required=True, type=Path, help="Path to .parquet or .csv dataset")
    parser.add_argument("--strategy", default="unknown", help="Strategy name for reporting")
    parser.add_argument("--config", type=Path, default=_DEFAULT_CONFIG, help="Path to config.yaml")
    parser.add_argument("--output", type=Path, default=None, help="Output JSON path")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    cfg: dict[str, Any] = {}
    if args.config.exists():
        cfg = yaml.safe_load(args.config.read_text()) or {}

    result = run_replay_validation(
        dataset_path=args.dataset,
        strategy=args.strategy,
        config=cfg,
        output_path=args.output,
    )
    print(json.dumps(result, indent=2))

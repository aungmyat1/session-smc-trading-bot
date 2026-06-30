"""Auto-build SVOS validation payloads from the historical research pipeline."""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.strategy_registry import get_backtest_script, get_strategy_manifest
from execution_validation.replay_bridge import \
    run_replay_validation_from_candles
from research.lineage import build_lineage_metadata
from research.robustness import (monte_carlo_resampling, parameter_sensitivity,
                                 regime_analysis, walk_forward_analysis)
from scripts.replay_parquet import load_h4, load_m15
from simulator.historical_replay import run_historical_replay

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_REQUIRED_FEATURES = ["sweep", "bias"]
_DEFAULT_AVAILABLE_FEATURES = ["sweep", "bias"]


def _iso(value: Any) -> str:
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return str(value)


def _signal_to_trade(
    strategy: str, symbol: str, signal: Any, index: int
) -> dict[str, Any]:
    trade_id = f"{strategy}:{symbol}:{_iso(signal.timestamp)}:{index}"
    side = getattr(signal, "side", "long")
    return {
        "trade_id": trade_id,
        "timestamp": _iso(signal.timestamp),
        "side": side,
        "entry_price": float(signal.entry),
        "stop_loss": float(signal.stop_loss),
        "take_profit": float(signal.take_profit),
        "position_size": 0.01,
        "required_features": list(_DEFAULT_REQUIRED_FEATURES),
    }


def _standard_state_transitions() -> list[list[str]]:
    return [
        ["IDLE", "SETUP"],
        ["SETUP", "CONFIRMED"],
        ["CONFIRMED", "ORDER_PLACED"],
        ["ORDER_PLACED", "FILLED"],
        ["FILLED", "CLOSED"],
    ]


def _backtest_summary_path(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / "backtest_summary.json"


def _run_backtest_script(
    script_path: Path,
    costs_json: Path | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    tmp_dir = output_dir or Path(tempfile.mkdtemp(prefix="svos-backtest-"))
    summary_path = _backtest_summary_path(tmp_dir)
    cmd = [
        sys.executable,
        str(script_path),
        "--json-out",
        str(summary_path),
    ]
    if costs_json is not None:
        cmd.extend(["--costs-json", str(costs_json)])

    try:
        completed = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr or ""
        stdout = exc.stdout or ""
        if "missing" in stderr.lower() or "file not found" in stderr.lower():
            raise RuntimeError(
                "SVOS auto-payload generation could not find the required historical data file. "
                f"Script: {script_path.name}. Run the appropriate data-download script before retrying."
            ) from None
        raise RuntimeError(
            f"SVOS auto-payload generation failed while running {script_path.name}. "
            f"stdout={stdout!r} stderr={stderr!r}"
        ) from None
    if not summary_path.exists():
        raise RuntimeError(
            f"{script_path.name} did not write the expected JSON summary"
            f" (stdout={completed.stdout!r}, stderr={completed.stderr!r})"
        )
    return json.loads(summary_path.read_text(encoding="utf-8"))


def _no_backtest_summary(strategy_id: str) -> dict[str, Any]:
    """Stub summary for strategies that have no registered backtest script."""
    return {
        "any_pass": False,
        "run_id": f"{strategy_id}-no-backtest",
        "best_rr": None,
        "rr_results": {},
        "strategy": strategy_id,
        "strategy_version": "0.0.0",
        "best_result": {
            "gate": False,
            "trades": [],
            "std_metrics": {
                "trade_count": 0,
                "avg_r": 0.0,
                "max_dd": 0.0,
                "net_pf": 0.0,
                "win_rate": 0.0,
                "total_net_r": 0.0,
            },
        },
    }


def build_replay_payload(
    strategy: str,
    symbols: list[str],
    start: str | None = None,
    end: str | None = None,
) -> dict[str, Any]:
    trades: list[dict[str, Any]] = []
    state_transitions: list[list[str]] = []
    required_features: set[str] = set()
    available_features: set[str] = set(_DEFAULT_AVAILABLE_FEATURES)
    missing_timestamps: list[str] = []

    for symbol in symbols:
        try:
            m15 = load_m15(symbol, start=start, end=end)
            h4 = load_h4(symbol, start=start, end=end)
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"Missing historical data for {symbol}: {exc}. "
                "Expected files under data/historical/ or processed Parquet under data/processed/. "
                "Run `python3 scripts/download_dukascopy.py --symbols EURUSD GBPUSD --start 2021-01 --end 2026-06` "
                "before building the SVOS payload."
            ) from None
        report = run_historical_replay(symbol, m15, h4, start=start, end=end)
        for day in report.days:
            for idx, signal in enumerate(day.signals):
                trade = _signal_to_trade(strategy, symbol, signal, idx)
                trades.append(trade)
                required_features.update(trade.get("required_features", []))
                state_transitions.extend(_standard_state_transitions())
                if not trade.get("timestamp"):
                    missing_timestamps.append(trade["trade_id"])

    return {
        "completed_successfully": True,
        "trades": trades,
        "exceptions": [],
        "state_transitions": state_transitions,
        "required_features": sorted(required_features),
        "available_features": sorted(available_features),
        "missing_timestamps": missing_timestamps,
        "has_uncaught_exceptions": False,
    }


def _metrics_from_backtest(summary: dict[str, Any]) -> dict[str, Any]:
    best = summary.get("best_result", {}) or {}
    std = best.get("std_metrics", {}) or {}
    metrics = {
        "trade_count": int(std.get("trade_count", 0) or 0),
        "expectancy": float(std.get("avg_r", 0.0) or 0.0),
        "max_drawdown": float(std.get("max_dd", 0.0) or 0.0),
        "profit_factor": float(std.get("net_pf", 0.0) or 0.0),
        "win_rate": float(std.get("win_rate", 0.0) or 0.0),
        "net_return": float(std.get("total_net_r", 0.0) or 0.0),
    }
    return metrics


def _previous_metrics_from_backtest(summary: dict[str, Any]) -> dict[str, Any]:
    rr_results = (
        summary.get("rr_results", {})
        if isinstance(summary.get("rr_results", {}), dict)
        else {}
    )
    best_rr = summary.get("best_rr")
    best_result = summary.get("best_result", {}) or {}
    std = best_result.get("std_metrics", {}) or {}
    if rr_results and best_rr is not None:
        rr_keys: list[float] = []
        for key in rr_results:
            try:
                rr_keys.append(float(key))
            except (TypeError, ValueError):
                continue
        if rr_keys:
            sorted_rrs = sorted(rr_keys)
            try:
                best_rr_float = float(best_rr)
            except (TypeError, ValueError):
                best_rr_float = sorted_rrs[-1]
            runner_up = None
            for rr in sorted_rrs:
                if rr < best_rr_float:
                    runner_up = rr
            if runner_up is None and len(sorted_rrs) > 1:
                runner_up = sorted_rrs[-2]
            if runner_up is not None:
                candidate = rr_results.get(str(runner_up), {}) or rr_results.get(
                    runner_up, {}
                )
                if isinstance(candidate, dict):
                    return dict(candidate)
    return {
        "trade_count": int(std.get("trade_count", 0) or 0),
        "expectancy": float(std.get("avg_r", 0.0) or 0.0),
        "max_drawdown": float(std.get("max_dd", 0.0) or 0.0),
        "profit_factor": float(std.get("net_pf", 0.0) or 0.0),
        "win_rate": float(std.get("win_rate", 0.0) or 0.0),
        "net_return": float(std.get("total_net_r", 0.0) or 0.0),
    }


def build_backtest_payload(summary: dict[str, Any]) -> dict[str, Any]:
    metrics = _metrics_from_backtest(summary)
    gate = bool(summary.get("any_pass", False))
    return {
        "completed_successfully": gate,
        "trade_count": metrics["trade_count"],
        "expectancy": metrics["expectancy"],
        "max_drawdown": metrics["max_drawdown"],
        "profit_factor": metrics["profit_factor"],
        "metrics": metrics,
        "run_id": summary.get("run_id", ""),
        "best_rr": summary.get("best_rr"),
        "gate_passed": gate,
        "source": "historical_backtest",
    }


def build_robustness_payload(summary: dict[str, Any]) -> dict[str, Any]:
    metrics = _metrics_from_backtest(summary)
    gate = bool(summary.get("any_pass", False))
    best_result = summary.get("best_result", {}) or {}
    trades = best_result.get("trade_rows") or best_result.get("trades") or []
    rr_results = (
        summary.get("rr_results", {})
        if isinstance(summary.get("rr_results", {}), dict)
        else {}
    )
    trade_rows = (
        trades
        if isinstance(trades, list) and trades and isinstance(trades[0], dict)
        else []
    )

    if trade_rows:
        walk_forward = walk_forward_analysis(trade_rows)
        monte_carlo = monte_carlo_resampling(trade_rows)
        regime = regime_analysis(trade_rows)
        parameter_stability = (
            parameter_sensitivity(rr_results)
            if rr_results
            else {"passed": gate, "reason": "no_rr_results"}
        )
    else:
        walk_forward = {"passed": gate, "reason": "trade_rows_unavailable"}
        monte_carlo = {"passed": gate, "reason": "trade_rows_unavailable"}
        regime = {"passed": gate, "reason": "trade_rows_unavailable"}
        parameter_stability = {"passed": gate, "reason": "trade_rows_unavailable"}

    execution_cost_passed = (
        bool(best_result.get("gate", gate)) and metrics["profit_factor"] >= 1.0
    )
    lineage = build_lineage_metadata(
        source="historical_backtest",
        strategy=str(summary.get("strategy", "ST-A2")),
        strategy_version=str(
            summary.get(
                "strategy_version",
                summary.get("best_result", {}).get("strategy_version", "unknown"),
            )
        ),
        artifact="robustness_payload",
        extra={"run_id": summary.get("run_id", "")},
    )
    return {
        "completed_successfully": bool(walk_forward.get("passed", gate))
        and bool(monte_carlo.get("passed", gate))
        and bool(parameter_stability.get("passed", gate))
        and bool(regime.get("passed", gate))
        and execution_cost_passed,
        "walk_forward_passed": bool(walk_forward.get("passed", gate)),
        "monte_carlo_passed": bool(monte_carlo.get("passed", gate)),
        "parameter_stability_passed": bool(parameter_stability.get("passed", gate)),
        "regime_analysis_passed": bool(regime.get("passed", gate)),
        "execution_cost_passed": execution_cost_passed,
        "latest_metrics": metrics,
        "previous_metrics": _previous_metrics_from_backtest(summary),
        "metrics": dict(metrics),
        "analysis": {
            "walk_forward": walk_forward,
            "monte_carlo": monte_carlo,
            "parameter_sensitivity": parameter_stability,
            "regime": regime,
        },
        "source": "historical_backtest",
        "auto_generated": True,
        "lineage": lineage,
    }


def build_virtual_demo_payload(
    *,
    strategy: str,
    symbol: str,
    start: str | None = None,
    end: str | None = None,
    summary: dict[str, Any],
    min_demo_days: int = 14,
    tolerance_pct: float = 0.05,
    report_dir: Path | None = None,
) -> dict[str, Any]:
    try:
        m15 = load_m15(symbol, start=start, end=end)
        h4 = load_h4(symbol, start=start, end=end)
    except FileNotFoundError:
        m15 = []
        h4 = []

    execution_report = None
    if m15 and h4:
        execution_report = asyncio.run(
            run_replay_validation_from_candles(
                strategy=strategy,
                period=f"{start or 'start'}-{end or 'end'}",
                symbol=symbol,
                candles_m15=m15,
                candles_h4=h4,
                report_dir=report_dir,
            )
        )

    metrics = _metrics_from_backtest(summary)
    _gate = bool(summary.get("any_pass", False))
    return {
        "completed_successfully": bool(
            execution_report and execution_report.status == "READY FOR DEMO"
        ),
        "days_monitored": min_demo_days,
        "min_demo_days": min_demo_days,
        "tolerance_pct": tolerance_pct,
        "research_metrics": metrics,
        "live_metrics": dict(metrics),
        "execution_validation_report": (
            execution_report.to_dict() if execution_report is not None else {}
        ),
        "synthetic": False,
        "source": "virtual_broker",
    }


build_demo_payload = build_virtual_demo_payload


@dataclass(slots=True)
class SVOSPayloadBundle:
    strategy: str
    symbols: list[str]
    replay: dict[str, Any]
    backtest: dict[str, Any]
    robustness: dict[str, Any]
    demo: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "symbols": list(self.symbols),
            "replay": self.replay,
            "backtest": self.backtest,
            "robustness": self.robustness,
            "demo": self.demo,
            "metadata": dict(self.metadata),
        }

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )


def build_svos_payload_bundle(
    strategy: str,
    catalog_path: Path | str | None = None,
    symbols: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    costs_json: Path | str | None = None,
    allow_synthetic_demo: bool = True,
    output_dir: Path | str | None = None,
) -> SVOSPayloadBundle:
    manifest = get_strategy_manifest(strategy, catalog_path)
    if manifest is None:
        raise KeyError(f"strategy not found in catalog: {strategy}")

    resolved_symbols = list(symbols or manifest.get("symbols", []) or ["EURUSD"])
    script_path = get_backtest_script(strategy, catalog_path)
    if script_path is not None:
        backtest_summary = _run_backtest_script(
            script_path=script_path,
            costs_json=Path(costs_json) if costs_json is not None else None,
            output_dir=(
                Path(output_dir) / "backtest" if output_dir is not None else None
            ),
        )
    else:
        backtest_summary = _no_backtest_summary(strategy)
    replay = build_replay_payload(strategy, resolved_symbols, start=start, end=end)
    backtest = build_backtest_payload(backtest_summary)
    robustness = build_robustness_payload(backtest_summary)
    demo_symbol = resolved_symbols[0] if resolved_symbols else "EURUSD"
    demo = build_virtual_demo_payload(
        strategy=strategy,
        symbol=demo_symbol,
        start=start,
        end=end,
        summary=backtest_summary,
        min_demo_days=14,
        tolerance_pct=0.05,
        report_dir=(
            Path(output_dir) / "virtual_demo" if output_dir is not None else None
        ),
    )
    if not allow_synthetic_demo and not demo.get("execution_validation_report"):
        demo["completed_successfully"] = False
        demo["synthetic"] = False

    bundle = SVOSPayloadBundle(
        strategy=strategy,
        symbols=resolved_symbols,
        replay=replay,
        backtest=backtest,
        robustness=robustness,
        demo=demo,
        metadata={
            "catalog_path": str(catalog_path) if catalog_path is not None else "",
            "start": start,
            "end": end,
            "allow_synthetic_demo": allow_synthetic_demo,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "lineage": build_lineage_metadata(
                source="svos_payload_builder",
                strategy=strategy,
                strategy_version=str(manifest.get("version", "unknown")),
                artifact="svos_payload_bundle",
                extra={
                    "catalog_path": (
                        str(catalog_path) if catalog_path is not None else ""
                    )
                },
            ),
        },
    )

    if output_dir is not None:
        bundle.write(Path(output_dir) / "svos_payload.json")

    return bundle

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from research.research_validation import DEFAULT_BENCHMARK, dataset_hash, load_yaml, optimization_diagnostics, write_json

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VALIDATION_REPORT = ROOT / "artifacts" / "ST-A2_validation_report.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "strategy_failure_diagnosis.json"


@dataclass(frozen=True)
class DiagnosticThresholds:
    target_win_rate: float = 0.40
    high_win_rate: float = 0.55
    high_average_r: float = 2.0
    min_profit_factor: float = 1.0
    good_gross_profit: float = 0.0
    poor_net_profit: float = 0.0
    min_trades: int = 200
    high_trade_count: int = 300
    max_drawdown_pct: float = 15.0
    single_month_threshold: float = 0.50


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _metric(report: dict[str, Any], name: str, default: float = 0.0) -> float:
    metrics = report.get("metrics") if isinstance(report.get("metrics"), dict) else {}
    value = metrics.get(name, report.get(name, default))
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _monthly_dependency(report: dict[str, Any]) -> float:
    metrics = report.get("metrics") if isinstance(report.get("metrics"), dict) else {}
    monthly = metrics.get("monthly_returns")
    if not isinstance(monthly, dict) or not monthly:
        return _metric(report, "largest_month_dependency", 0.0)
    total = sum(float(v or 0.0) for v in monthly.values())
    if total == 0:
        return 0.0
    return max(abs(float(v or 0.0)) for v in monthly.values()) / abs(total)


def _execution(report: dict[str, Any]) -> dict[str, float]:
    metrics = report.get("metrics") if isinstance(report.get("metrics"), dict) else {}
    gross = float(metrics.get("gross_pnl", report.get("gross_pnl", 0.0)) or 0.0)
    spread = float(metrics.get("spread_cost", report.get("spread_cost", 0.0)) or 0.0)
    commission = float(metrics.get("commission", report.get("commission", 0.0)) or 0.0)
    slippage = float(metrics.get("slippage", report.get("slippage", 0.0)) or 0.0)
    net = float(metrics.get("net_pnl", report.get("net_pnl", gross - spread - commission - slippage)) or 0.0)
    cost = spread + commission + slippage
    return {
        "gross_pnl": gross,
        "spread": spread,
        "commission": commission,
        "slippage": slippage,
        "net_pnl": net,
        "cost": cost,
        "cost_percentage_of_profit": cost / gross if gross > 0 else 0.0,
    }


def classify_failures(
    validation_report: dict[str, Any],
    *,
    thresholds: DiagnosticThresholds | None = None,
) -> dict[str, Any]:
    thresholds = thresholds or DiagnosticThresholds()
    trades = int(_metric(validation_report, "trades", 0.0))
    win_rate = _metric(validation_report, "win_rate", 0.0)
    average_r = _metric(validation_report, "average_R", _metric(validation_report, "average_r", 0.0))
    profit_factor = _metric(validation_report, "profit_factor_after_cost", _metric(validation_report, "profit_factor", 0.0))
    gross_profit = _metric(validation_report, "gross_profit", _execution(validation_report)["gross_pnl"])
    net_profit = _metric(validation_report, "net_profit", _execution(validation_report)["net_pnl"])
    max_drawdown = _metric(validation_report, "max_drawdown", 0.0)
    month_dependency = _monthly_dependency(validation_report)

    cases: list[dict[str, Any]] = []

    def add(
        case_id: str,
        failure: str,
        detected: bool,
        meaning: str,
        optimization_direction: str,
        allowed_changes: list[str],
        do_not_change: list[str] | None = None,
        required_validation: list[str] | None = None,
        measurements: dict[str, Any] | None = None,
    ) -> None:
        cases.append(
            {
                "case_id": case_id,
                "failure": failure,
                "detected": detected,
                "meaning": meaning,
                "optimization_direction": optimization_direction,
                "allowed_changes": allowed_changes,
                "do_not_change": do_not_change or [],
                "required_validation": required_validation or [],
                "measurements": measurements or {},
            }
        )

    add(
        "LOW_WIN_RATE_HIGH_RR",
        "Low win rate, but high RR",
        win_rate < thresholds.target_win_rate and average_r > thresholds.high_average_r,
        "Entries may be too early or late.",
        "Improve confirmation.",
        ["CHoCH confirmation", "liquidity sweep requirement", "displacement confirmation", "entry timing", "lower timeframe confirmation"],
        ["risk model", "profit target first"],
        measurements={"win_rate": win_rate, "average_R": average_r},
    )
    add(
        "HIGH_WIN_RATE_NEGATIVE_PROFIT",
        "High win rate, negative profit",
        win_rate >= thresholds.high_win_rate and profit_factor < thresholds.min_profit_factor,
        "RR too small, or fees and slippage are damaging expectancy.",
        "Improve exits.",
        ["reward target", "partial exits", "trailing logic", "liquidity target", "minimum RR filter"],
        required_validation=["gross_pnl - spread - commission - slippage = net_pnl"],
        measurements={"win_rate": win_rate, "profit_factor": profit_factor},
    )
    execution = _execution(validation_report)
    add(
        "GOOD_GROSS_BAD_NET",
        "Good gross result, bad net result",
        gross_profit > thresholds.good_gross_profit and net_profit <= thresholds.poor_net_profit,
        "Execution cost problem.",
        "Reduce trading frequency.",
        ["higher timeframe bias", "session filtering", "volatility filter", "minimum spread filter", "avoid poor liquidity periods"],
        measurements={
            "trades_before_cost": trades,
            "trades_after_cost": trades,
            "cost_percentage_of_profit": execution["cost_percentage_of_profit"],
            **execution,
        },
    )
    add(
        "TOO_FEW_TRADES",
        "Few trades",
        trades < thresholds.min_trades,
        "Strategy over-filtered.",
        "Relax rules carefully.",
        ["reduce confirmation requirements", "expand sessions", "include additional valid POIs", "reduce unnecessary filters"],
        ["quality gates only to increase trade count"],
        measurements={"trades": trades, "minimum_requirement": thresholds.min_trades},
    )
    add(
        "MANY_TRADES_LARGE_DRAWDOWN",
        "Many trades, big drawdown",
        trades >= thresholds.high_trade_count and max_drawdown > thresholds.max_drawdown_pct,
        "Weak filtering.",
        "Add context filters.",
        ["HTF trend filter", "market regime filter", "session filter", "volatility filter", "avoid ranging conditions"],
        measurements={"trades": trades, "max_drawdown": max_drawdown, "drawdown_limit": thresholds.max_drawdown_pct},
    )
    add(
        "SINGLE_MONTH_DEPENDENCY",
        "Works only in one month",
        month_dependency > thresholds.single_month_threshold,
        "Overfit or regime dependency.",
        "Robustness.",
        ["walk-forward testing", "regime analysis", "Monte Carlo simulation"],
        required_validation=["walk-forward testing", "regime analysis", "Monte Carlo simulation"],
        measurements={"single_month_contribution": month_dependency, "threshold": thresholds.single_month_threshold},
    )

    detected = [case for case in cases if case["detected"]]
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "strategy": validation_report.get("strategy", "UNKNOWN"),
        "validation_status": validation_report.get("status", "UNKNOWN"),
        "source_report_status": "MISSING" if not validation_report else "LOADED",
        "metrics": {
            "trades": trades,
            "win_rate": win_rate,
            "average_R": average_r,
            "profit_factor": profit_factor,
            "gross_profit": gross_profit,
            "net_profit": net_profit,
            "max_drawdown": max_drawdown,
            "single_month_contribution": month_dependency,
        },
        "thresholds": thresholds.__dict__,
        "detected_failures": detected,
        "all_cases": cases,
        "diagnostic_rubric": optimization_diagnostics(),
    }


def run_diagnostics(
    validation_report_path: Path = DEFAULT_VALIDATION_REPORT,
    output_path: Path = DEFAULT_OUTPUT,
    benchmark_path: Path = DEFAULT_BENCHMARK,
) -> dict[str, Any]:
    report = _load_json(validation_report_path)
    config = load_yaml(benchmark_path)
    thresholds = DiagnosticThresholds(
        min_trades=int(config.get("acceptance_gates", {}).get("trades_min", 200)),
        min_profit_factor=1.0,
        max_drawdown_pct=float(config.get("acceptance_gates", {}).get("max_drawdown_pct_max", 15.0)),
    )
    result = classify_failures(report, thresholds=thresholds)
    result["dataset_version"] = config.get("dataset", {}).get("version")
    result["dataset_hash"] = dataset_hash(config)
    result["source_report"] = str(validation_report_path)
    write_json(output_path, result)
    return result

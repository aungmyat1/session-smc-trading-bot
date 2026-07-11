from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Any

from research.research_validation import dataset_hash, load_yaml, write_json
from research.st_a2_freeze import LEDGER_DIR, load_ledgers

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
BENCHMARK_CONFIG = ROOT / "config" / "research_benchmark.yaml"

TARGETS = {
    "trade_count": 200,
    "profit_factor": 1.25,
    "sharpe": 1.20,
    "max_drawdown": 15.0,
    "expectancy": 0.0,
}


def _created_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_time(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _month(row: dict[str, Any]) -> str:
    return str(row.get("entry_time") or "")[:7] or "UNKNOWN"


def _duration_hours(row: dict[str, Any]) -> float:
    start = _parse_time(row.get("entry_time"))
    end = _parse_time(row.get("exit_time"))
    if not start or not end:
        return 0.0
    return max(0.0, (end - start).total_seconds() / 3600.0)


def _pf(values: list[float]) -> float:
    wins = sum(value for value in values if value > 0)
    losses = abs(sum(value for value in values if value < 0))
    if losses == 0:
        return float("inf") if wins > 0 else 0.0
    return wins / losses


def _drawdown(values: list[float]) -> float:
    running = peak = worst = 0.0
    for value in values:
        running += value
        peak = max(peak, running)
        worst = max(worst, peak - running)
    return worst


def _sharpe(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    sd = pstdev(values)
    return mean(values) / sd * math.sqrt(len(values)) if sd else 0.0


def _sortino(values: list[float]) -> float:
    downside = [value for value in values if value < 0]
    if not values or not downside:
        return 0.0
    sd = pstdev(downside) if len(downside) > 1 else abs(downside[0])
    return mean(values) / sd * math.sqrt(len(values)) if sd else 0.0


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    net = [float(row.get("net_pnl", 0.0) or 0.0) for row in rows]
    gross = [float(row.get("gross_pnl", 0.0) or 0.0) for row in rows]
    wins = [value for value in net if value > 0]
    costs = [
        float(row.get("spread_cost", 0.0) or 0.0)
        + float(row.get("commission_cost", row.get("commission", 0.0)) or 0.0)
        + float(row.get("slippage_cost", row.get("slippage", 0.0)) or 0.0)
        for row in rows
    ]
    return {
        "trades": len(rows),
        "trade_count": len(rows),
        "gross_profit": sum(gross),
        "net_profit": sum(net),
        "profit_factor": _pf(net),
        "profit_factor_after_cost": _pf(net),
        "gross_profit_factor": _pf(gross),
        "expectancy": mean(net) if net else 0.0,
        "average_R": mean(net) if net else 0.0,
        "win_rate": len(wins) / len(net) if net else 0.0,
        "sharpe": _sharpe(net),
        "sortino": _sortino(net),
        "drawdown": _drawdown(net),
        "max_drawdown": _drawdown(net),
        "spread_cost": sum(float(row.get("spread_cost", 0.0) or 0.0) for row in rows),
        "commission_cost": sum(float(row.get("commission_cost", row.get("commission", 0.0)) or 0.0) for row in rows),
        "slippage_cost": sum(float(row.get("slippage_cost", row.get("slippage", 0.0)) or 0.0) for row in rows),
        "cost": sum(costs),
        "cost_ratio": sum(costs) / abs(sum(gross)) if sum(gross) else 0.0,
        "cost_per_trade": sum(costs) / len(rows) if rows else 0.0,
    }


def _group(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        buckets.setdefault(str(row.get(key) or "UNKNOWN"), []).append(row)
    return buckets


def _edge_score(metrics: dict[str, Any]) -> float:
    pf = float(metrics.get("profit_factor", 0.0) or 0.0)
    exp = float(metrics.get("expectancy", 0.0) or 0.0)
    sharpe = float(metrics.get("sharpe", 0.0) or 0.0)
    dd = float(metrics.get("drawdown", 0.0) or 0.0)
    pf_score = min(2.0, pf) / 2.0
    exp_score = max(-1.0, min(1.0, exp)) * 0.4
    sharpe_score = max(-1.0, min(1.0, sharpe / 1.2)) * 0.3
    dd_penalty = min(0.4, dd / 40.0)
    return round(pf_score + exp_score + sharpe_score - dd_penalty, 4)


def _ranked_attribution(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    grouped = _group(rows, key)
    metrics_by_name = {}
    for name, bucket in sorted(grouped.items()):
        metrics = _metrics(bucket)
        metrics["edge_score"] = _edge_score(metrics)
        metrics_by_name[name] = metrics
    if not metrics_by_name:
        return {"items": {}, "rankings": {}}
    ranked = sorted(metrics_by_name.items(), key=lambda item: (item[1]["edge_score"], item[1]["net_profit"]), reverse=True)
    neutral = min(metrics_by_name.items(), key=lambda item: abs(float(item[1]["net_profit"])))
    return {
        "items": metrics_by_name,
        "rankings": {
            "best": ranked[0][0],
            "worst": ranked[-1][0],
            "neutral": neutral[0],
        },
    }


def failure_breakdown(rows: list[dict[str, Any]], validation_report: dict[str, Any] | None = None) -> dict[str, Any]:
    metrics = _metrics(rows)
    monthly_buckets: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        monthly_buckets.setdefault(_month(row), []).append(row)
    monthly_profit_factor = {month: _metrics(bucket)["profit_factor"] for month, bucket in sorted(monthly_buckets.items())}
    monthly_drawdown = {month: _metrics(bucket)["drawdown"] for month, bucket in sorted(monthly_buckets.items())}
    monthly_returns = {month: _metrics(bucket)["net_profit"] for month, bucket in sorted(monthly_buckets.items())}

    actual = {
        "trade_count": metrics["trade_count"],
        "profit_factor": metrics["profit_factor_after_cost"],
        "sharpe": metrics["sharpe"],
        "max_drawdown": metrics["max_drawdown"],
        "expectancy": metrics["expectancy"],
    }
    gaps = {
        "trade_count": TARGETS["trade_count"] - actual["trade_count"],
        "profit_factor": TARGETS["profit_factor"] - actual["profit_factor"],
        "sharpe": TARGETS["sharpe"] - actual["sharpe"],
        "max_drawdown": actual["max_drawdown"] - TARGETS["max_drawdown"],
        "expectancy": TARGETS["expectancy"] - actual["expectancy"],
    }
    severity = {
        "trade_count": max(0.0, gaps["trade_count"] / TARGETS["trade_count"]),
        "profit_factor": max(0.0, gaps["profit_factor"] / TARGETS["profit_factor"]),
        "sharpe": max(0.0, gaps["sharpe"] / TARGETS["sharpe"]),
        "max_drawdown": max(0.0, gaps["max_drawdown"] / TARGETS["max_drawdown"]),
        "expectancy": max(0.0, abs(gaps["expectancy"])) if actual["expectancy"] < 0 else 0.0,
    }
    failed = [name for name, value in severity.items() if value > 0]
    primary = [name for name in failed if severity[name] >= 0.15]
    secondary = [name for name in failed if name not in primary]
    recommendation = "Run attribution and generate one-change hypotheses before any optimization."
    if "sharpe" in primary or "profit_factor" in primary:
        recommendation = "Prioritize edge decomposition by symbol, regime, session, and execution cost."

    return {
        "created_at": _created_at(),
        "performance": {
            "trade_count": metrics["trade_count"],
            "win_rate": metrics["win_rate"],
            "profit_factor": metrics["profit_factor"],
            "profit_factor_after_cost": metrics["profit_factor_after_cost"],
            "expectancy": metrics["expectancy"],
            "average_R": metrics["average_R"],
        },
        "risk": {
            "max_drawdown": metrics["max_drawdown"],
            "sharpe": metrics["sharpe"],
            "sortino": metrics["sortino"],
        },
        "stability": {
            "monthly_returns": monthly_returns,
            "monthly_profit_factor": monthly_profit_factor,
            "monthly_drawdown": monthly_drawdown,
        },
        "gap_analysis": {
            "actual": actual,
            "target": TARGETS,
            "gaps": gaps,
            "primary_failures": primary,
            "secondary_failures": secondary,
            "severity_score": severity,
            "recommendation": recommendation,
        },
    }


def symbol_attribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    attribution = _ranked_attribution(rows, "symbol")
    items = attribution["items"]
    return {
        "created_at": _created_at(),
        "symbols": items,
        "questions": {
            "profit_contributors": [name for name, m in items.items() if m["net_profit"] > 0],
            "performance_destroyers": [name for name, m in items.items() if m["net_profit"] < 0],
            "insufficient_sample": [name for name, m in items.items() if m["trades"] < 50],
        },
        "rankings": {
            "best_symbol": attribution["rankings"].get("best"),
            "worst_symbol": attribution["rankings"].get("worst"),
            "neutral_symbol": attribution["rankings"].get("neutral"),
        },
    }


def regime_attribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    attribution = _ranked_attribution(rows, "market_regime")
    items = attribution["items"]
    expected = ["TREND_HIGH_VOL", "TREND_LOW_VOL", "RANGE_HIGH_VOL", "RANGE_LOW_VOL"]
    for regime in expected:
        items.setdefault(regime, {**_metrics([]), "edge_score": 0.0})
    return {
        "created_at": _created_at(),
        "regimes": dict(sorted(items.items())),
        "edge_regimes": [name for name, m in items.items() if m["trades"] > 0 and m["expectancy"] > 0 and m["profit_factor"] > 1.0],
        "destructive_regimes": [name for name, m in items.items() if m["trades"] > 0 and (m["expectancy"] < 0 or m["profit_factor"] < 1.0)],
        "rankings": attribution["rankings"],
    }


def _session_name(raw: str) -> str:
    value = str(raw or "UNKNOWN").lower()
    if value == "new_york":
        return "NewYork"
    if value == "newyork":
        return "NewYork"
    if value == "london":
        return "London"
    if value == "asian":
        return "Asian"
    if value == "overlap":
        return "Overlap"
    return raw or "UNKNOWN"


def session_attribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = [{**row, "session_norm": _session_name(str(row.get("session", "")))} for row in rows]
    attribution = _ranked_attribution(normalized, "session_norm")
    items = attribution["items"]
    for session in ["Asian", "London", "NewYork", "Overlap"]:
        items.setdefault(session, _metrics([]))
    return {
        "created_at": _created_at(),
        "sessions": dict(sorted(items.items())),
        "best_session": attribution["rankings"].get("best"),
        "worst_session": attribution["rankings"].get("worst"),
    }


def _concentration(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[str(row.get(key) or "UNKNOWN")] = counts.get(str(row.get(key) or "UNKNOWN"), 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def trade_quality(rows: list[dict[str, Any]]) -> dict[str, Any]:
    winners = [row for row in rows if float(row.get("net_pnl", 0.0) or 0.0) > 0]
    losers = [row for row in rows if float(row.get("net_pnl", 0.0) or 0.0) < 0]

    def quality(bucket: list[dict[str, Any]]) -> dict[str, Any]:
        pnl = [float(row.get("net_pnl", 0.0) or 0.0) for row in bucket]
        holds = [_duration_hours(row) for row in bucket]
        return {
            "count": len(bucket),
            "average": mean(pnl) if pnl else 0.0,
            "median": median(pnl) if pnl else 0.0,
            "average_holding_hours": mean(holds) if holds else 0.0,
            "median_holding_hours": median(holds) if holds else 0.0,
            "session": _concentration(bucket, "session"),
            "regime": _concentration(bucket, "market_regime"),
            "symbol": _concentration(bucket, "symbol"),
        }

    loser_symbol_counts = _concentration(losers, "symbol")
    winner_symbol_counts = _concentration(winners, "symbol")
    total_cost = sum(
        float(row.get("spread_cost", 0.0) or 0.0)
        + float(row.get("commission_cost", row.get("commission", 0.0)) or 0.0)
        + float(row.get("slippage_cost", row.get("slippage", 0.0)) or 0.0)
        for row in rows
    )
    gross = sum(float(row.get("gross_pnl", 0.0) or 0.0) for row in rows)
    return {
        "created_at": _created_at(),
        "winners": quality(winners),
        "losers": quality(losers),
        "questions": {
            "losers_concentrated": bool(loser_symbol_counts) and next(iter(loser_symbol_counts.values())) / max(1, len(losers)) >= 0.4,
            "winners_clustered": bool(winner_symbol_counts) and next(iter(winner_symbol_counts.values())) / max(1, len(winners)) >= 0.4,
            "execution_cost_too_high": total_cost / abs(gross) > 0.5 if gross else False,
        },
    }


def cost_attribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = _metrics(rows)

    def cost_group(key: str) -> dict[str, Any]:
        out = {}
        for name, bucket in sorted(_group(rows, key).items()):
            out[name] = {
                "trades": len(bucket),
                "spread_cost": sum(float(row.get("spread_cost", 0.0) or 0.0) for row in bucket),
                "commission_cost": sum(float(row.get("commission_cost", row.get("commission", 0.0)) or 0.0) for row in bucket),
                "slippage_cost": sum(float(row.get("slippage_cost", row.get("slippage", 0.0)) or 0.0) for row in bucket),
                "cost_ratio": _metrics(bucket)["cost_ratio"],
                "cost_per_trade": _metrics(bucket)["cost_per_trade"],
            }
        return out

    is_cost_problem = metrics["gross_profit"] > 0 and metrics["net_profit"] < 0
    return {
        "created_at": _created_at(),
        "gross_profit": metrics["gross_profit"],
        "spread_cost": metrics["spread_cost"],
        "commission_cost": metrics["commission_cost"],
        "slippage_cost": metrics["slippage_cost"],
        "net_profit": metrics["net_profit"],
        "cost_ratio": metrics["cost_ratio"],
        "cost_per_trade": metrics["cost_per_trade"],
        "cost_by_symbol": cost_group("symbol"),
        "cost_by_session": cost_group("session"),
        "is_cost_problem": is_cost_problem,
    }


def root_causes(
    breakdown: dict[str, Any],
    symbols: dict[str, Any],
    regimes: dict[str, Any],
    sessions: dict[str, Any],
    costs: dict[str, Any],
) -> dict[str, Any]:
    causes: list[dict[str, Any]] = []

    def add(cause: str, evidence: list[str], confidence: float) -> None:
        causes.append({"cause": cause, "evidence": evidence, "confidence": round(max(0.0, min(1.0, confidence)), 4)})

    perf = breakdown["performance"]
    risk = breakdown["risk"]
    gap = breakdown["gap_analysis"]
    if perf["profit_factor_after_cost"] < 1.0 or perf["expectancy"] <= 0:
        add("LOW_EDGE", [f"PF_after_cost={perf['profit_factor_after_cost']:.4f}", f"expectancy={perf['expectancy']:.4f}"], 0.8)
    if perf["trade_count"] < TARGETS["trade_count"]:
        add("LOW_SAMPLE_SIZE", [f"trades={perf['trade_count']} < {TARGETS['trade_count']}"], 0.65)
    if costs["is_cost_problem"]:
        add("COST_PROBLEM", [f"gross_profit={costs['gross_profit']:.4f}", f"net_profit={costs['net_profit']:.4f}", f"cost_ratio={costs['cost_ratio']:.4f}"], 0.85)
    destructive_regimes = regimes.get("destructive_regimes", [])
    if destructive_regimes:
        add("REGIME_DEPENDENCY", [f"destructive_regimes={', '.join(destructive_regimes)}"], min(0.9, 0.45 + 0.1 * len(destructive_regimes)))
    worst_session = sessions.get("worst_session")
    best_session = sessions.get("best_session")
    if worst_session and best_session and worst_session != best_session:
        add("SESSION_DEPENDENCY", [f"best_session={best_session}", f"worst_session={worst_session}"], 0.65)
    worst_symbol = symbols.get("rankings", {}).get("worst_symbol")
    best_symbol = symbols.get("rankings", {}).get("best_symbol")
    if worst_symbol and best_symbol and worst_symbol != best_symbol:
        add("SYMBOL_DEPENDENCY", [f"best_symbol={best_symbol}", f"worst_symbol={worst_symbol}"], 0.75)
    if perf["win_rate"] < 0.35 and perf["average_R"] < 0:
        add("ENTRY_TIMING_PROBLEM", [f"win_rate={perf['win_rate']:.4f}", f"average_R={perf['average_R']:.4f}"], 0.55)
    if risk["max_drawdown"] >= TARGETS["max_drawdown"]:
        add("WEAK_FILTERS", [f"max_drawdown={risk['max_drawdown']:.4f} >= {TARGETS['max_drawdown']}"], 0.55)
    if perf["win_rate"] > 0.45 and perf["profit_factor_after_cost"] < 1.0:
        add("EXIT_PROBLEM", [f"win_rate={perf['win_rate']:.4f}", f"PF={perf['profit_factor_after_cost']:.4f}"], 0.5)

    return {
        "created_at": _created_at(),
        "allowed_root_causes": [
            "LOW_EDGE",
            "LOW_SAMPLE_SIZE",
            "COST_PROBLEM",
            "WEAK_FILTERS",
            "REGIME_DEPENDENCY",
            "SESSION_DEPENDENCY",
            "SYMBOL_DEPENDENCY",
            "ENTRY_TIMING_PROBLEM",
            "EXIT_PROBLEM",
        ],
        "root_causes": sorted(causes, key=lambda item: item["confidence"], reverse=True),
        "gap_primary_failures": gap.get("primary_failures", []),
    }


def hypotheses(root_cause_report: dict[str, Any], regimes: dict[str, Any], sessions: dict[str, Any], symbols: dict[str, Any], costs: dict[str, Any]) -> dict[str, Any]:
    out: list[dict[str, Any]] = []

    def add(cause: str, evidence: list[str], hypothesis: str, single_change: str, confidence: float, risk: str) -> None:
        out.append(
            {
                "cause": cause,
                "evidence": evidence,
                "hypothesis": hypothesis,
                "single_change": single_change,
                "confidence": round(confidence, 4),
                "risk": risk,
            }
        )

    cause_map = {item["cause"]: item for item in root_cause_report.get("root_causes", [])}
    destructive_regimes = regimes.get("destructive_regimes", [])
    if "REGIME_DEPENDENCY" in cause_map and destructive_regimes:
        worst = min(
            destructive_regimes,
            key=lambda name: regimes["regimes"].get(name, {}).get("edge_score", 0.0),
        )
        metrics = regimes["regimes"].get(worst, {})
        add(
            "REGIME_DEPENDENCY",
            [f"{worst} PF={metrics.get('profit_factor', 0.0):.4f}", f"expectancy={metrics.get('expectancy', 0.0):.4f}"],
            f"Disable {worst} trades.",
            f"Add filter excluding {worst}",
            cause_map["REGIME_DEPENDENCY"]["confidence"],
            "May overfit to observed regime labels; requires walk-forward validation.",
        )
    if "SESSION_DEPENDENCY" in cause_map:
        best = sessions.get("best_session")
        worst = sessions.get("worst_session")
        if best and worst:
            add(
                "SESSION_DEPENDENCY",
                [f"best_session={best}", f"worst_session={worst}"],
                f"Trade only {best} session or disable {worst}.",
                f"Session filter: {best} only",
                cause_map["SESSION_DEPENDENCY"]["confidence"],
                "May reduce sample size below validation gate.",
            )
    if "SYMBOL_DEPENDENCY" in cause_map:
        worst_symbol = symbols.get("rankings", {}).get("worst_symbol")
        best_symbol = symbols.get("rankings", {}).get("best_symbol")
        add(
            "SYMBOL_DEPENDENCY",
            [f"best_symbol={best_symbol}", f"worst_symbol={worst_symbol}"],
            f"Disable {worst_symbol} or require stronger confirmation for {worst_symbol}.",
            f"Symbol filter: exclude {worst_symbol}",
            cause_map["SYMBOL_DEPENDENCY"]["confidence"],
            "Symbol exclusion can overfit and reduce diversification.",
        )
    if "COST_PROBLEM" in cause_map:
        add(
            "COST_PROBLEM",
            [f"cost_ratio={costs.get('cost_ratio', 0.0):.4f}", f"net_profit={costs.get('net_profit', 0.0):.4f}"],
            "Reduce low-quality trades where costs consume gross edge.",
            "Minimum spread/cost threshold",
            cause_map["COST_PROBLEM"]["confidence"],
            "Can remove winners and lower sample count.",
        )
    if "ENTRY_TIMING_PROBLEM" in cause_map:
        add(
            "ENTRY_TIMING_PROBLEM",
            cause_map["ENTRY_TIMING_PROBLEM"]["evidence"],
            "Require stronger displacement or lower timeframe confirmation before entry.",
            "Entry confirmation filter",
            cause_map["ENTRY_TIMING_PROBLEM"]["confidence"],
            "Confirmation delay can worsen entries.",
        )
    if "WEAK_FILTERS" in cause_map:
        add(
            "WEAK_FILTERS",
            cause_map["WEAK_FILTERS"]["evidence"],
            "Add one context filter to reduce drawdown clusters.",
            "HTF trend or regime filter",
            cause_map["WEAK_FILTERS"]["confidence"],
            "Additional filters may over-filter.",
        )
    return {"created_at": _created_at(), "hypotheses": out[:5]}


def experiment_plan(hypothesis_report: dict[str, Any]) -> dict[str, Any]:
    experiments = []
    for idx, item in enumerate(hypothesis_report.get("hypotheses", [])[:5], start=1):
        experiments.append(
            {
                "experiment_id": f"STA2-HYP-{idx:03d}",
                "strategy_version": f"ST-A2_v1.{idx}",
                "single_change": item["single_change"],
                "reason": "; ".join(item["evidence"]),
                "expected_improvement": item["hypothesis"],
                "risk": item["risk"],
                "cause": item["cause"],
                "confidence": item["confidence"],
            }
        )
    return {"created_at": _created_at(), "experiments": experiments}


def experiment_priority(plan: dict[str, Any], csv_path: Path) -> list[dict[str, Any]]:
    rows = []
    for item in plan.get("experiments", []):
        confidence = float(item.get("confidence", 0.0) or 0.0)
        impact = {
            "COST_PROBLEM": 0.85,
            "SYMBOL_DEPENDENCY": 0.80,
            "REGIME_DEPENDENCY": 0.75,
            "SESSION_DEPENDENCY": 0.65,
            "WEAK_FILTERS": 0.60,
            "ENTRY_TIMING_PROBLEM": 0.55,
        }.get(str(item.get("cause")), 0.5)
        overfit = {
            "SYMBOL_DEPENDENCY": 0.75,
            "SESSION_DEPENDENCY": 0.70,
            "REGIME_DEPENDENCY": 0.65,
            "COST_PROBLEM": 0.45,
            "WEAK_FILTERS": 0.55,
            "ENTRY_TIMING_PROBLEM": 0.60,
        }.get(str(item.get("cause")), 0.5)
        priority = round((impact * 0.45) + (confidence * 0.4) - (overfit * 0.15), 4)
        rows.append(
            {
                "experiment_id": item["experiment_id"],
                "hypothesis": item["expected_improvement"],
                "impact_score": round(impact, 4),
                "confidence_score": round(confidence, 4),
                "overfit_risk": round(overfit, 4),
                "priority": priority,
            }
        )
    rows.sort(key=lambda row: row["priority"], reverse=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["experiment_id", "hypothesis", "impact_score", "confidence_score", "overfit_risk", "priority"])
        writer.writeheader()
        writer.writerows(rows)
    return rows


def run_failure_decomposition(ledger_dir: Path = LEDGER_DIR, artifact_dir: Path = ARTIFACTS) -> dict[str, Any]:
    rows = load_ledgers(ledger_dir)
    benchmark = load_yaml(BENCHMARK_CONFIG)
    metadata = {
        "dataset_version": benchmark["dataset"]["version"],
        "dataset_hash": dataset_hash(benchmark),
        "trade_count": len(rows),
    }
    breakdown = {**metadata, **failure_breakdown(rows)}
    symbols = {**metadata, **symbol_attribution(rows)}
    regimes = {**metadata, **regime_attribution(rows)}
    sessions = {**metadata, **session_attribution(rows)}
    quality = {**metadata, **trade_quality(rows)}
    costs = {**metadata, **cost_attribution(rows)}
    causes = {**metadata, **root_causes(breakdown, symbols, regimes, sessions, costs)}
    hyp = {**metadata, **hypotheses(causes, regimes, sessions, symbols, costs)}
    plan = {**metadata, **experiment_plan(hyp)}

    outputs = {
        "failure_breakdown": artifact_dir / "ST-A2_failure_breakdown.json",
        "symbol_attribution": artifact_dir / "ST-A2_symbol_attribution.json",
        "regime_attribution": artifact_dir / "ST-A2_regime_attribution.json",
        "session_attribution": artifact_dir / "ST-A2_session_attribution.json",
        "trade_quality": artifact_dir / "ST-A2_trade_quality_report.json",
        "cost_attribution": artifact_dir / "ST-A2_cost_attribution.json",
        "root_causes": artifact_dir / "ST-A2_root_causes.json",
        "hypotheses": artifact_dir / "ST-A2_optimization_hypotheses.json",
        "experiment_plan": artifact_dir / "ST-A2_experiment_plan.json",
        "experiment_priority": artifact_dir / "ST-A2_experiment_priority.csv",
    }
    write_json(outputs["failure_breakdown"], breakdown)
    write_json(outputs["symbol_attribution"], symbols)
    write_json(outputs["regime_attribution"], regimes)
    write_json(outputs["session_attribution"], sessions)
    write_json(outputs["trade_quality"], quality)
    write_json(outputs["cost_attribution"], costs)
    write_json(outputs["root_causes"], causes)
    write_json(outputs["hypotheses"], hyp)
    write_json(outputs["experiment_plan"], plan)
    priority_rows = experiment_priority(plan, outputs["experiment_priority"])

    return {
        "trade_count": len(rows),
        "outputs": {name: str(path) for name, path in outputs.items()},
        "root_causes": [item["cause"] for item in causes["root_causes"]],
        "hypothesis_count": len(hyp["hypotheses"]),
        "experiment_count": len(plan["experiments"]),
        "priority_count": len(priority_rows),
    }

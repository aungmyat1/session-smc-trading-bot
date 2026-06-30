from __future__ import annotations

from datetime import datetime
from random import Random
from statistics import mean, median
from typing import Any, Iterable


def _trade_rows(
    trades: Iterable[dict[str, Any]], r_key: str = "std_net_r"
) -> list[dict[str, Any]]:
    rows = []
    for trade in trades:
        if not isinstance(trade, dict):
            continue
        if r_key not in trade:
            continue
        rows.append(trade)
    rows.sort(key=lambda row: str(row.get("entry_time") or row.get("timestamp") or ""))
    return rows


def _equity_path(rs: list[float]) -> list[float]:
    equity = 0.0
    path: list[float] = []
    for value in rs:
        equity += value
        path.append(equity)
    return path


def _max_drawdown(path: list[float]) -> float:
    peak = float("-inf")
    worst = 0.0
    for equity in path:
        peak = max(peak, equity)
        worst = max(worst, peak - equity)
    return worst


def walk_forward_analysis(
    trades: Iterable[dict[str, Any]],
    *,
    folds: int = 4,
    r_key: str = "std_net_r",
) -> dict[str, Any]:
    rows = _trade_rows(trades, r_key=r_key)
    rs = [float(row[r_key]) for row in rows]
    if len(rs) < max(8, folds * 2):
        return {
            "passed": False,
            "reason": "insufficient_data",
            "folds": [],
            "trade_count": len(rs),
        }

    chunk = max(1, len(rs) // folds)
    fold_rows: list[dict[str, Any]] = []
    passed = True
    for idx in range(folds):
        test_start = idx * chunk
        test_end = len(rs) if idx == folds - 1 else min(len(rs), (idx + 1) * chunk)
        test = rs[test_start:test_end]
        train = rs[:test_start] + rs[test_end:]
        if not test or not train:
            continue

        def _pf(values: list[float]) -> float:
            wins = sum(v for v in values if v > 0)
            losses = abs(sum(v for v in values if v <= 0))
            return wins / losses if losses else (wins if wins > 0 else 0.0)

        test_pf = _pf(test)
        train_pf = _pf(train)
        fold_passed = test_pf >= 1.0
        passed = passed and fold_passed
        fold_rows.append(
            {
                "fold": idx + 1,
                "train_count": len(train),
                "test_count": len(test),
                "train_pf": round(train_pf, 4),
                "test_pf": round(test_pf, 4),
                "train_net_r": round(sum(train), 4),
                "test_net_r": round(sum(test), 4),
                "passed": fold_passed,
            }
        )

    return {
        "passed": passed and bool(fold_rows),
        "reason": "" if passed and fold_rows else "fold_failure",
        "folds": fold_rows,
        "trade_count": len(rs),
        "overall_net_r": round(sum(rs), 4),
    }


def monte_carlo_resampling(
    trades: Iterable[dict[str, Any]],
    *,
    iterations: int = 500,
    seed: int = 42,
    r_key: str = "std_net_r",
) -> dict[str, Any]:
    rows = _trade_rows(trades, r_key=r_key)
    rs = [float(row[r_key]) for row in rows]
    if len(rs) < 5:
        return {
            "passed": False,
            "reason": "insufficient_data",
            "iterations": 0,
            "sample_count": len(rs),
        }

    rng = Random(seed)
    pfs: list[float] = []
    max_dds: list[float] = []
    net_rs: list[float] = []
    for _ in range(iterations):
        sample = [rs[rng.randrange(len(rs))] for _ in range(len(rs))]
        wins = sum(v for v in sample if v > 0)
        losses = abs(sum(v for v in sample if v <= 0))
        pf = wins / losses if losses else (wins if wins > 0 else 0.0)
        pfs.append(pf)
        path = _equity_path(sample)
        max_dds.append(_max_drawdown(path))
        net_rs.append(sum(sample))

    pf_median = median(pfs)
    dd_p95 = sorted(max_dds)[int(round((len(max_dds) - 1) * 0.95))]
    net_r_median = median(net_rs)
    passed = pf_median >= 1.0 and net_r_median > 0
    return {
        "passed": passed,
        "iterations": iterations,
        "sample_count": len(rs),
        "profit_factor_median": round(pf_median, 4),
        "profit_factor_mean": round(mean(pfs), 4),
        "net_r_median": round(net_r_median, 4),
        "max_drawdown_p95": round(dd_p95, 4),
    }


def parameter_sensitivity(
    rr_results: dict[str, Any],
) -> dict[str, Any]:
    if not rr_results:
        return {"passed": False, "reason": "no_rr_results", "rr_results": {}}

    normalized: list[tuple[float, dict[str, Any]]] = []
    for rr_key, result in rr_results.items():
        try:
            rr = float(rr_key)
        except (TypeError, ValueError):
            continue
        metrics = result.get("std_metrics") if isinstance(result, dict) else None
        if not isinstance(metrics, dict):
            continue
        normalized.append((rr, metrics))

    if len(normalized) < 2:
        return {
            "passed": False,
            "reason": "insufficient_rr_variants",
            "rr_results": rr_results,
        }

    normalized.sort(key=lambda item: item[0])
    best_rr, best_metrics = max(
        normalized, key=lambda item: float(item[1].get("net_pf", 0.0) or 0.0)
    )
    best_pf = float(best_metrics.get("net_pf", 0.0) or 0.0)
    runner_up_pf = max(
        float(metrics.get("net_pf", 0.0) or 0.0)
        for rr, metrics in normalized
        if rr != best_rr
    )
    spread = best_pf - runner_up_pf
    neighboring = [
        float(metrics.get("net_pf", 0.0) or 0.0)
        for rr, metrics in normalized
        if abs(rr - best_rr) <= 1.0 and rr != best_rr
    ]
    neighborhood_pf = median(neighboring) if neighboring else runner_up_pf
    passed = (
        best_pf >= 1.0
        and spread <= max(0.35, best_pf * 0.25)
        and neighborhood_pf >= 0.85
    )
    return {
        "passed": passed,
        "best_rr": best_rr,
        "best_profit_factor": round(best_pf, 4),
        "runner_up_profit_factor": round(runner_up_pf, 4),
        "profit_factor_spread": round(spread, 4),
        "neighbor_profit_factor_median": round(neighborhood_pf, 4),
        "rr_results": rr_results,
    }


def regime_analysis(
    trades: Iterable[dict[str, Any]],
    *,
    r_key: str = "std_net_r",
) -> dict[str, Any]:
    rows = _trade_rows(trades, r_key=r_key)
    if not rows:
        return {"passed": False, "reason": "no_trades", "regimes": []}

    regime_key = "regime" if any("regime" in row for row in rows) else None
    buckets: dict[str, list[float]] = {}
    for row in rows:
        if regime_key and row.get("regime"):
            bucket = str(row.get("regime"))
        elif row.get("session"):
            bucket = f"session:{str(row.get('session'))}"
        else:
            timestamp = row.get("entry_time") or row.get("timestamp")
            try:
                bucket = f"year:{datetime.fromisoformat(str(timestamp).replace('Z', '+00:00')).year}"
            except Exception:
                bucket = "unknown"
        buckets.setdefault(bucket, []).append(float(row[r_key]))

    regime_rows: list[dict[str, Any]] = []
    passed = True
    for bucket, values in sorted(buckets.items()):
        wins = sum(v for v in values if v > 0)
        losses = abs(sum(v for v in values if v <= 0))
        pf = wins / losses if losses else (wins if wins > 0 else 0.0)
        bucket_passed = pf >= 1.0
        passed = passed and bucket_passed
        regime_rows.append(
            {
                "regime": bucket,
                "trade_count": len(values),
                "profit_factor": round(pf, 4),
                "net_r": round(sum(values), 4),
                "passed": bucket_passed,
            }
        )

    return {
        "passed": passed,
        "reason": "" if passed else "regime_underperformance",
        "regimes": regime_rows,
    }

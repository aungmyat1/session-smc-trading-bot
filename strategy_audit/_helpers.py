from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any, Iterable


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _numbers(values: Iterable[Any]) -> list[float]:
    out: list[float] = []
    for value in values:
        try:
            out.append(float(value))
        except (TypeError, ValueError):
            continue
    return out


def _profit_factor(returns: list[float]) -> float:
    wins = sum(v for v in returns if v > 0)
    losses = abs(sum(v for v in returns if v <= 0))
    if losses == 0:
        return wins if wins > 0 else 0.0
    return wins / losses


def _expectancy(returns: list[float]) -> float:
    return mean(returns) if returns else 0.0


def _sharpe(returns: list[float]) -> float:
    if len(returns) < 2:
        return 0.0
    sd = pstdev(returns)
    if sd == 0:
        return 0.0
    return mean(returns) / sd


def _sortino(returns: list[float]) -> float:
    downside = [min(0.0, v) for v in returns]
    downside_dev = pstdev(downside) if len(downside) > 1 else 0.0
    if downside_dev == 0:
        return 0.0
    return mean(returns) / downside_dev


def _max_drawdown(returns: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    worst = 0.0
    for value in returns:
        equity += value
        peak = max(peak, equity)
        worst = max(worst, peak - equity)
    return worst


def _round(value: float | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def _status(score: float, *, verified: bool = True) -> str:
    if not verified:
        return "NOT_VERIFIED"
    if score >= 80:
        return "PASS"
    if score >= 50:
        return "PARTIAL"
    return "FAIL"


def _score_from_ratio(ratio: float | None, threshold: float = 1.0) -> float:
    if ratio is None or math.isnan(ratio):
        return 0.0
    if ratio <= 0:
        return 0.0
    if ratio >= threshold:
        return min(100.0, 60.0 + (ratio - threshold) * 20.0)
    return max(0.0, 60.0 * (ratio / threshold))


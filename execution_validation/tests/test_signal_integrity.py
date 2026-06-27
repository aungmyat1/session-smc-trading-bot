from __future__ import annotations

__test__ = False

from dataclasses import asdict
from typing import Any

from execution_validation.common import CheckResult


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def assess_signal_integrity(signals: list[Any], orders: list[Any]) -> CheckResult:
    expected = len(signals)
    executed = len(orders)
    matched = 0
    mismatches: list[str] = []
    order_by_signal = {
        str(_get(order, "signal_id", _get(order, "order_id", _get(order, "id", "")))): order
        for order in orders
    }

    for signal in signals:
        signal_id = str(_get(signal, "signal_id", _get(signal, "id", "")))
        if signal_id in order_by_signal:
            order = order_by_signal[signal_id]
            if (
                str(_get(signal, "symbol", "")).upper() == str(_get(order, "symbol", "")).upper()
                and str(_get(signal, "direction", "")).upper() == str(_get(order, "direction", "")).upper()
            ):
                matched += 1
            else:
                mismatches.append(signal_id)
        else:
            mismatches.append(signal_id)

    accuracy = (matched / expected) if expected else 1.0
    return CheckResult(
        name="signal_integrity",
        passed=accuracy >= 0.99,
        score=accuracy,
        details={
            "total_signals": expected,
            "executed_orders": executed,
            "matched": matched,
            "missed": max(expected - matched, 0),
            "mismatches": mismatches,
        },
        message=f"Signal accuracy {accuracy:.1%}",
    )

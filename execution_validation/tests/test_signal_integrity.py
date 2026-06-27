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
    mismatches: list[dict[str, Any]] = []
    order_by_signal = {
        str(_get(order, "signal_id", _get(order, "order_id", _get(order, "id", "")))): order
        for order in orders
    }

    for signal in signals:
        signal_id = str(_get(signal, "signal_id", _get(signal, "id", "")))
        if signal_id in order_by_signal:
            order = order_by_signal[signal_id]
            signal_volume = _get(signal, "volume", _get(signal, "lots", None))
            order_volume = _get(order, "volume", None)
            signal_stop = _get(signal, "stop_loss", _get(signal, "SL", None))
            order_stop = _get(order, "stop_loss", _get(order, "SL", None))
            signal_take = _get(signal, "take_profit", _get(signal, "TP", None))
            order_take = _get(order, "take_profit", _get(order, "TP", None))
            comparisons = {
                "symbol": str(_get(signal, "symbol", "")).upper() == str(_get(order, "symbol", "")).upper(),
                "direction": str(_get(signal, "direction", "")).upper() == str(_get(order, "direction", "")).upper(),
                "volume": True if signal_volume is None or order_volume is None else abs(float(signal_volume) - float(order_volume)) <= 1e-9,
                "stop_loss": True if signal_stop is None or order_stop is None else abs(float(signal_stop) - float(order_stop)) <= 1e-9,
                "take_profit": True if signal_take is None or order_take is None else abs(float(signal_take) - float(order_take)) <= 1e-9,
            }
            if all(comparisons.values()):
                matched += 1
            else:
                mismatches.append({"signal_id": signal_id, "comparisons": comparisons})
        else:
            mismatches.append({"signal_id": signal_id, "reason": "missing_order"})

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

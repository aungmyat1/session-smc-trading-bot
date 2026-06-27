from __future__ import annotations

__test__ = False

from typing import Any

from execution_validation.common import CheckResult


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def assess_order_execution(expected_orders: list[Any], filled_orders: list[Any]) -> CheckResult:
    matched = 0
    mismatches: list[str] = []
    filled_by_id = {str(_get(order, "order_id", _get(order, "id", ""))): order for order in filled_orders}

    for expected in expected_orders:
        order_id = str(_get(expected, "order_id", _get(expected, "id", "")))
        actual = filled_by_id.get(order_id)
        if actual is None:
            mismatches.append(order_id)
            continue
        numeric_fields = ("volume", "stop_loss", "take_profit")
        string_fields = ("symbol", "direction")
        numeric_ok = all(
            abs(float(_get(expected, field, 0.0)) - float(_get(actual, field, 0.0))) <= 1e-9
            for field in numeric_fields
        )
        string_ok = all(
            str(_get(expected, field, "")).upper() == str(_get(actual, field, "")).upper()
            for field in string_fields
        )
        if numeric_ok and string_ok:
            matched += 1
        else:
            mismatches.append(order_id)

    total = len(expected_orders)
    accuracy = (matched / total) if total else 1.0
    return CheckResult(
        name="order_execution",
        passed=accuracy >= 0.99,
        score=accuracy,
        details={
            "total_orders": total,
            "matched": matched,
            "mismatches": mismatches,
        },
        message=f"Order accuracy {accuracy:.1%}",
    )

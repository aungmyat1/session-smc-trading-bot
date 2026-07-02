from __future__ import annotations

from typing import Any


def validate_dry_run_order(order: dict[str, Any]) -> tuple[bool, str]:
    if not order.get("stop_loss"):
        return False, "stop loss is required"
    if float(order.get("risk_pct", 0)) <= 0:
        return False, "positive risk_pct is required"
    return True, "dry run accepted"

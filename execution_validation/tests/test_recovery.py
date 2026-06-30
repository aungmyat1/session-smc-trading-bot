from __future__ import annotations

__test__ = False

from typing import Any

from execution_validation.common import CheckResult
from execution_simulator.broker.virtual_broker import VirtualBroker


def assess_recovery(
    snapshot: dict,
    expected_open_positions: int,
    expected_risk_state: dict[str, Any] | None = None,
) -> CheckResult:
    restored = VirtualBroker.restore_state(snapshot)
    open_positions = restored._positions.open_positions()
    passed = len(open_positions) == expected_open_positions
    risk_state_ok = True
    if expected_risk_state is not None:
        actual_risk_state = snapshot.get("risk_state", {})
        risk_state_ok = actual_risk_state == expected_risk_state
        passed = passed and risk_state_ok
    return CheckResult(
        name="recovery",
        passed=passed,
        score=1.0 if passed else 0.0,
        details={
            "expected_open_positions": expected_open_positions,
            "actual_open_positions": len(open_positions),
            "expected_risk_state": expected_risk_state,
            "risk_state_restored": risk_state_ok,
        },
        message="Recovery state restored" if passed else "Recovery state mismatch",
    )

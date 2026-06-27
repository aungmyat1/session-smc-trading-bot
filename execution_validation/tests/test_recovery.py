from __future__ import annotations

__test__ = False

from execution_validation.common import CheckResult
from execution_simulator.broker.virtual_broker import VirtualBroker


def assess_recovery(snapshot: dict, expected_open_positions: int) -> CheckResult:
    restored = VirtualBroker.restore_state(snapshot)
    open_positions = restored._positions.open_positions()
    passed = len(open_positions) == expected_open_positions
    return CheckResult(
        name="recovery",
        passed=passed,
        score=1.0 if passed else 0.0,
        details={"expected_open_positions": expected_open_positions, "actual_open_positions": len(open_positions)},
        message="Recovery state restored" if passed else "Recovery state mismatch",
    )

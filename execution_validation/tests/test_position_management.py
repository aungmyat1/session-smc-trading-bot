from __future__ import annotations

__test__ = False

from typing import Any

from execution_validation.common import CheckResult
from execution_simulator.broker.virtual_broker import VirtualBroker


def assess_position_management(broker: VirtualBroker, scenarios: list[dict[str, Any]]) -> CheckResult:
    passed = 0
    details: list[dict[str, Any]] = []

    for scenario in scenarios:
        for tick in scenario.get("ticks", []):
            broker.on_market_event(tick)

        open_positions = broker._positions.open_positions()  # inspection-only validation
        expected_open = scenario.get("expected_open", 0)
        ok = (len(open_positions) == expected_open)
        details.append({"scenario": scenario.get("name", ""), "open_positions": len(open_positions)})
        if ok:
            passed += 1

    total = len(scenarios)
    accuracy = (passed / total) if total else 1.0
    return CheckResult(
        name="position_management",
        passed=accuracy >= 0.99,
        score=accuracy,
        details={"cases": details, "total": total, "passed": passed},
        message=f"Position management accuracy {accuracy:.1%}",
    )

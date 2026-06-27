from __future__ import annotations

__test__ = False

from typing import Any

from execution_validation.common import CheckResult
from execution_simulator.execution.risk_engine import RiskEngine


def assess_risk_engine(samples: list[dict[str, Any]], engine: RiskEngine) -> CheckResult:
    passed = 0
    details: list[dict[str, Any]] = []
    for sample in samples:
        result = engine.validate_order(
            symbol=str(sample["symbol"]),
            direction=str(sample["direction"]),
            volume=float(sample["volume"]),
            stop_loss=float(sample["stop_loss"]),
            take_profit=float(sample["take_profit"]),
            market_event=sample["market_event"],
            open_positions=int(sample.get("open_positions", 0)),
            same_symbol_positions=int(sample.get("same_symbol_positions", 0)),
            account_balance=float(sample.get("account_balance", 0.0)),
        )
        details.append({"symbol": sample["symbol"], "allowed": result.allowed, "reason": result.reason})
        if result.allowed == bool(sample.get("expected_allowed", True)):
            passed += 1

    total = len(samples)
    accuracy = (passed / total) if total else 1.0
    return CheckResult(
        name="risk_engine",
        passed=accuracy >= 0.99,
        score=accuracy,
        details={"cases": details, "total": total, "passed": passed},
        message=f"Risk engine accuracy {accuracy:.1%}",
    )


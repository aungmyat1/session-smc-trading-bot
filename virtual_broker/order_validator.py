from __future__ import annotations

from dataclasses import dataclass

from execution_simulator.execution.risk_engine import RiskEngine, RiskResult


@dataclass(slots=True)
class OrderValidator:
    """Thin compatibility facade around the execution risk engine."""

    risk_engine: RiskEngine

    def validate(self, *args, **kwargs) -> RiskResult:
        return self.risk_engine.validate_order(*args, **kwargs)

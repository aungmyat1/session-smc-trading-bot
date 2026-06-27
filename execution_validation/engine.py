from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import quantiles
from typing import Any

from execution_gate import ExecutionGate, ExecutionGateConfig
from execution_validation.common import CheckResult
from execution_validation.rules import ValidationRules, load_validation_rules
from execution_validation.tests.test_broker_rules import assess_broker_rules
from execution_validation.tests.test_order_execution import assess_order_execution
from execution_validation.tests.test_position_management import assess_position_management
from execution_validation.tests.test_recovery import assess_recovery
from execution_validation.tests.test_risk_engine import assess_risk_engine
from execution_validation.tests.test_signal_integrity import assess_signal_integrity
from execution_simulator.broker.virtual_broker import VirtualBroker, VirtualBrokerConfig
from execution_simulator.execution.risk_engine import RiskEngine
from execution_events import ExecutionEvent
from models.order import Order

_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_REPORT_DIR = _ROOT / "execution_validation" / "reports"


@dataclass(slots=True)
class ExecutionValidationReport:
    strategy: str
    period: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    rule_hash: str = ""
    strategy_version: str = ""
    signal_accuracy: float = 0.0
    order_accuracy: float = 0.0
    risk_accuracy: float = 0.0
    spread_handling_passed: bool = False
    slippage_passed: bool = False
    recovery_passed: bool = False
    broker_simulation_passed: bool = False
    slippage_average_pip: float = 0.0
    slippage_p95_pip: float = 0.0
    slippage_worst_pip: float = 0.0
    execution_delay_ms_average: float = 0.0
    execution_delay_ms_maximum: float = 0.0
    final_score: int = 0
    status: str = "BLOCKED"
    checks: dict[str, CheckResult] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "period": self.period,
            "created_at": self.created_at,
            "rule_hash": self.rule_hash,
            "strategy_version": self.strategy_version,
            "signal_accuracy": self.signal_accuracy,
            "order_accuracy": self.order_accuracy,
            "risk_accuracy": self.risk_accuracy,
            "spread_handling_passed": self.spread_handling_passed,
            "slippage_passed": self.slippage_passed,
            "recovery_passed": self.recovery_passed,
            "broker_simulation_passed": self.broker_simulation_passed,
            "slippage_average_pip": self.slippage_average_pip,
            "slippage_p95_pip": self.slippage_p95_pip,
            "slippage_worst_pip": self.slippage_worst_pip,
            "execution_delay_ms_average": self.execution_delay_ms_average,
            "execution_delay_ms_maximum": self.execution_delay_ms_maximum,
            "final_score": self.final_score,
            "status": self.status,
            "checks": {name: asdict(check) for name, check in self.checks.items()},
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True, default=str)


def _metric_average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _metric_p95(values: list[float]) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    return quantiles(values, n=20, method="inclusive")[18]


class ExecutionValidationSuite:
    def __init__(
        self,
        rules: ValidationRules | None = None,
        report_dir: Path | str | None = None,
    ) -> None:
        self.rules = rules or load_validation_rules()
        self.report_dir = Path(report_dir) if report_dir is not None else _DEFAULT_REPORT_DIR
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        *,
        strategy: str,
        period: str,
        signals: list[Any],
        orders: list[Any],
        fills: list[Any],
        execution_events: list[ExecutionEvent],
        risk_samples: list[dict[str, Any]],
        broker_rule_samples: list[dict[str, Any]],
        recovery_snapshot: dict[str, Any],
        recovery_expected_open_positions: int,
        broker: VirtualBroker | None = None,
        backtest_pf: float = 1.0,
        virtual_pf: float = 1.0,
    ) -> ExecutionValidationReport:
        broker = broker or VirtualBroker(config=VirtualBrokerConfig(max_spread_pips=self.rules.max_spread_points))
        risk_engine = RiskEngine(
            max_spread_pips=self.rules.max_spread_points,
            min_lot=self.rules.minimum_lot,
            max_lot=self.rules.maximum_lot,
            min_stop_distance_points=self.rules.min_stop_distance_points,
        )

        signal_check = assess_signal_integrity(signals, orders)
        order_check = assess_order_execution(orders, fills)
        risk_check = assess_risk_engine(risk_samples, risk_engine)
        broker_check = assess_broker_rules(broker_rule_samples, risk_engine)
        recovery_check = assess_recovery(recovery_snapshot, recovery_expected_open_positions)

        slippage_pips = []
        for ev in execution_events:
            if ev.event_type != "ORDER_FILLED":
                continue
            point_size = float(ev.metadata.get("point_size", 0.0001) or 0.0001)
            slippage = float(ev.metadata.get("slippage", 0.0) or 0.0)
            slippage_pips.append(slippage / point_size if point_size else 0.0)
        delays_ms = [float(ev.metadata.get("latency_ms", 0.0)) for ev in execution_events if ev.event_type == "ORDER_FILLED"]
        spread_ok = broker_check.passed

        slippage_average = _metric_average(slippage_pips)
        slippage_p95 = _metric_p95(slippage_pips)
        slippage_worst = max(slippage_pips) if slippage_pips else 0.0
        delay_average = _metric_average(delays_ms)
        delay_max = max(delays_ms) if delays_ms else 0.0

        slippage_passed = slippage_average <= self.rules.maximum_slippage_pip and slippage_worst <= self.rules.maximum_slippage_pip

        score = 0
        score += 20 if signal_check.passed else 0
        score += 20 if order_check.passed else 0
        score += 20 if risk_check.passed else 0
        score += 10 if spread_ok else 0
        score += 10 if slippage_passed else 0
        score += 10 if recovery_check.passed else 0
        score += 10 if broker_check.passed else 0

        report = ExecutionValidationReport(
            strategy=strategy,
            period=period,
            rule_hash=self.rules.rules_hash,
            strategy_version=self.rules.strategy_version,
            signal_accuracy=signal_check.score,
            order_accuracy=order_check.score,
            risk_accuracy=risk_check.score,
            spread_handling_passed=spread_ok,
            slippage_passed=slippage_passed,
            recovery_passed=recovery_check.passed,
            broker_simulation_passed=broker_check.passed,
            slippage_average_pip=slippage_average,
            slippage_p95_pip=slippage_p95,
            slippage_worst_pip=slippage_worst,
            execution_delay_ms_average=delay_average,
            execution_delay_ms_maximum=delay_max,
            final_score=score,
            status="READY FOR DEMO" if score >= 90 and signal_check.passed and order_check.passed and risk_check.passed and recovery_check.passed and slippage_passed and spread_ok and broker_check.passed else "BLOCKED",
            checks={
                "signal_integrity": signal_check,
                "order_execution": order_check,
                "risk_engine": risk_check,
                "broker_rules": broker_check,
                "recovery": recovery_check,
            },
        )
        self._write_report(report)
        return report

    def _write_report(self, report: ExecutionValidationReport) -> None:
        payload = report.to_dict()
        path = self.report_dir / "validation_report.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")

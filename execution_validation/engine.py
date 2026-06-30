from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import quantiles
from typing import Any

from execution_validation.common import CheckResult
from execution_validation.rules import ValidationRules, load_validation_rules
from execution_validation.tests.test_broker_rules import assess_broker_rules
from execution_validation.tests.test_order_execution import assess_order_execution
from execution_validation.tests.test_recovery import assess_recovery
from execution_validation.tests.test_risk_engine import assess_risk_engine
from execution_validation.tests.test_signal_integrity import assess_signal_integrity
from execution_simulator.broker.virtual_broker import VirtualBroker, VirtualBrokerConfig
from execution_simulator.execution.risk_engine import RiskEngine
from execution_events import ExecutionEvent
from research.lineage import build_release_metadata

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
    duplicate_order_protection_passed: bool = False
    spread_handling_passed: bool = False
    slippage_passed: bool = False
    exit_management_passed: bool = False
    recovery_passed: bool = False
    broker_simulation_passed: bool = False
    strategy_version_control_passed: bool = False
    slippage_average_pip: float = 0.0
    slippage_p95_pip: float = 0.0
    slippage_worst_pip: float = 0.0
    execution_delay_ms_average: float = 0.0
    execution_delay_ms_maximum: float = 0.0
    final_score: int = 0
    readiness_status: str = "BLOCKED"
    status: str = "BLOCKED"
    blocking_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    coverage_summary: dict[str, Any] = field(default_factory=dict)
    sample_size_summary: dict[str, Any] = field(default_factory=dict)
    exit_path_exercised: bool = False
    live_approval_allowed: bool = False
    release: dict[str, Any] = field(default_factory=build_release_metadata)
    metrics: dict[str, Any] = field(default_factory=dict)
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
            "duplicate_order_protection_passed": self.duplicate_order_protection_passed,
            "spread_handling_passed": self.spread_handling_passed,
            "slippage_passed": self.slippage_passed,
            "exit_management_passed": self.exit_management_passed,
            "recovery_passed": self.recovery_passed,
            "broker_simulation_passed": self.broker_simulation_passed,
            "strategy_version_control_passed": self.strategy_version_control_passed,
            "slippage_average_pip": self.slippage_average_pip,
            "slippage_p95_pip": self.slippage_p95_pip,
            "slippage_worst_pip": self.slippage_worst_pip,
            "execution_delay_ms_average": self.execution_delay_ms_average,
            "execution_delay_ms_maximum": self.execution_delay_ms_maximum,
            "final_score": self.final_score,
            "readiness_status": self.readiness_status,
            "status": self.status,
            "blocking_reasons": self.blocking_reasons,
            "warnings": self.warnings,
            "coverage_summary": self.coverage_summary,
            "sample_size_summary": self.sample_size_summary,
            "exit_path_exercised": self.exit_path_exercised,
            "live_approval_allowed": self.live_approval_allowed,
            "release": self.release,
            "metrics": self.metrics,
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


def _get_value(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _id_of(item: Any) -> str:
    return str(_get_value(item, "signal_id", _get_value(item, "order_id", _get_value(item, "id", ""))))


def _metadata_of(item: Any) -> dict[str, Any]:
    raw = _get_value(item, "metadata", {})
    return raw if isinstance(raw, dict) else {}


def _event_type_of(item: Any) -> str:
    return str(_get_value(item, "event_type", ""))


def _event_message_of(item: Any) -> str:
    return str(_get_value(item, "message", ""))


def _event_metadata_of(item: Any) -> dict[str, Any]:
    raw = _get_value(item, "metadata", {})
    return raw if isinstance(raw, dict) else {}


def _event_reason_of(item: Any) -> str:
    parts = [
        _event_message_of(item),
        str(_event_metadata_of(item).get("exit_reason", "")),
        str(_event_metadata_of(item).get("reason", "")),
    ]
    return " ".join(part for part in parts if part).strip()


def _detect_duplicates(items: list[Any]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for item in items:
        item_id = _id_of(item)
        if not item_id:
            continue
        if item_id in seen:
            duplicates.add(item_id)
        seen.add(item_id)
    return sorted(duplicates)


def _assess_duplicate_protection(signals: list[Any], orders: list[Any]) -> CheckResult:
    duplicate_signal_ids = _detect_duplicates(signals)
    duplicate_order_ids = _detect_duplicates(orders)
    duplicate_ids = sorted(set(duplicate_signal_ids + duplicate_order_ids))
    passed = not duplicate_ids
    return CheckResult(
        name="duplicate_order_protection",
        passed=passed,
        score=1.0 if passed else 0.0,
        details={
            "duplicate_signal_ids": duplicate_signal_ids,
            "duplicate_order_ids": duplicate_order_ids,
        },
        message="No duplicate signal or order IDs" if passed else f"Duplicate IDs detected: {', '.join(duplicate_ids)}",
    )


def _assess_strategy_version_control(signals: list[Any], orders: list[Any], strategy: str, rules: ValidationRules) -> CheckResult:
    versions = set()
    rule_hashes = set()
    for item in [*signals, *orders]:
        metadata = _metadata_of(item)
        if "strategy_version" in metadata:
            versions.add(str(metadata["strategy_version"]))
        if "rules_hash" in metadata:
            rule_hashes.add(str(metadata["rules_hash"]))
        if _get_value(item, "strategy_version", None) is not None:
            versions.add(str(_get_value(item, "strategy_version")))
        if _get_value(item, "rules_hash", None) is not None:
            rule_hashes.add(str(_get_value(item, "rules_hash")))

    strategy_name_matches = not rules.strategy_name or strategy == rules.strategy_name
    version_matches = not versions or versions == {rules.strategy_version}
    hash_matches = not rule_hashes or rule_hashes == {rules.rules_hash}
    passed = strategy_name_matches and version_matches and hash_matches
    return CheckResult(
        name="strategy_version_control",
        passed=passed,
        score=1.0 if passed else 0.0,
        details={
            "expected_strategy": rules.strategy_name,
            "actual_strategy": strategy,
            "expected_version": rules.strategy_version,
            "observed_versions": sorted(versions),
            "expected_rules_hash": rules.rules_hash,
            "observed_rules_hashes": sorted(rule_hashes),
        },
        message="Strategy version metadata is consistent" if passed else "Strategy/version metadata mismatch",
    )


def _assess_exit_management(execution_events: list[ExecutionEvent], fills: list[Any], broker: VirtualBroker | None = None) -> CheckResult:
    close_events = [ev for ev in execution_events if _event_type_of(ev) in {"POSITION_CLOSED", "ORDER_CLOSED"}]
    exit_reasons = [str(_event_reason_of(ev) or _event_type_of(ev)) for ev in close_events]
    open_positions = 0
    if broker is not None:
        try:
            open_positions = len(broker._positions.open_positions())  # inspection-only
        except Exception:
            open_positions = -1
    observed_exit = bool(close_events)
    open_positions_clear = open_positions in {0, -1}
    passed = observed_exit and open_positions_clear
    details = {
        "close_events": len(close_events),
        "exit_reasons": exit_reasons,
        "open_positions": open_positions,
        "observed_exit": observed_exit,
        "open_positions_clear": open_positions_clear,
    }
    if not observed_exit:
        details["failure"] = "no_close_events_observed"
    elif open_positions > 0:
        details["failure"] = "positions_remain_open_after_exit"
    return CheckResult(
        name="exit_management",
        passed=passed,
        score=1.0 if passed else 0.0,
        details=details,
        message="Exit management observed" if passed else "Exit management not fully exercised",
    )


def _coverage_flag(markers: dict[str, Any], key: str) -> bool:
    if key not in markers:
        return False
    value = markers.get(key)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "covered", "exercised"}
    return bool(value)


def _has_event_reason(execution_events: list[ExecutionEvent], keywords: tuple[str, ...]) -> bool:
    for ev in execution_events:
        if _event_type_of(ev) not in {"POSITION_CLOSED", "ORDER_CLOSED"}:
            continue
        reason = _event_reason_of(ev).lower()
        if any(keyword in reason for keyword in keywords):
            return True
    return False


def _coverage_summary(
    *,
    signals: list[Any],
    orders: list[Any],
    execution_events: list[ExecutionEvent],
    risk_samples: list[dict[str, Any]],
    broker_rule_samples: list[dict[str, Any]],
    recovery_snapshot: dict[str, Any],
    recovery_check: CheckResult,
    coverage_markers: dict[str, Any],
) -> dict[str, Any]:
    duplicate_signal_ids = _detect_duplicates(signals)
    duplicate_order_ids = _detect_duplicates(orders)
    broker_rejection_observed = any(not bool(sample.get("expected_allowed", True)) for sample in broker_rule_samples) or any(
        _event_type_of(ev) == "ORDER_REJECTED" for ev in execution_events
    )
    risk_rejection_observed = any(not bool(sample.get("expected_allowed", True)) for sample in risk_samples)
    entry_order_placement = _coverage_flag(coverage_markers, "entry_order_placement") or (bool(signals) and bool(orders))
    stop_loss_exit = _coverage_flag(coverage_markers, "stop_loss_exit") or _has_event_reason(execution_events, ("stop_loss", "stop loss", "sl"))
    take_profit_exit = _coverage_flag(coverage_markers, "take_profit_exit") or _has_event_reason(execution_events, ("take_profit", "take profit", "tp"))
    session_manual_close = _coverage_flag(coverage_markers, "session_manual_close") or _has_event_reason(
        execution_events,
        ("manual", "session", "managed", "close"),
    )
    duplicate_order_protection = _coverage_flag(coverage_markers, "duplicate_order_protection") or bool(duplicate_signal_ids or duplicate_order_ids)
    broker_rejection = _coverage_flag(coverage_markers, "broker_rejection") or broker_rejection_observed or risk_rejection_observed
    recovery_restart = _coverage_flag(coverage_markers, "recovery_restart") or recovery_check.passed or bool(recovery_snapshot)

    critical_paths = {
        "entry_order_placement": entry_order_placement,
        "stop_loss_exit": stop_loss_exit,
        "take_profit_exit": take_profit_exit,
        "session_manual_close": session_manual_close,
        "duplicate_order_protection": duplicate_order_protection,
        "broker_rejection": broker_rejection,
        "recovery_restart": recovery_restart,
    }
    exit_path_exercised = bool(stop_loss_exit or take_profit_exit or session_manual_close)
    return {
        "paths": {name: {"exercised": exercised} for name, exercised in critical_paths.items()},
        "critical_paths_complete": all(critical_paths.values()),
        "exit_path_exercised": exit_path_exercised,
        "broker_rejection_observed": broker_rejection_observed,
        "risk_rejection_observed": risk_rejection_observed,
        "duplicate_ids_detected": {"signals": duplicate_signal_ids, "orders": duplicate_order_ids},
    }


def _readiness_status(
    *,
    checks_passed: bool,
    exit_path_exercised: bool,
    critical_paths_complete: bool,
    executed_orders: int,
    rules: ValidationRules,
) -> str:
    if not checks_passed:
        return "BLOCKED"
    if critical_paths_complete and executed_orders >= rules.minimum_live_executed_orders:
        return "READY_FOR_LIVE"
    if critical_paths_complete and executed_orders >= rules.minimum_small_live_executed_orders:
        return "READY_FOR_SMALL_LIVE"
    if exit_path_exercised and executed_orders >= rules.minimum_shadow_executed_orders:
        return "READY_FOR_SHADOW"
    if exit_path_exercised and executed_orders >= rules.minimum_demo_executed_orders:
        return "READY_FOR_DEMO"
    return "READY_FOR_DEMO_WITH_LIMITATIONS"


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
        recovery_expected_risk_state: dict[str, Any] | None = None,
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
        recovery_check = assess_recovery(recovery_snapshot, recovery_expected_open_positions, recovery_expected_risk_state)
        duplicate_check = _assess_duplicate_protection(signals, orders)
        strategy_check = _assess_strategy_version_control(signals, orders, strategy, self.rules)
        exit_check = _assess_exit_management(execution_events, fills, broker=broker)

        slippage_pips = []
        for ev in execution_events:
            if _event_type_of(ev) != "ORDER_FILLED":
                continue
            metadata = _event_metadata_of(ev)
            point_size = float(metadata.get("point_size", 0.0001) or 0.0001)
            slippage = float(metadata.get("slippage", 0.0) or 0.0)
            slippage_pips.append(slippage / point_size if point_size else 0.0)
        delays_ms = [float(_event_metadata_of(ev).get("latency_ms", 0.0)) for ev in execution_events if _event_type_of(ev) == "ORDER_FILLED"]
        spread_ok = broker_check.passed

        slippage_average = _metric_average(slippage_pips)
        slippage_p95 = _metric_p95(slippage_pips)
        slippage_worst = max(slippage_pips) if slippage_pips else 0.0
        delay_average = _metric_average(delays_ms)
        delay_max = max(delays_ms) if delays_ms else 0.0

        slippage_passed = slippage_average <= self.rules.maximum_slippage_pip and slippage_worst <= self.rules.maximum_slippage_pip
        spread_ok = broker_check.passed
        exit_ok = exit_check.passed

        score = 0
        score += 20 if signal_check.passed else 0
        score += 15 if order_check.passed else 0
        score += 15 if risk_check.passed else 0
        score += 10 if duplicate_check.passed else 0
        score += 10 if spread_ok else 0
        score += 10 if slippage_passed else 0
        score += 5 if exit_ok else 0
        score += 5 if recovery_check.passed else 0
        score += 5 if broker_check.passed else 0
        score += 5 if strategy_check.passed else 0

        report = ExecutionValidationReport(
            strategy=strategy,
            period=period,
            rule_hash=self.rules.rules_hash,
            strategy_version=self.rules.strategy_version,
            signal_accuracy=signal_check.score,
            order_accuracy=order_check.score,
            risk_accuracy=risk_check.score,
            duplicate_order_protection_passed=duplicate_check.passed,
            spread_handling_passed=spread_ok,
            slippage_passed=slippage_passed,
            exit_management_passed=exit_ok,
            recovery_passed=recovery_check.passed,
            broker_simulation_passed=broker_check.passed,
            strategy_version_control_passed=strategy_check.passed,
            slippage_average_pip=slippage_average,
            slippage_p95_pip=slippage_p95,
            slippage_worst_pip=slippage_worst,
            execution_delay_ms_average=delay_average,
            execution_delay_ms_maximum=delay_max,
            final_score=score,
            status="READY FOR DEMO"
            if score >= 90
            and signal_check.passed
            and order_check.passed
            and risk_check.passed
            and duplicate_check.passed
            and recovery_check.passed
            and slippage_passed
            and spread_ok
            and broker_check.passed
            and strategy_check.passed
            and exit_ok
            else "BLOCKED",
            checks={
                "signal_integrity": signal_check,
                "order_execution": order_check,
                "risk_engine": risk_check,
                "duplicate_order_protection": duplicate_check,
                "strategy_version_control": strategy_check,
                "exit_management": exit_check,
                "broker_rules": broker_check,
                "recovery": recovery_check,
            },
            metrics={
                "total_signals": signal_check.details.get("total_signals", len(signals)),
                "executed_orders": signal_check.details.get("executed_orders", len(orders)),
                "signal_missed": signal_check.details.get("missed", 0),
                "signal_matches": signal_check.details.get("matched", 0),
                "average_slippage_pip": slippage_average,
                "p95_slippage_pip": slippage_p95,
                "worst_slippage_pip": slippage_worst,
                "average_execution_delay_ms": delay_average,
                "maximum_execution_delay_ms": delay_max,
                "spread_handling": "PASS" if spread_ok else "FAIL",
                "broker_simulation": "PASS" if broker_check.passed else "FAIL",
                "exit_management": "PASS" if exit_ok else "FAIL",
            },
        )
        self._write_report(report)
        return report

    def _write_report(self, report: ExecutionValidationReport) -> None:
        payload = report.to_dict()
        path = self.report_dir / "validation_report.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")

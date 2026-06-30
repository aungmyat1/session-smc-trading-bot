"""Validation gate engine for replay, backtest, and lifecycle promotion."""

from __future__ import annotations

import html
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

from core.strategy_registry import DirectCatalogMutationError
from research.regression.engine import RegressionEngine, RegressionResult

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_CONFIG_PATH = _ROOT / "config" / "validation.yaml"
_DEFAULT_REPORT_DIR = _ROOT / "reports" / "validation"

_ALLOWED_TRANSITIONS = {
    ("IDLE", "SETUP"),
    ("SETUP", "CONFIRMED"),
    ("SETUP", "EXPIRED"),
    ("SETUP", "CANCELLED"),
    ("CONFIRMED", "ORDER_PLACED"),
    ("CONFIRMED", "EXPIRED"),
    ("ORDER_PLACED", "FILLED"),
    ("ORDER_PLACED", "REJECTED"),
    ("FILLED", "CLOSED"),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_nan(value: Any) -> bool:
    return isinstance(value, float) and math.isnan(value)


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    raise TypeError(f"Unsupported validation payload type: {type(value)!r}")


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return list(value)


@dataclass
class ReplayTrade:
    trade_id: str
    timestamp: str
    side: str
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size: float
    required_features: list[str] = field(default_factory=list)


@dataclass
class ReplayValidationInput:
    completed_successfully: bool
    trades: list[ReplayTrade] = field(default_factory=list)
    exceptions: list[str] = field(default_factory=list)
    state_transitions: list[tuple[str, str]] = field(default_factory=list)
    required_features: list[str] = field(default_factory=list)
    available_features: list[str] = field(default_factory=list)
    missing_timestamps: list[str] = field(default_factory=list)
    has_uncaught_exceptions: bool = False


@dataclass
class BacktestValidationInput:
    completed_successfully: bool
    trade_count: int
    expectancy: float
    max_drawdown: float
    profit_factor: float
    metrics: dict[str, float] = field(default_factory=dict)
    sharpe_ratio: float | None = None
    sortino_ratio: float | None = None
    recovery_factor: float | None = None
    mar_ratio: float | None = None
    exposure_pct: float | None = None
    average_hold_time_minutes: float | None = None
    spread_included: bool | None = None
    commission_included: bool | None = None
    slippage_included: bool | None = None
    swap_included: bool | None = None
    latency_included: bool | None = None
    monte_carlo_passed: bool | None = None
    bootstrap_passed: bool | None = None
    confidence_interval_passed: bool | None = None


@dataclass
class ValidationCheck:
    name: str
    passed: bool
    severity: str = "ERROR"
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    stage: str
    status: str
    checks: list[ValidationCheck] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "status": self.status,
            "checks": [asdict(check) for check in self.checks],
            "created_at": self.created_at,
            "summary": self.summary,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True, default=str)

    def to_markdown(self) -> str:
        lines = [
            f"## {self.stage.title()} Validation",
            "",
            f"- Status: **{self.status}**",
            f"- Timestamp: `{self.created_at}`",
        ]
        if self.summary:
            lines.extend(["", self.summary])
        lines.extend(["", "| Check | Status | Message |", "|---|---|---|"])
        for check in self.checks:
            status = "PASS" if check.passed else "FAIL"
            msg = check.message.replace("|", "\\|")
            lines.append(f"| {check.name} | {status} | {msg} |")
        return "\n".join(lines) + "\n"

    def to_html(self) -> str:
        rows = []
        for check in self.checks:
            status = "PASS" if check.passed else "FAIL"
            rows.append(
                "<tr>"
                f"<td>{html.escape(check.name)}</td>"
                f"<td>{html.escape(status)}</td>"
                f"<td>{html.escape(check.message)}</td>"
                "</tr>"
            )
        return (
            "<html><body>"
            f"<h2>{html.escape(self.stage.title())} Validation</h2>"
            f"<p><strong>Status:</strong> {html.escape(self.status)}</p>"
            f"<p><strong>Timestamp:</strong> {html.escape(self.created_at)}</p>"
            + (f"<p>{html.escape(self.summary)}</p>" if self.summary else "")
            + "<table><thead><tr><th>Check</th><th>Status</th><th>Message</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
            "</body></html>"
        )


@dataclass
class ValidationConfig:
    minimum_trade_count: int = 100
    minimum_profit_factor: float = 1.0
    maximum_drawdown: float = 10.0
    minimum_expectancy: float = 0.0
    regression_thresholds: dict[str, dict[str, float]] = field(default_factory=dict)
    promotion_map: dict[str, str] = field(default_factory=dict)

    def next_stage(self, current_stage: str) -> Optional[str]:
        return self.promotion_map.get(current_stage)


def load_validation_config(path: Path | str | None = None) -> ValidationConfig:
    config_path = Path(path) if path is not None else _DEFAULT_CONFIG_PATH
    payload: dict[str, Any] = {}
    if config_path.exists():
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            payload = {}
    return ValidationConfig(
        minimum_trade_count=int(payload.get("minimum_trade_count", 100)),
        minimum_profit_factor=float(payload.get("minimum_profit_factor", 1.0)),
        maximum_drawdown=float(payload.get("maximum_drawdown", 10.0)),
        minimum_expectancy=float(payload.get("minimum_expectancy", 0.0)),
        regression_thresholds=dict(payload.get("regression_thresholds", {}) or {}),
        promotion_map=dict(payload.get("promotion_map", {}) or {}),
    )


class ValidationGate:
    """Validate replay and backtest outputs before promotion."""

    def __init__(self, config: ValidationConfig | None = None) -> None:
        self.config = config or load_validation_config()

    def validate_replay(
        self, payload: ReplayValidationInput | dict[str, Any]
    ) -> ValidationResult:
        data = _as_dict(payload)
        checks: list[ValidationCheck] = []

        completed = bool(data.get("completed_successfully", False))
        checks.append(
            ValidationCheck(
                "replay_completed",
                completed,
                message=(
                    "Replay completed successfully"
                    if completed
                    else "Replay did not complete successfully"
                ),
            )
        )

        exceptions = _as_list(data.get("exceptions", []))
        has_uncaught = bool(data.get("has_uncaught_exceptions", False)) or bool(
            exceptions
        )
        checks.append(
            ValidationCheck(
                "no_uncaught_exceptions",
                not has_uncaught,
                message=(
                    "No uncaught exceptions detected"
                    if not has_uncaught
                    else "Replay emitted uncaught exceptions"
                ),
                details={"exceptions": exceptions},
            )
        )

        trades = [_as_dict(trade) for trade in _as_list(data.get("trades", []))]
        trade_ids = [
            str(trade.get("trade_id", "")) for trade in trades if trade.get("trade_id")
        ]
        duplicate_ids = sorted({tid for tid in trade_ids if trade_ids.count(tid) > 1})
        checks.append(
            ValidationCheck(
                "no_duplicate_trade_ids",
                not duplicate_ids,
                message=(
                    "No duplicate trade IDs"
                    if not duplicate_ids
                    else f"Duplicate trade IDs: {', '.join(duplicate_ids)}"
                ),
                details={"duplicates": duplicate_ids},
            )
        )

        invalid_transitions = []
        for transition in _as_list(data.get("state_transitions", [])):
            if isinstance(transition, tuple) and len(transition) == 2:
                src, dst = transition
            elif isinstance(transition, list) and len(transition) == 2:
                src, dst = transition[0], transition[1]
            else:
                invalid_transitions.append(str(transition))
                continue
            if (str(src), str(dst)) not in _ALLOWED_TRANSITIONS:
                invalid_transitions.append(f"{src}->{dst}")
        checks.append(
            ValidationCheck(
                "valid_state_transitions",
                not invalid_transitions,
                message=(
                    "State transitions valid"
                    if not invalid_transitions
                    else f"Invalid transitions: {', '.join(invalid_transitions)}"
                ),
                details={"invalid_transitions": invalid_transitions},
            )
        )

        negative_sizes = [
            trade.get("trade_id")
            for trade in trades
            if float(trade.get("position_size", 0.0) or 0.0) < 0
        ]
        checks.append(
            ValidationCheck(
                "non_negative_position_sizes",
                not negative_sizes,
                message=(
                    "Position sizes are non-negative"
                    if not negative_sizes
                    else f"Negative position sizes on trades: {', '.join(map(str, negative_sizes))}"
                ),
                details={"trade_ids": negative_sizes},
            )
        )

        invalid_geometry = []
        missing_trade_timestamps = []
        for trade in trades:
            trade_id = str(trade.get("trade_id", ""))
            ts = trade.get("timestamp")
            if not ts:
                missing_trade_timestamps.append(trade_id)
            entry = trade.get("entry_price")
            stop = trade.get("stop_loss")
            target = trade.get("take_profit")
            side = str(trade.get("side", "")).lower()
            if _is_nan(entry) or _is_nan(stop) or _is_nan(target):
                invalid_geometry.append(f"{trade_id}: NaN price")
                continue
            try:
                entry_f = float(entry)  # type: ignore[arg-type]
                stop_f = float(stop)  # type: ignore[arg-type]
                target_f = float(target)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                invalid_geometry.append(f"{trade_id}: non-numeric price")
                continue
            if side == "long" and not (stop_f < entry_f < target_f):
                invalid_geometry.append(f"{trade_id}: long geometry invalid")
            elif side == "short" and not (target_f < entry_f < stop_f):
                invalid_geometry.append(f"{trade_id}: short geometry invalid")
            required = [str(v) for v in _as_list(trade.get("required_features", []))]
            available = {str(v) for v in _as_list(data.get("available_features", []))}
            missing = [feat for feat in required if feat not in available]
            if missing:
                invalid_geometry.append(
                    f"{trade_id}: missing features {', '.join(missing)}"
                )
        checks.append(
            ValidationCheck(
                "valid_trade_geometry",
                not invalid_geometry,
                message=(
                    "Trade SL/TP geometry valid"
                    if not invalid_geometry
                    else "; ".join(invalid_geometry)
                ),
                details={"invalid_geometry": invalid_geometry},
            )
        )

        checks.append(
            ValidationCheck(
                "no_missing_timestamps",
                not (data.get("missing_timestamps") or missing_trade_timestamps),
                message=(
                    "No missing timestamps"
                    if not (data.get("missing_timestamps") or missing_trade_timestamps)
                    else "Missing timestamps detected"
                ),
                details={
                    "missing_timestamps": data.get("missing_timestamps", []),
                    "trade_timestamps": missing_trade_timestamps,
                },
            )
        )

        all_passed = all(check.passed for check in checks)
        status = "PASS" if all_passed else "FAIL"
        summary = (
            "Replay validation passed." if all_passed else "Replay validation failed."
        )
        return ValidationResult(
            stage="replay", status=status, checks=checks, summary=summary
        )

    def validate_backtest(
        self, payload: BacktestValidationInput | dict[str, Any]
    ) -> ValidationResult:
        data = _as_dict(payload)
        checks: list[ValidationCheck] = []

        completed = bool(data.get("completed_successfully", False))
        checks.append(
            ValidationCheck(
                "backtest_completed",
                completed,
                message=(
                    "Backtest completed successfully"
                    if completed
                    else "Backtest did not complete successfully"
                ),
            )
        )

        metrics = dict(data.get("metrics", {}) or {})
        trade_count = int(
            data.get("trade_count", metrics.get("trade_count", 0) or 0) or 0
        )
        expectancy = float(
            data.get("expectancy", metrics.get("expectancy", float("nan")))
            or float("nan")
        )
        max_drawdown = float(
            data.get("max_drawdown", metrics.get("max_drawdown", float("nan")))
            or float("nan")
        )
        profit_factor = float(
            data.get("profit_factor", metrics.get("profit_factor", float("nan")))
            or float("nan")
        )
        sharpe_ratio = data.get("sharpe_ratio", metrics.get("sharpe_ratio"))
        sortino_ratio = data.get("sortino_ratio", metrics.get("sortino_ratio"))
        recovery_factor = data.get("recovery_factor", metrics.get("recovery_factor"))
        mar_ratio = data.get("mar_ratio", metrics.get("mar_ratio"))
        exposure_pct = data.get("exposure_pct", metrics.get("exposure_pct"))
        average_hold_time_minutes = data.get(
            "average_hold_time_minutes", metrics.get("average_hold_time_minutes")
        )
        costs_flags = {
            "spread_included": data.get(
                "spread_included", metrics.get("spread_included")
            ),
            "commission_included": data.get(
                "commission_included", metrics.get("commission_included")
            ),
            "slippage_included": data.get(
                "slippage_included", metrics.get("slippage_included")
            ),
            "swap_included": data.get("swap_included", metrics.get("swap_included")),
            "latency_included": data.get(
                "latency_included", metrics.get("latency_included")
            ),
        }
        robustness_flags = {
            "monte_carlo_passed": data.get(
                "monte_carlo_passed", metrics.get("monte_carlo_passed")
            ),
            "bootstrap_passed": data.get(
                "bootstrap_passed", metrics.get("bootstrap_passed")
            ),
            "confidence_interval_passed": data.get(
                "confidence_interval_passed", metrics.get("confidence_interval_passed")
            ),
        }

        checks.append(
            ValidationCheck(
                "minimum_trade_count",
                trade_count >= self.config.minimum_trade_count,
                message=(
                    f"Trade count {trade_count} >= {self.config.minimum_trade_count}"
                    if trade_count >= self.config.minimum_trade_count
                    else f"Trade count {trade_count} below minimum {self.config.minimum_trade_count}"
                ),
                details={"trade_count": trade_count},
            )
        )
        checks.append(
            ValidationCheck(
                "positive_expectancy",
                not _is_nan(expectancy) and expectancy > self.config.minimum_expectancy,
                message=(
                    f"Expectancy {expectancy:.4f} above minimum {self.config.minimum_expectancy}"
                    if not _is_nan(expectancy)
                    and expectancy > self.config.minimum_expectancy
                    else "Expectancy not positive"
                ),
                details={"expectancy": expectancy},
            )
        )
        checks.append(
            ValidationCheck(
                "maximum_drawdown",
                not _is_nan(max_drawdown)
                and max_drawdown <= self.config.maximum_drawdown,
                message=(
                    f"Max drawdown {max_drawdown:.4f} within limit {self.config.maximum_drawdown}"
                    if not _is_nan(max_drawdown)
                    and max_drawdown <= self.config.maximum_drawdown
                    else f"Max drawdown {max_drawdown:.4f} above limit {self.config.maximum_drawdown}"
                ),
                details={"max_drawdown": max_drawdown},
            )
        )
        checks.append(
            ValidationCheck(
                "profit_factor",
                not _is_nan(profit_factor)
                and profit_factor >= self.config.minimum_profit_factor,
                message=(
                    f"Profit factor {profit_factor:.4f} meets threshold {self.config.minimum_profit_factor}"
                    if not _is_nan(profit_factor)
                    and profit_factor >= self.config.minimum_profit_factor
                    else f"Profit factor {profit_factor:.4f} below threshold {self.config.minimum_profit_factor}"
                ),
                details={"profit_factor": profit_factor},
            )
        )

        if sharpe_ratio is not None:
            sharpe_ratio = float(sharpe_ratio)
            checks.append(
                ValidationCheck(
                    "sharpe_ratio",
                    sharpe_ratio >= 1.0,
                    message=(
                        f"Sharpe ratio {sharpe_ratio:.4f} >= 1.0"
                        if sharpe_ratio >= 1.0
                        else f"Sharpe ratio {sharpe_ratio:.4f} below 1.0"
                    ),
                    details={"sharpe_ratio": sharpe_ratio},
                )
            )
        if sortino_ratio is not None:
            sortino_ratio = float(sortino_ratio)
            checks.append(
                ValidationCheck(
                    "sortino_ratio",
                    sortino_ratio >= 1.0,
                    message=(
                        f"Sortino ratio {sortino_ratio:.4f} >= 1.0"
                        if sortino_ratio >= 1.0
                        else f"Sortino ratio {sortino_ratio:.4f} below 1.0"
                    ),
                    details={"sortino_ratio": sortino_ratio},
                )
            )
        if recovery_factor is not None:
            recovery_factor = float(recovery_factor)
            checks.append(
                ValidationCheck(
                    "recovery_factor",
                    recovery_factor >= 1.0,
                    message=(
                        f"Recovery factor {recovery_factor:.4f} >= 1.0"
                        if recovery_factor >= 1.0
                        else f"Recovery factor {recovery_factor:.4f} below 1.0"
                    ),
                    details={"recovery_factor": recovery_factor},
                )
            )
        if mar_ratio is not None:
            mar_ratio = float(mar_ratio)
            checks.append(
                ValidationCheck(
                    "mar_ratio",
                    mar_ratio >= 0.5,
                    message=(
                        f"MAR ratio {mar_ratio:.4f} >= 0.5"
                        if mar_ratio >= 0.5
                        else f"MAR ratio {mar_ratio:.4f} below 0.5"
                    ),
                    details={"mar_ratio": mar_ratio},
                )
            )
        if exposure_pct is not None:
            exposure_pct = float(exposure_pct)
            checks.append(
                ValidationCheck(
                    "exposure_pct",
                    0.0 <= exposure_pct <= 100.0,
                    message=(
                        f"Exposure {exposure_pct:.2f}% within range"
                        if 0.0 <= exposure_pct <= 100.0
                        else f"Exposure {exposure_pct:.2f}% outside valid range"
                    ),
                    details={"exposure_pct": exposure_pct},
                )
            )
        if average_hold_time_minutes is not None:
            average_hold_time_minutes = float(average_hold_time_minutes)
            checks.append(
                ValidationCheck(
                    "average_hold_time_minutes",
                    average_hold_time_minutes > 0,
                    message=(
                        f"Average hold time {average_hold_time_minutes:.2f} min"
                        if average_hold_time_minutes > 0
                        else "Average hold time must be positive"
                    ),
                    details={"average_hold_time_minutes": average_hold_time_minutes},
                )
            )
        for name, value in costs_flags.items():
            if value is None:
                continue
            checks.append(
                ValidationCheck(
                    name,
                    bool(value),
                    message=(
                        f"{name.replace('_', ' ').title()} included"
                        if bool(value)
                        else f"{name.replace('_', ' ').title()} not included"
                    ),
                    details={name: bool(value)},
                )
            )
        for name, value in robustness_flags.items():
            if value is None:
                continue
            checks.append(
                ValidationCheck(
                    name,
                    bool(value),
                    message=(
                        f"{name.replace('_', ' ').title()} passed"
                        if bool(value)
                        else f"{name.replace('_', ' ').title()} failed"
                    ),
                    details={name: bool(value)},
                )
            )

        metric_values = list(metrics.values()) + [
            trade_count,
            expectancy,
            max_drawdown,
            profit_factor,
        ]
        has_nan = any(
            _is_nan(value) for value in metric_values if isinstance(value, float)
        )
        checks.append(
            ValidationCheck(
                "no_nan_metrics",
                not has_nan,
                message="No NaN metrics" if not has_nan else "NaN detected in metrics",
                details={"metrics": metrics},
            )
        )

        all_passed = all(check.passed for check in checks)
        status = "PASS" if all_passed else "FAIL"
        summary = (
            "Backtest validation passed."
            if all_passed
            else "Backtest validation failed."
        )
        return ValidationResult(
            stage="backtest", status=status, checks=checks, summary=summary
        )


@dataclass
class ValidationReportBundle:
    strategy: str
    replay: ValidationResult
    backtest: ValidationResult
    regression: RegressionResult
    overall_status: str
    lifecycle_recommendation: str
    next_stage: Optional[str]
    promoted: bool
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "replay": self.replay.to_dict(),
            "backtest": self.backtest.to_dict(),
            "regression": self.regression.to_dict(),
            "overall_status": self.overall_status,
            "lifecycle_recommendation": self.lifecycle_recommendation,
            "next_stage": self.next_stage,
            "promoted": self.promoted,
            "created_at": self.created_at,
        }

    def to_markdown(self) -> str:
        lines = [
            f"# Validation Report - {self.strategy}",
            "",
            f"- Overall Status: **{self.overall_status}**",
            f"- Lifecycle Recommendation: **{self.lifecycle_recommendation}**",
            f"- Next Stage: `{self.next_stage or 'n/a'}`",
            f"- Promoted: `{str(self.promoted).lower()}`",
            f"- Timestamp: `{self.created_at}`",
            "",
            self.replay.to_markdown(),
            self.backtest.to_markdown(),
            self.regression.to_markdown(),
        ]
        return "\n".join(lines)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True, default=str)

    def to_html(self) -> str:
        return (
            "<html><body>"
            f"<h1>Validation Report - {html.escape(self.strategy)}</h1>"
            f"<p><strong>Overall Status:</strong> {html.escape(self.overall_status)}</p>"
            f"<p><strong>Lifecycle Recommendation:</strong> {html.escape(self.lifecycle_recommendation)}</p>"
            f"<p><strong>Next Stage:</strong> {html.escape(self.next_stage or 'n/a')}</p>"
            f"<p><strong>Promoted:</strong> {str(self.promoted).lower()}</p>"
            f"<p><strong>Timestamp:</strong> {html.escape(self.created_at)}</p>"
            + self.replay.to_html()
            + self.backtest.to_html()
            + self.regression.to_html()
            + "</body></html>"
        )


class ValidationRunner:
    """Run replay validation, backtest validation, regression comparison, and promotion."""

    def __init__(
        self,
        strategy: str,
        config: ValidationConfig | None = None,
        registry_path: Path | str | None = None,
        output_dir: Path | str | None = None,
        regression_engine: RegressionEngine | None = None,
    ) -> None:
        self.strategy = strategy
        self.config = config or load_validation_config()
        self.registry_path = registry_path
        self.output_dir = (
            Path(output_dir) if output_dir is not None else _DEFAULT_REPORT_DIR
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.gate = ValidationGate(self.config)
        self.regression_engine = regression_engine or RegressionEngine(
            self.config.regression_thresholds
        )

    def run(
        self,
        replay: ReplayValidationInput | dict[str, Any] | None = None,
        backtest: BacktestValidationInput | dict[str, Any] | None = None,
        latest_metrics: dict[str, float] | None = None,
        previous_metrics: dict[str, float] | None = None,
        current_stage: str = "backtest",
        promote: bool = False,
    ) -> ValidationReportBundle:
        if replay is None:
            replay_result = ValidationResult(
                stage="replay",
                status="SKIPPED",
                summary="Replay validation was not requested.",
            )
        else:
            replay_result = self.gate.validate_replay(replay)

        if backtest is None:
            backtest_result = ValidationResult(
                stage="backtest",
                status="SKIPPED",
                summary="Backtest validation was not requested.",
            )
        else:
            backtest_result = self.gate.validate_backtest(backtest)

        if latest_metrics is None:
            regression_result = RegressionResult(
                status="PASS",
                comparisons=[],
                summary="Regression comparison skipped; no latest metrics provided.",
                baseline_available=False,
            )
        else:
            regression_result = self.regression_engine.compare(
                latest_metrics, previous_metrics
            )

        overall_status = "PASS"
        if (
            replay_result.status not in {"PASS", "SKIPPED"}
            or backtest_result.status not in {"PASS", "SKIPPED"}
            or regression_result.status == "FAIL"
        ):
            overall_status = "FAIL"
        elif regression_result.status == "WARNING":
            overall_status = "WARNING"

        next_stage = self.config.next_stage(current_stage)
        promoted = False
        if promote and overall_status == "PASS" and next_stage:
            raise DirectCatalogMutationError(
                "ValidationRunner cannot promote lifecycle state. Record its report as evidence and request a governed transition."
            )

        recommendation = {
            "PASS": "Eligible for next lifecycle stage",
            "WARNING": "Review regression drift before promotion",
            "FAIL": "Hold strategy in current stage",
        }[overall_status]

        bundle = ValidationReportBundle(
            strategy=self.strategy,
            replay=replay_result,
            backtest=backtest_result,
            regression=regression_result,
            overall_status=overall_status,
            lifecycle_recommendation=recommendation,
            next_stage=next_stage,
            promoted=promoted,
        )
        self._write_reports(bundle)
        return bundle

    def _write_reports(self, bundle: ValidationReportBundle) -> None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        report_dir = self.output_dir / bundle.strategy / stamp
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "validation.md").write_text(
            bundle.to_markdown(), encoding="utf-8"
        )
        (report_dir / "validation.json").write_text(bundle.to_json(), encoding="utf-8")
        (report_dir / "validation.html").write_text(bundle.to_html(), encoding="utf-8")

"""Strategy Validation Operating System.

This layer sits above the existing replay, backtest, regression, and registry
modules. It turns a raw strategy description into a structured spec, then
drives it through PASS / FAIL / FIX gates.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal

from core.strategy_registry import can_deploy_strategy, promote_strategy_stage
from research.regression.engine import RegressionEngine
from research.validation.engine import (
    BacktestValidationInput,
    ReplayValidationInput,
    ValidationGate,
    ValidationResult,
    load_validation_config,
)
from research.lineage import build_release_metadata

_ROOT = Path(__file__).resolve().parents[2]

StageStatus = Literal["PASS", "FAIL", "FIX"]

_REQUIRED_FIELDS = (
    "market",
    "session",
    "bias",
    "entry_trigger",
    "confirmation",
    "invalidation",
    "stop_loss",
    "take_profit",
    "risk",
    "filters",
    "exit_rules",
)

_FIELD_ALIASES = {
    "market": ("market", "instrument", "asset"),
    "session": ("session", "sessions"),
    "bias": ("bias", "direction", "trend"),
    "entry_trigger": ("entry trigger", "entry", "trigger"),
    "confirmation": ("confirmation", "confirmations", "confirm"),
    "invalidation": ("invalidation", "invalid", "invalidates"),
    "stop_loss": ("stop loss", "stop", "sl"),
    "take_profit": ("take profit", "target", "tp"),
    "risk": ("risk", "risk percent", "risk%"),
    "filters": ("filters", "filter"),
    "exit_rules": ("exit rules", "exit", "exits"),
}

_FIELD_LABELS = {
    "market": "Market",
    "session": "Session",
    "bias": "Bias",
    "entry_trigger": "Entry Trigger",
    "confirmation": "Confirmation",
    "invalidation": "Invalidation",
    "stop_loss": "Stop Loss",
    "take_profit": "Take Profit",
    "risk": "Risk",
    "filters": "Filters",
    "exit_rules": "Exit Rules",
}

_AMBIGUITY_PATTERNS = (
    r"\bor\/and\b",
    r"\band\/or\b",
    r"\bor\b",
    r"\bmaybe\b",
    r"\btbd\b",
    r"\bunclear\b",
    r"\bunspecified\b",
    r"\boptional\b",
    r"\bwhatever\b",
    r"\bdepends\b",
    r"\bif needed\b",
)

_CONTRADICTION_HINTS = (
    ("bias", ("long", "short")),
    ("direction", ("bullish", "bearish")),
    ("entry", ("buy", "sell")),
    ("exit", ("close long", "close short")),
)

_PLACEHOLDER_MARKERS = {
    "synthetic",
    "sample",
    "example",
    "placeholder",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _normalize_field_name(name: str) -> str:
    cleaned = name.strip().lower().replace("_", " ")
    for canonical, aliases in _FIELD_ALIASES.items():
        if cleaned == canonical or cleaned in aliases:
            return canonical
    return cleaned.replace(" ", "_")


def _append_fragment(current: str, fragment: str) -> str:
    fragment = fragment.strip()
    if not fragment:
        return current
    if not current:
        return fragment
    return f"{current} {fragment}"


def _extract_fields(raw_text: str) -> dict[str, str]:
    fields: dict[str, list[str]] = {field: [] for field in _REQUIRED_FIELDS}
    current_field: str | None = None

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            current_field = None
            continue

        key_match = re.match(r"^([A-Za-z][A-Za-z0-9 _/-]{1,40}):\s*(.*)$", line)
        if key_match:
            field_name = _normalize_field_name(key_match.group(1))
            value = key_match.group(2).strip()
            if field_name in fields:
                current_field = field_name
                if value:
                    fields[field_name].append(value)
                continue

        if current_field:
            if re.match(r"^[A-Za-z][A-Za-z0-9 _/-]{1,40}:\s*", line):
                current_field = None
                continue
            fields[current_field].append(line)
            continue

    extracted = {field: " ".join(parts).strip() for field, parts in fields.items() if parts}
    return extracted


def _infer_field_from_keywords(raw_text: str, field: str) -> str:
    text = raw_text.lower()
    if field == "market":
        if any(token in text for token in ("eurusd", "gbpusd", "forex", "fx")):
            return "FX"
    elif field == "session":
        sessions = []
        for token in ("london", "new york", "asian", "tokyo", "ny", "nyc"):
            if token in text:
                sessions.append(token.title())
        if sessions:
            return ", ".join(dict.fromkeys(sessions))
    elif field == "bias":
        if "bullish" in text or "long bias" in text or "long" in text:
            return "Bullish / Long"
        if "bearish" in text or "short bias" in text or "short" in text:
            return "Bearish / Short"
    elif field == "entry_trigger":
        if any(token in text for token in ("sweep", "breakout", "choch", "bos", "mss")):
            return _first_matching_phrase(raw_text, ("sweep", "breakout", "choch", "bos", "mss"))
    elif field == "confirmation":
        if any(token in text for token in ("fvg", "order block", "retest", "displacement")):
            return _first_matching_phrase(raw_text, ("fvg", "order block", "retest", "displacement"))
    elif field == "invalidation":
        if any(token in text for token in ("invalidate", "invalid", "if price returns", "fails")):
            return _first_matching_phrase(raw_text, ("invalidate", "invalid", "fails"))
    elif field == "stop_loss":
        if any(token in text for token in ("stop", "sl", "below", "above")):
            return _first_matching_phrase(raw_text, ("stop", "below", "above"))
    elif field == "take_profit":
        if any(token in text for token in ("target", "tp", "rr", "risk reward")):
            return _first_matching_phrase(raw_text, ("target", "tp", "rr"))
    elif field == "risk":
        if "%" in text or "risk" in text:
            return _first_matching_phrase(raw_text, ("risk", "%"))
    elif field == "filters":
        fragments = []
        for token in ("bias", "spread", "session", "news", "volatility", "trend"):
            if token in text:
                fragments.append(token)
        if fragments:
            return ", ".join(dict.fromkeys(fragments))
    elif field == "exit_rules":
        if any(token in text for token in ("exit", "close", "trail", "partial", "runner")):
            return _first_matching_phrase(raw_text, ("exit", "close", "trail", "partial", "runner"))
    return ""


def _first_matching_phrase(raw_text: str, phrases: Iterable[str]) -> str:
    text = raw_text.lower()
    for phrase in phrases:
        idx = text.find(phrase.lower())
        if idx >= 0:
            end = min(len(raw_text), idx + max(len(phrase), 40))
            return raw_text[idx:end].strip().replace("\n", " ")
    return ""


def _find_ambiguities(raw_text: str, fields: dict[str, str]) -> list["StrategyIssue"]:
    issues: list[StrategyIssue] = []
    for field, value in fields.items():
        lowered = value.lower()
        for pattern in _AMBIGUITY_PATTERNS:
            if re.search(pattern, lowered):
                issues.append(
                    StrategyIssue(
                        code="ambiguous_rule",
                        field=field,
                        severity="MEDIUM",
                        message=f"{_FIELD_LABELS[field]} contains ambiguous wording.",
                        suggestion=f"Replace ambiguous language in {_FIELD_LABELS[field]} with a single, explicit rule.",
                    )
                )
                break
    return issues


def _find_contradictions(raw_text: str, fields: dict[str, str]) -> list["StrategyIssue"]:
    issues: list[StrategyIssue] = []
    lowered = raw_text.lower()

    if "long" in lowered and "short" in lowered:
        if "both long and short" not in lowered and "long/short" not in lowered:
            issues.append(
                StrategyIssue(
                    code="contradictory_direction",
                    field="bias",
                    severity="CRITICAL",
                    message="Strategy text mixes long and short direction without a clear rule.",
                    suggestion="Specify one direction per setup or define explicit branching rules.",
                )
            )

    for hint_field, pair in _CONTRADICTION_HINTS:
        if all(token in lowered for token in pair):
            issues.append(
                StrategyIssue(
                    code="contradictory_rule",
                    field=hint_field,
                    severity="CRITICAL",
                    message=f"Strategy text contains contradictory {hint_field} language.",
                    suggestion="Split the rule into separate cases or remove the contradiction.",
                )
            )
            break

    for field, value in fields.items():
        if "both" in value.lower() and any(token in value.lower() for token in ("long", "short", "bullish", "bearish")):
            issues.append(
                StrategyIssue(
                    code="contradictory_field",
                    field=field,
                    severity="CRITICAL",
                    message=f"{_FIELD_LABELS[field]} appears to require conflicting outcomes.",
                    suggestion=f"Rewrite {_FIELD_LABELS[field]} so it resolves to one unambiguous condition.",
                )
            )
    return issues


def _contains_placeholder_marker(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return False
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).strip().lower()
            if lowered in _PLACEHOLDER_MARKERS and _contains_placeholder_marker(item):
                return True
            if _contains_placeholder_marker(item):
                return True
        return False
    if isinstance(value, (list, tuple, set)):
        return any(_contains_placeholder_marker(item) for item in value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        return any(marker in lowered for marker in _PLACEHOLDER_MARKERS)
    return False


@dataclass
class StrategyIssue:
    code: str
    message: str
    severity: str = "HIGH"
    field: str = ""
    suggestion: str = ""


@dataclass
class StrategySpec:
    name: str | None
    raw_text: str
    fields: dict[str, str] = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)
    inferred_fields: list[str] = field(default_factory=list)


@dataclass
class StageResult:
    phase: int
    stage: str
    status: StageStatus
    issues: list[StrategyIssue] = field(default_factory=list)
    fix_instructions: list[str] = field(default_factory=list)
    next_stage: str | None = None
    can_promote: bool = False
    spec: StrategySpec | None = None
    clarifying_questions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True, default=str)


@dataclass
class RobustnessValidationInput:
    completed_successfully: bool = True
    walk_forward_passed: bool | None = None
    monte_carlo_passed: bool | None = None
    parameter_stability_passed: bool | None = None
    regime_analysis_passed: bool | None = None
    execution_cost_passed: bool | None = None
    latest_metrics: dict[str, float] = field(default_factory=dict)
    previous_metrics: dict[str, float] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)


@dataclass
class DemoValidationInput:
    completed_successfully: bool = True
    days_monitored: int | None = None
    min_demo_days: int = 14
    tolerance_pct: float = 0.05
    research_metrics: dict[str, float] = field(default_factory=dict)
    live_metrics: dict[str, float] = field(default_factory=dict)


@dataclass
class SVOSRunResult:
    strategy: str
    stages: list[StageResult] = field(default_factory=list)
    overall_status: StageStatus = "PASS"
    promoted_stage: str | None = None
    created_at: str = field(default_factory=_now)
    release: dict[str, Any] = field(default_factory=build_release_metadata)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True, default=str)


class StrategyAuditEngine:
    """Normalize and audit a raw strategy description."""

    def __init__(self, required_fields: Iterable[str] | None = None) -> None:
        self.required_fields = tuple(required_fields or _REQUIRED_FIELDS)

    def audit(self, strategy: str | dict[str, Any], strategy_name: str | None = None) -> StageResult:
        raw_text = _strategy_text(strategy)
        extracted = _extract_fields(raw_text)
        normalized_fields: dict[str, str] = {}
        inferred_fields: list[str] = []

        for field in self.required_fields:
            value = extracted.get(field, "")
            if not value:
                inferred = _infer_field_from_keywords(raw_text, field)
                if inferred:
                    value = inferred
                    inferred_fields.append(field)
            normalized_fields[field] = value.strip()

        issues: list[StrategyIssue] = []
        clarifying_questions: list[str] = []
        fix_instructions: list[str] = []
        missing_fields: list[str] = []

        for field in self.required_fields:
            if not normalized_fields[field]:
                missing_fields.append(field)
                issue = StrategyIssue(
                    code="missing_field",
                    field=field,
                    severity="HIGH",
                    message=f"Missing required field: {_FIELD_LABELS[field]}",
                    suggestion=f"Specify {_FIELD_LABELS[field]} explicitly.",
                )
                issues.append(issue)
                clarifying_questions.append(f"What is the {_FIELD_LABELS[field]}?")
                fix_instructions.append(issue.suggestion)

        issues.extend(_find_ambiguities(raw_text, normalized_fields))
        issues.extend(_find_contradictions(raw_text, normalized_fields))
        for issue in issues:
            if issue.suggestion:
                fix_instructions.append(issue.suggestion)

        if any(issue.severity == "CRITICAL" for issue in issues):
            status: StageStatus = "FAIL"
        elif issues:
            status = "FIX"
        else:
            status = "PASS"

        next_stage = "enhancement" if status in {"PASS", "FIX"} else None
        spec = StrategySpec(
            name=strategy_name,
            raw_text=raw_text,
            fields=normalized_fields,
            missing_fields=missing_fields,
            inferred_fields=inferred_fields,
        )
        metadata = {
            "required_fields": list(self.required_fields),
            "missing_count": len(missing_fields),
            "issue_count": len(issues),
            "inferred_count": len(inferred_fields),
        }
        return StageResult(
            phase=0,
            stage="audit",
            status=status,
            issues=_dedupe_issues(issues),
            fix_instructions=_dedupe_text(fix_instructions),
            next_stage=next_stage,
            can_promote=status == "PASS",
            spec=spec,
            clarifying_questions=_dedupe_text(clarifying_questions),
            metadata=metadata,
        )


def audit_strategy_text(strategy: str | dict[str, Any], strategy_name: str | None = None) -> StageResult:
    return StrategyAuditEngine().audit(strategy, strategy_name=strategy_name)


class SVOSRunner:
    """Orchestrate the strategy validation stages."""

    def __init__(
        self,
        strategy_name: str,
        registry_path: Path | str | None = None,
        output_dir: Path | str | None = None,
        validation_config: Any | None = None,
    ) -> None:
        self.strategy_name = strategy_name
        self.registry_path = Path(registry_path) if registry_path is not None else None
        self.output_dir = Path(output_dir) if output_dir is not None else _ROOT / "reports" / "svos"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.validation_config = validation_config or load_validation_config()
        self.audit_engine = StrategyAuditEngine()
        self.validation_gate = ValidationGate(self.validation_config)
        self.regression_engine = RegressionEngine(self.validation_config.regression_thresholds)

    def run_pipeline(
        self,
        strategy: str | dict[str, Any],
        replay: ReplayValidationInput | dict[str, Any] | None = None,
        backtest: BacktestValidationInput | dict[str, Any] | None = None,
        robustness: RobustnessValidationInput | dict[str, Any] | None = None,
        demo: DemoValidationInput | dict[str, Any] | None = None,
        promote: bool = False,
        allow_live_promotion: bool = False,
    ) -> SVOSRunResult:
        stages: list[StageResult] = []
        promoted_stage: str | None = None

        audit = self.audit_engine.audit(strategy, strategy_name=self.strategy_name)
        stages.append(audit)
        if audit.status != "PASS":
            return self._finish(stages, promoted_stage)

        enhancement = self._enhance(audit)
        stages.append(enhancement)
        if enhancement.status != "PASS":
            return self._finish(stages, promoted_stage)

        replay_result = self._validate_replay(replay)
        stages.append(replay_result)
        if replay_result.status != "PASS":
            return self._finish(stages, promoted_stage)
        if promote:
            self._promote("backtest")
        promoted_stage = "backtest"

        backtest_result = self._validate_backtest(backtest)
        stages.append(backtest_result)
        if backtest_result.status != "PASS":
            return self._finish(stages, promoted_stage)
        if promote:
            self._promote("walk_forward")
        promoted_stage = "walk_forward"

        robustness_result = self._validate_robustness(robustness)
        stages.append(robustness_result)
        if robustness_result.status != "PASS":
            return self._finish(stages, promoted_stage)
        if promote:
            self._promote("shadow")
        promoted_stage = "shadow"

        demo_result = self._validate_demo(demo)
        stages.append(demo_result)
        if demo_result.status != "PASS":
            return self._finish(stages, promoted_stage)
        if promote:
            self._promote("demo")
            promoted_stage = "demo"

        production_result = self._validate_production_approval(demo, allow_live_promotion=allow_live_promotion, promote=promote)
        stages.append(production_result)
        if production_result.status == "PASS" and production_result.can_promote:
            if promote and allow_live_promotion:
                self._promote("live")
                promoted_stage = "live"

        return self._finish(stages, promoted_stage)

    def _finish(self, stages: list[StageResult], promoted_stage: str | None = None) -> SVOSRunResult:
        overall = "PASS"
        for stage in stages:
            if stage.status == "FAIL":
                overall = "FAIL"
                break
            if stage.status == "FIX" and overall != "FAIL":
                overall = "FIX"
        result = SVOSRunResult(
            strategy=self.strategy_name,
            stages=stages,
            overall_status=overall,
            promoted_stage=promoted_stage,
        )
        self._write_report(result)
        return result

    def _enhance(self, audit: StageResult) -> StageResult:
        if audit.status != "PASS":
            return StageResult(
                phase=1,
                stage="enhancement",
                status=audit.status,
                issues=list(audit.issues),
                fix_instructions=list(audit.fix_instructions),
                next_stage=None,
                can_promote=False,
                spec=audit.spec,
                clarifying_questions=list(audit.clarifying_questions),
                metadata={"source_stage": "audit"},
            )
        spec = audit.spec
        assert spec is not None
        recommendations = self._suggest_enhancements(spec)
        return StageResult(
            phase=1,
            stage="enhancement",
            status="PASS",
            issues=[],
            fix_instructions=[],
            next_stage="replay",
            can_promote=True,
            spec=spec,
            clarifying_questions=[],
            metadata={
                "recommendations": recommendations,
                "source_stage": "audit",
            },
        )

    def _validate_replay(self, replay: ReplayValidationInput | dict[str, Any] | None) -> StageResult:
        if replay is None:
            return _missing_stage_result(2, "replay", "replay payload", "backtest")
        result = self.validation_gate.validate_replay(replay)
        return _stage_from_validation_result(2, "replay", result, "backtest")

    def _validate_backtest(self, backtest: BacktestValidationInput | dict[str, Any] | None) -> StageResult:
        if backtest is None:
            return _missing_stage_result(3, "backtest", "backtest payload", "walk_forward")
        result = self.validation_gate.validate_backtest(backtest)
        return _stage_from_validation_result(3, "backtest", result, "walk_forward")

    def _validate_robustness(self, robustness: RobustnessValidationInput | dict[str, Any] | None) -> StageResult:
        if robustness is None:
            return _missing_stage_result(4, "robustness", "robustness evidence", "shadow")
        data = _as_dict(robustness)
        issues: list[StrategyIssue] = []
        fix_instructions: list[str] = []

        completed = bool(data.get("completed_successfully", False))
        if not completed:
            issues.append(
                StrategyIssue(
                    code="robustness_incomplete",
                    severity="HIGH",
                    message="Robustness testing did not complete successfully.",
                    suggestion="Re-run the robustness suite and collect complete outputs.",
                )
            )

        checks = {
            "walk_forward_passed": data.get("walk_forward_passed"),
            "monte_carlo_passed": data.get("monte_carlo_passed"),
            "parameter_stability_passed": data.get("parameter_stability_passed"),
            "regime_analysis_passed": data.get("regime_analysis_passed"),
            "execution_cost_passed": data.get("execution_cost_passed"),
        }
        missing = [name for name, value in checks.items() if value is None]
        failed = [name for name, value in checks.items() if value is False]

        for name in missing:
            issues.append(
                StrategyIssue(
                    code="robustness_missing_evidence",
                    field=name,
                    severity="HIGH",
                    message=f"Missing robustness evidence: {name}",
                    suggestion=f"Provide a boolean result for {name}.",
                )
            )
            fix_instructions.append(f"Provide robustness evidence for {name}.")

        for name in failed:
            issues.append(
                StrategyIssue(
                    code="robustness_failed",
                    field=name,
                    severity="HIGH",
                    message=f"Robustness check failed: {name}",
                    suggestion=f"Fix the underlying issue causing {name} to fail, then rerun robustness testing.",
                )
            )
            fix_instructions.append(f"Resolve the failing robustness gate: {name}.")

        latest_metrics = _metric_dict(data.get("latest_metrics") or data.get("metrics") or {})
        previous_metrics = _metric_dict(data.get("previous_metrics") or {})
        if not latest_metrics or not previous_metrics:
            issues.append(
                StrategyIssue(
                    code="robustness_missing_metrics",
                    severity="HIGH",
                    message="Robustness comparison requires both latest and previous metrics.",
                    suggestion="Provide latest_metrics and previous_metrics for regression comparison.",
                )
            )
            fix_instructions.append("Provide latest and previous metrics for regression comparison.")
            regression_status = "PASS" if not latest_metrics and not previous_metrics else "FAIL"
            regression_result = None
        else:
            regression_result = self.regression_engine.compare(latest_metrics, previous_metrics)
            regression_status = regression_result.status
            if regression_status == "WARNING":
                issues.append(
                    StrategyIssue(
                        code="regression_warning",
                        severity="MEDIUM",
                        message="Regression comparison produced a warning.",
                        suggestion="Review the drift report and tighten the strategy before promotion.",
                    )
                )
                fix_instructions.append("Review regression drift before moving forward.")
            elif regression_status == "FAIL":
                issues.append(
                    StrategyIssue(
                        code="regression_fail",
                        severity="HIGH",
                        message="Regression comparison failed.",
                        suggestion="Address the regression drift before promotion.",
                    )
                )
                fix_instructions.append("Fix regression drift before continuing.")

        if any(issue.severity == "HIGH" for issue in issues):
            status: StageStatus = "FAIL" if failed or regression_status == "FAIL" or not completed else "FIX"
        elif issues:
            status = "FIX"
        else:
            status = "PASS"

        if missing:
            status = "FIX"
        if regression_status == "WARNING" and status == "PASS":
            status = "FIX"

        return StageResult(
            phase=4,
            stage="robustness",
            status=status,
            issues=_dedupe_issues(issues),
            fix_instructions=_dedupe_text(fix_instructions),
            next_stage="demo",
            can_promote=status == "PASS",
            metadata={
                "regression": regression_result.to_dict() if regression_result is not None else None,
                "completed_successfully": completed,
            },
        )

    def _validate_demo(self, demo: DemoValidationInput | dict[str, Any] | None) -> StageResult:
        if demo is None:
            return _missing_stage_result(5, "demo", "demo metrics", "production_approval")
        data = _as_dict(demo)
        issues: list[StrategyIssue] = []
        fix_instructions: list[str] = []

        completed = bool(data.get("completed_successfully", False))
        if not completed:
            issues.append(
                StrategyIssue(
                    code="demo_incomplete",
                    severity="HIGH",
                    message="Demo validation did not complete successfully.",
                    suggestion="Re-run the demo period until it completes cleanly.",
                )
            )
            fix_instructions.append("Re-run demo validation to completion.")

        days_monitored = data.get("days_monitored")
        min_demo_days = int(data.get("min_demo_days", 14))
        if days_monitored is None:
            issues.append(
                StrategyIssue(
                    code="demo_missing_days",
                    severity="HIGH",
                    message="Missing demo monitoring duration.",
                    suggestion="Provide the number of demo trading days.",
                )
            )
            fix_instructions.append("Provide demo trading duration.")
        elif int(days_monitored) < min_demo_days:
            issues.append(
                StrategyIssue(
                    code="demo_short_window",
                    severity="HIGH",
                    field="days_monitored",
                    message=f"Demo monitoring window too short: {days_monitored} days.",
                    suggestion=f"Monitor the strategy for at least {min_demo_days} days.",
                )
            )
            fix_instructions.append(f"Extend demo monitoring to at least {min_demo_days} days.")

        research_metrics = _metric_dict(data.get("research_metrics") or {})
        live_metrics = _metric_dict(data.get("live_metrics") or {})
        if not research_metrics or not live_metrics:
            issues.append(
                StrategyIssue(
                    code="demo_missing_metrics",
                    severity="HIGH",
                    message="Demo validation requires both research and live metrics.",
                    suggestion="Provide comparable research_metrics and live_metrics.",
                )
            )
            fix_instructions.append("Provide both research and live metrics.")
        else:
            tolerance = float(data.get("tolerance_pct", 0.05))
            for metric in ("profit_factor", "win_rate", "expectancy"):
                if metric in research_metrics and metric in live_metrics:
                    research = float(research_metrics[metric])
                    live = float(live_metrics[metric])
                    if research == 0:
                        continue
                    delta_pct = abs(live - research) / abs(research)
                    if delta_pct > tolerance:
                        issues.append(
                            StrategyIssue(
                                code="demo_metric_drift",
                                field=metric,
                                severity="HIGH",
                                message=f"{metric} drift exceeds tolerance: {delta_pct:.2%} > {tolerance:.2%}.",
                                suggestion=f"Reduce drift in {metric} before promoting to live.",
                            )
                        )
                        fix_instructions.append(f"Bring {metric} drift within {tolerance:.2%}.")
            if "max_drawdown" in research_metrics and "max_drawdown" in live_metrics:
                research = float(research_metrics["max_drawdown"])
                live = float(live_metrics["max_drawdown"])
                if research > 0:
                    delta_pct = abs(live - research) / abs(research)
                    if delta_pct > tolerance:
                        issues.append(
                            StrategyIssue(
                                code="demo_drawdown_drift",
                                field="max_drawdown",
                                severity="HIGH",
                                message=f"max_drawdown drift exceeds tolerance: {delta_pct:.2%} > {tolerance:.2%}.",
                                suggestion="Reduce live drawdown drift before promotion.",
                            )
                        )
                        fix_instructions.append("Bring max_drawdown drift within tolerance.")

        if any(issue.severity == "HIGH" for issue in issues):
            status: StageStatus = "FAIL"
        elif issues:
            status = "FIX"
        else:
            status = "PASS"

        return StageResult(
            phase=5,
            stage="demo",
            status=status,
            issues=_dedupe_issues(issues),
            fix_instructions=_dedupe_text(fix_instructions),
            next_stage="production_approval",
            can_promote=status == "PASS",
            metadata={
                "days_monitored": days_monitored,
                "min_demo_days": min_demo_days,
                "research_metrics": research_metrics,
                "live_metrics": live_metrics,
            },
        )

    def _validate_production_approval(
        self,
        demo: DemoValidationInput | dict[str, Any] | None,
        *,
        allow_live_promotion: bool,
        promote: bool,
    ) -> StageResult:
        approved = can_deploy_strategy(self.strategy_name, target_stage="demo", path=self.registry_path)
        demo_payload = _as_dict(demo)
        has_placeholder = _contains_placeholder_marker(demo_payload)
        live_guard_blocked = not allow_live_promotion or not promote or has_placeholder
        blocking_reasons: list[str] = []
        if not allow_live_promotion:
            blocking_reasons.append("Missing explicit --allow-live-promotion flag.")
        if not promote:
            blocking_reasons.append("Pipeline promotion is disabled.")
        if has_placeholder:
            blocking_reasons.append("Demo payload contains synthetic/sample/example placeholder markers.")
        if approved:
            return StageResult(
                phase=6,
                stage="production_approval",
                status="PASS",
                issues=[],
                fix_instructions=[],
                next_stage=None,
                can_promote=approved and not live_guard_blocked,
                metadata={
                    "registry_approved": True,
                    "live_promotion_allowed": approved and not live_guard_blocked,
                    "live_promotion_guard": {
                        "blocked": live_guard_blocked,
                        "reasons": blocking_reasons,
                        "placeholder_detected": has_placeholder,
                    },
                },
            )
        return StageResult(
            phase=6,
            stage="production_approval",
            status="FAIL",
            issues=[
                StrategyIssue(
                    code="registry_blocked",
                    severity="HIGH",
                    message="Strategy is not approved for live deployment in the registry.",
                    suggestion="Update the strategy manifest so approved=true and status is at least demo.",
                )
            ],
            fix_instructions=[
                "Approve the strategy in the registry.",
                "Ensure the manifest status is at least demo before requesting live deployment.",
            ],
            next_stage=None,
            can_promote=False,
            metadata={"registry_approved": False, "live_promotion_allowed": False, "live_promotion_guard": {"blocked": True, "reasons": blocking_reasons}},
        )

    def _promote(self, stage: str) -> None:
        promote_strategy_stage(self.strategy_name, stage, path=self.registry_path)

    def _suggest_enhancements(self, spec: StrategySpec) -> list[str]:
        suggestions = []
        if spec.inferred_fields:
            suggestions.append(
                "Review inferred fields and convert them into explicit template values before replay."
            )
        if spec.missing_fields:
            suggestions.append("Fill all required template fields before moving to replay.")
        suggestions.append("Prefer reusable blocks: sweep, CHoCH, BOS, FVG, risk, and session filters.")
        return suggestions

    def _write_report(self, result: SVOSRunResult) -> None:
        report_dir = self.output_dir / result.strategy
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "svos_result.json").write_text(result.to_json(), encoding="utf-8")
        (report_dir / "svos_result.md").write_text(_render_markdown(result), encoding="utf-8")


def _stage_from_validation_result(
    phase: int,
    stage: str,
    result: ValidationResult,
    next_stage: str,
) -> StageResult:
    issues: list[StrategyIssue] = []
    fix_instructions: list[str] = []
    for check in result.checks:
        if check.passed:
            continue
        severity = "HIGH" if check.severity == "ERROR" else check.severity
        issues.append(
            StrategyIssue(
                code=check.name,
                severity=severity,
                message=check.message,
                suggestion=f"Resolve {check.name}: {check.message}",
            )
        )
        fix_instructions.append(check.message)

    if result.status == "PASS":
        status: StageStatus = "PASS"
    elif result.status == "WARNING":
        status = "FIX"
    else:
        status = "FAIL"

    return StageResult(
        phase=phase,
        stage=stage,
        status=status,
        issues=_dedupe_issues(issues),
        fix_instructions=_dedupe_text(fix_instructions),
        next_stage=next_stage if status == "PASS" else None,
        can_promote=status == "PASS",
        metadata={"validation": result.to_dict()},
    )


def _missing_stage_result(phase: int, stage: str, what: str, next_stage: str) -> StageResult:
    return StageResult(
        phase=phase,
        stage=stage,
        status="FIX",
        issues=[
            StrategyIssue(
                code="missing_input",
                severity="HIGH",
                message=f"Missing required input for {stage}: {what}.",
                suggestion=f"Provide {what} before rerunning the {stage} stage.",
            )
        ],
        fix_instructions=[f"Provide {what} before rerunning the {stage} stage."],
        next_stage=next_stage,
        can_promote=False,
    )


def _strategy_text(strategy: str | dict[str, Any]) -> str:
    if isinstance(strategy, str):
        return strategy
    if isinstance(strategy, dict):
        if "text" in strategy:
            return _clean_text(strategy["text"])
        if "strategy_text" in strategy:
            return _clean_text(strategy["strategy_text"])
        return json.dumps(strategy, indent=2, sort_keys=True, default=str)
    return _clean_text(strategy)


def _metric_dict(value: Any) -> dict[str, float]:
    if not value:
        return {}
    if isinstance(value, dict):
        out: dict[str, float] = {}
        for key, raw in value.items():
            try:
                out[str(key)] = float(raw)
            except (TypeError, ValueError):
                continue
        return out
    return {}


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    raise TypeError(f"Unsupported SVOS payload type: {type(value)!r}")


def _dedupe_text(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def _dedupe_issues(values: Iterable[StrategyIssue]) -> list[StrategyIssue]:
    seen: set[tuple[str, str, str]] = set()
    out: list[StrategyIssue] = []
    for issue in values:
        key = (issue.code, issue.field, issue.message)
        if key in seen:
            continue
        seen.add(key)
        out.append(issue)
    return out


def _render_markdown(result: SVOSRunResult) -> str:
    lines = [
        f"# SVOS Result - {result.strategy}",
        "",
        f"- Overall Status: **{result.overall_status}**",
        f"- Promoted Stage: `{result.promoted_stage or 'n/a'}`",
        f"- Timestamp: `{result.created_at}`",
    ]
    for stage in result.stages:
        lines.extend(
            [
                "",
                f"## {stage.stage.title()}",
                f"- Phase: `{stage.phase}`",
                f"- Status: **{stage.status}**",
                f"- Next Stage: `{stage.next_stage or 'n/a'}`",
                f"- Can Promote: `{str(stage.can_promote).lower()}`",
            ]
        )
        if stage.clarifying_questions:
            lines.append("- Clarifying Questions:")
            for question in stage.clarifying_questions:
                lines.append(f"  - {question}")
        if stage.fix_instructions:
            lines.append("- Fix Instructions:")
            for item in stage.fix_instructions:
                lines.append(f"  - {item}")
        if stage.issues:
            lines.append("- Issues:")
            for issue in stage.issues:
                lines.append(f"  - {issue.severity}: {issue.message}")
    return "\n".join(lines) + "\n"

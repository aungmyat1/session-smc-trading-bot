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

from core.strategy_registry import DirectCatalogMutationError, can_deploy_strategy, get_strategy_manifest
from execution_validation.engine import ExecutionValidationReport
from research.regression.engine import RegressionEngine
from research.validation.engine import (
    BacktestValidationInput,
    ReplayValidationInput,
    ValidationGate,
    ValidationResult,
    load_validation_config,
)
from research.lineage import build_release_metadata
from strategy_validation.ai.editor_engine import StrategyEditorEngine
from strategy_validation.models import StrategyDocument as ValidationStrategyDocument
from strategy_validation.models import ValidationRecommendation, ValidationReport as StrategyValidationReport
from strategy_validation.pipeline.strategy_validation_pipeline import StrategyValidationPipeline
from svos.orchestration import SVOSPlatform
from svos.registry import StrategyRegistryService
from svos.reports.stage_package import write_stage_report_package

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

_DATA_REQUIREMENT_KEYWORDS = {
    "order_book": ("order book", "orderbook", "dom"),
    "volume_profile": ("volume profile", "vp"),
    "tick_volume": ("tick volume", "tick data", "volume"),
    "ohlc": ("ohlc", "candles", "bars"),
}

_OVERFIT_PARAMETER_PATTERNS = (
    r"\b(?:ema|sma|rsi|atr|macd|lookback|period|window|length|threshold|stop|target)\s*[:=]\s*\d+(?:\.\d+)?%?",
    r"\b\d+(?:\.\d+)?%?\b",
)


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
    for fname, value in fields.items():
        lowered = value.lower()
        for pattern in _AMBIGUITY_PATTERNS:
            if re.search(pattern, lowered):
                issues.append(
                    StrategyIssue(
                        code="ambiguous_rule",
                        field=fname,
                        severity="MEDIUM",
                        message=f"{_FIELD_LABELS[fname]} contains ambiguous wording.",
                        suggestion=f"Replace ambiguous language in {_FIELD_LABELS[fname]} with a single, explicit rule.",
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

    for fname, value in fields.items():
        if "both" in value.lower() and any(token in value.lower() for token in ("long", "short", "bullish", "bearish")):
            issues.append(
                StrategyIssue(
                    code="contradictory_field",
                    field=fname,
                    severity="CRITICAL",
                    message=f"{_FIELD_LABELS[fname]} appears to require conflicting outcomes.",
                    suggestion=f"Rewrite {_FIELD_LABELS[fname]} so it resolves to one unambiguous condition.",
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


def _infer_required_data(raw_text: str) -> list[str]:
    lowered = raw_text.lower()
    matches: list[str] = []
    for canonical, tokens in _DATA_REQUIREMENT_KEYWORDS.items():
        if any(token in lowered for token in tokens):
            matches.append(canonical)
    return list(dict.fromkeys(matches))


def _normalize_data_tokens(values: Iterable[Any]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        token = str(value).strip().lower().replace(" ", "_")
        if not token:
            continue
        normalized.append(token)
    return list(dict.fromkeys(normalized))


def _detect_overfitting(raw_text: str) -> tuple[bool, dict[str, Any]]:
    numeric_literals = re.findall(_OVERFIT_PARAMETER_PATTERNS[1], raw_text)
    fixed_parameter_matches = re.findall(_OVERFIT_PARAMETER_PATTERNS[0], raw_text.lower())
    score = len(numeric_literals) + len(fixed_parameter_matches)
    detected = score >= 8
    return detected, {
        "numeric_literal_count": len(numeric_literals),
        "fixed_parameter_count": len(fixed_parameter_matches),
        "score": score,
        "threshold": 8,
    }


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
    required_data: list[str] = field(default_factory=list)
    available_data: list[str] = field(default_factory=list)


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
    out_of_sample_passed: bool | None = None
    stress_test_passed: bool | None = None
    instrument_test_passed: bool | None = None
    market_regime_passed: bool | None = None
    latest_metrics: dict[str, float] = field(default_factory=dict)
    previous_metrics: dict[str, float] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)


@dataclass
class VirtualDemoValidationInput:
    completed_successfully: bool = True
    days_monitored: int | None = None
    min_demo_days: int = 14
    tolerance_pct: float = 0.05
    research_metrics: dict[str, float] = field(default_factory=dict)
    live_metrics: dict[str, float] = field(default_factory=dict)
    execution_validation_report: ExecutionValidationReport | dict[str, Any] | None = None
    require_ready_for_demo: bool = True
    expected_signals: int | None = None
    observed_signals: int | None = None
    expected_trades: int | None = None
    observed_trades: int | None = None
    execution_metrics: dict[str, float] = field(default_factory=dict)
    order_outcomes: dict[str, int] = field(default_factory=dict)
    risk_controls: dict[str, bool] = field(default_factory=dict)
    broker_comparison: dict[str, Any] = field(default_factory=dict)


DemoValidationInput = VirtualDemoValidationInput


@dataclass
class SVOSRunResult:
    strategy: str
    stages: list[StageResult] = field(default_factory=list)
    overall_status: StageStatus = "PASS"
    promoted_stage: str | None = None
    created_at: str = field(default_factory=_now)
    release: dict[str, Any] = field(default_factory=build_release_metadata)
    canonical_report: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True, default=str)


class StrategyValidationAuditAdapter:
    """Bridge the canonical Stage 1 validator into the legacy SVOS stage model."""

    def __init__(self, pipeline: StrategyValidationPipeline | None = None) -> None:
        self.pipeline = pipeline or StrategyValidationPipeline()

    def audit(self, strategy: str | dict[str, Any], strategy_name: str | None = None) -> StageResult:
        raw_text = _strategy_text(strategy)
        document = ValidationStrategyDocument.from_text(raw_text)
        strategy_label = strategy_name or document.strategy_name or _extract_strategy_name(strategy) or "UNNAMED"
        report = self.pipeline.run_text(raw_text)
        spec = _strategy_spec_from_validation_document(document, strategy_label, strategy, report)
        issues = _strategy_issues_from_validation_report(report)
        fix_instructions = _fix_instructions_from_validation_report(report)
        clarifying_questions = _clarifying_questions_from_validation_report(report)
        status = _stage_status_from_validation_report(report)
        next_stage = "enhancement" if status == "PASS" else None
        return StageResult(
            phase=1,
            stage="audit",
            status=status,
            issues=issues,
            fix_instructions=fix_instructions,
            next_stage=next_stage,
            can_promote=status == "PASS",
            spec=spec,
            clarifying_questions=clarifying_questions,
            metadata={
                "validation_report": report.to_dict(),
                "readiness_decision": report.readiness_decision,
                "overall_score": report.overall_score,
                "warning_count": len(report.warnings),
                "critical_issue_count": len(report.critical_issues),
            },
        )


class StrategyAuditEngine:
    """Normalize and audit a raw strategy description."""

    def __init__(self, required_fields: Iterable[str] | None = None) -> None:
        self.required_fields = tuple(required_fields or _REQUIRED_FIELDS)

    def audit(self, strategy: str | dict[str, Any], strategy_name: str | None = None) -> StageResult:
        raw_text = _strategy_text(strategy)
        extracted = _extract_fields(raw_text)
        normalized_fields: dict[str, str] = {}
        inferred_fields: list[str] = []
        available_data: list[str] = []
        required_data: list[str] = []

        if isinstance(strategy, dict):
            available_data = _normalize_data_tokens(strategy.get("available_data", []))
            required_data = _normalize_data_tokens(strategy.get("required_data", []))

        for fname in self.required_fields:
            value = extracted.get(fname, "")
            if not value:
                inferred = _infer_field_from_keywords(raw_text, fname)
                if inferred:
                    value = inferred
                    inferred_fields.append(fname)
            normalized_fields[fname] = value.strip()

        issues: list[StrategyIssue] = []
        clarifying_questions: list[str] = []
        fix_instructions: list[str] = []
        missing_fields: list[str] = []

        for fname in self.required_fields:
            if not normalized_fields[fname]:
                missing_fields.append(fname)
                issue = StrategyIssue(
                    code="missing_field",
                    field=fname,
                    severity="HIGH",
                    message=f"Missing required field: {_FIELD_LABELS[fname]}",
                    suggestion=f"Specify {_FIELD_LABELS[fname]} explicitly.",
                )
                issues.append(issue)
                clarifying_questions.append(f"What is the {_FIELD_LABELS[fname]}?")
                fix_instructions.append(issue.suggestion)

        issues.extend(_find_ambiguities(raw_text, normalized_fields))
        issues.extend(_find_contradictions(raw_text, normalized_fields))
        for issue in issues:
            if issue.suggestion:
                fix_instructions.append(issue.suggestion)

        detected_required_data = required_data or _infer_required_data(raw_text)
        data_availability_status = "NOT_VERIFIED" if detected_required_data and not available_data else "VERIFIED"
        if detected_required_data and available_data:
            missing_data = [item for item in detected_required_data if item not in available_data]
            if missing_data:
                issues.append(
                    StrategyIssue(
                        code="missing_data",
                        severity="CRITICAL",
                        field="available_data",
                        message="Strategy requires data that is not listed as available.",
                        suggestion="Either supply the missing data or remove the dependency from the strategy spec.",
                    )
                )
                fix_instructions.append("Provide all required market data before testing.")
                data_availability_status = "MISSING"

        overfit_detected, overfit_meta = _detect_overfitting(raw_text)
        if overfit_detected:
            issues.append(
                StrategyIssue(
                    code="possible_overfitting",
                    severity="MEDIUM",
                    message="Strategy contains many fixed numeric parameters and may be overfit.",
                    suggestion="Simplify fixed parameters or validate the ranges across multiple datasets.",
                )
            )
            fix_instructions.append("Review fixed numeric parameters for overfitting risk.")

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
            required_data=detected_required_data,
            available_data=available_data,
        )
        metadata = {
            "required_fields": list(self.required_fields),
            "missing_count": len(missing_fields),
            "issue_count": len(issues),
            "inferred_count": len(inferred_fields),
            "data_availability": {
                "status": data_availability_status,
                "required": detected_required_data,
                "available": available_data,
            },
            "overfitting": overfit_meta | {"detected": overfit_detected},
        }
        return StageResult(
            phase=1,
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


class StrategyIntakeEngine:
    """Normalize raw strategy input into a canonical intake record."""

    def intake(self, strategy: str | dict[str, Any], strategy_name: str | None = None) -> StageResult:
        raw_text = _strategy_text(strategy)
        if not raw_text.strip():
            return StageResult(
                phase=0,
                stage="intake",
                status="FAIL",
                issues=[
                    StrategyIssue(
                        code="missing_strategy_text",
                        severity="CRITICAL",
                        message="Strategy intake did not receive any strategy text.",
                        suggestion="Provide a markdown, text, JSON, YAML, or code-backed strategy description.",
                    )
                ],
                fix_instructions=["Provide a non-empty strategy description before intake."],
                next_stage=None,
                can_promote=False,
                metadata={"source_type": _detect_source_type(strategy)},
            )

        canonical_name = strategy_name or _extract_strategy_name(strategy) or "UNNAMED"
        canonical_fields = _extract_fields(raw_text)
        source_type = _detect_source_type(strategy)
        intake_metadata = {
            "strategy_id": _strategy_id(canonical_name, raw_text),
            "strategy_name": canonical_name,
            "version": "1.0",
            "source_type": source_type,
            "canonical_spec": {
                "name": canonical_name,
                "raw_text": raw_text,
                "fields": canonical_fields,
            },
            "version_history_initialized": True,
            "normalized_terms": sorted(canonical_fields.keys()),
        }
        return StageResult(
            phase=0,
            stage="intake",
            status="PASS",
            issues=[],
            fix_instructions=[],
            next_stage="audit",
            can_promote=True,
            metadata=intake_metadata,
        )


class SVOSRunner:
    """Orchestrate the strategy validation stages."""

    def __init__(
        self,
        strategy_name: str,
        registry_path: Path | str | None = None,
        output_dir: Path | str | None = None,
        canonical_output_dir: Path | str | None = None,
        validation_config: Any | None = None,
    ) -> None:
        self.strategy_name = strategy_name
        self.registry_path = Path(registry_path) if registry_path is not None else None
        self.output_dir = Path(output_dir) if output_dir is not None else _ROOT / "reports" / "svos"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.validation_config = validation_config or load_validation_config()
        self.intake_engine = StrategyIntakeEngine()
        self.audit_engine = StrategyValidationAuditAdapter()
        self.editor_engine = StrategyEditorEngine()
        self.validation_gate = ValidationGate(self.validation_config)
        self.regression_engine = RegressionEngine(self.validation_config.regression_thresholds)
        self._run_strategy_text = ""
        self._run_input_payloads: dict[str, Any] = {}
        self._strategy_id = re.sub(r"[^A-Za-z0-9]+", "-", strategy_name.strip().upper()).strip("-") or "UNNAMED"
        self._strategy_version = "0.0.0"
        self._previous_version: str | None = None
        self._platform: SVOSPlatform | None = None
        self._canonical_output_dir = (
            Path(canonical_output_dir)
            if canonical_output_dir is not None
            else self._resolve_canonical_output_dir()
        )

    def run_pipeline(
        self,
        strategy: str | dict[str, Any],
        replay: ReplayValidationInput | dict[str, Any] | None = None,
        backtest: BacktestValidationInput | dict[str, Any] | None = None,
        robustness: RobustnessValidationInput | dict[str, Any] | None = None,
        virtual_demo: VirtualDemoValidationInput | dict[str, Any] | None = None,
        demo: DemoValidationInput | dict[str, Any] | None = None,
        promote: bool = False,
        allow_live_promotion: bool = False,
        stop_after: str | None = None,
        stage_observer: Any | None = None,
    ) -> SVOSRunResult:
        stages: list[StageResult] = []
        promoted_stage: str | None = None
        self._prepare_run(
            strategy,
            replay=replay,
            backtest=backtest,
            robustness=robustness,
            virtual_demo=virtual_demo if virtual_demo is not None else demo,
        )

        intake = self.intake_engine.intake(strategy, strategy_name=self.strategy_name)
        stages.append(intake)
        self._write_stage_report(stages, promoted_stage)
        self._notify_stage_observer(stage_observer, stages, promoted_stage)
        if intake.status != "PASS":
            return self._finish(stages, promoted_stage)
        if stop_after == "intake":
            return self._finish(stages, promoted_stage)

        audit = self.audit_engine.audit(strategy, strategy_name=self.strategy_name)
        stages.append(audit)
        self._write_stage_report(stages, promoted_stage)
        self._notify_stage_observer(stage_observer, stages, promoted_stage)
        if stop_after == "audit":
            return self._finish(stages, promoted_stage)

        enhancement = self._enhance(audit)
        stages.append(enhancement)
        self._write_stage_report(stages, promoted_stage)
        self._notify_stage_observer(stage_observer, stages, promoted_stage)
        if audit.status != "PASS":
            return self._finish(stages, promoted_stage)
        if enhancement.status != "PASS":
            return self._finish(stages, promoted_stage)
        if stop_after == "enhancement":
            return self._finish(stages, promoted_stage)

        replay_result = self._validate_replay(replay)
        stages.append(replay_result)
        self._write_stage_report(stages, promoted_stage)
        self._notify_stage_observer(stage_observer, stages, promoted_stage)
        if replay_result.status != "PASS":
            return self._finish(stages, promoted_stage)
        if stop_after == "replay":
            return self._finish(stages, promoted_stage)
        if promote:
            self._promote("backtest")
            promoted_stage = "backtest"
            self._write_stage_report(stages, promoted_stage)
            self._notify_stage_observer(stage_observer, stages, promoted_stage)

        backtest_result = self._validate_backtest(backtest)
        stages.append(backtest_result)
        self._write_stage_report(stages, promoted_stage)
        self._notify_stage_observer(stage_observer, stages, promoted_stage)
        if backtest_result.status != "PASS":
            return self._finish(stages, promoted_stage)
        if stop_after == "backtest":
            return self._finish(stages, promoted_stage)
        if promote:
            self._promote("walk_forward")
            promoted_stage = "walk_forward"
            self._write_stage_report(stages, promoted_stage)
            self._notify_stage_observer(stage_observer, stages, promoted_stage)

        robustness_result = self._validate_robustness(robustness)
        stages.append(robustness_result)
        self._write_stage_report(stages, promoted_stage)
        self._notify_stage_observer(stage_observer, stages, promoted_stage)
        if robustness_result.status != "PASS":
            return self._finish(stages, promoted_stage)
        if stop_after == "robustness":
            return self._finish(stages, promoted_stage)
        if promote:
            self._promote("shadow")
            promoted_stage = "shadow"
            self._write_stage_report(stages, promoted_stage)
            self._notify_stage_observer(stage_observer, stages, promoted_stage)

        verification_ready = self._build_verification_ready(stages)
        stages.append(verification_ready)
        self._write_stage_report(stages, promoted_stage)
        self._notify_stage_observer(stage_observer, stages, promoted_stage)
        if verification_ready.status != "PASS":
            return self._finish(stages, promoted_stage)
        if stop_after == "verification_ready":
            return self._finish(stages, promoted_stage)

        virtual_demo_payload = virtual_demo if virtual_demo is not None else demo
        demo_result = self._validate_virtual_demo(virtual_demo_payload)
        stages.append(demo_result)
        self._write_stage_report(stages, promoted_stage)
        self._notify_stage_observer(stage_observer, stages, promoted_stage)
        if demo_result.status != "PASS":
            return self._finish(stages, promoted_stage)
        if stop_after == "virtual_demo" or not promote:
            return self._finish(stages, promoted_stage)
        if promote:
            self._promote("demo")
            promoted_stage = "demo"
            self._write_stage_report(stages, promoted_stage)
            self._notify_stage_observer(stage_observer, stages, promoted_stage)

        production_result = self._validate_production_approval(virtual_demo_payload, allow_live_promotion=allow_live_promotion, promote=promote)
        stages.append(production_result)
        self._write_stage_report(stages, promoted_stage)
        self._notify_stage_observer(stage_observer, stages, promoted_stage)
        if production_result.status == "PASS" and production_result.can_promote:
            if promote and allow_live_promotion:
                self._promote("live")
                promoted_stage = "live"
                self._write_stage_report(stages, promoted_stage)
                self._notify_stage_observer(stage_observer, stages, promoted_stage)

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
        result.canonical_report = self._write_canonical_report_package(result)
        self._write_report(result)
        return result

    def _resolve_project_root(self) -> Path:
        if self.registry_path is None:
            return _ROOT
        parent = self.registry_path.resolve().parent
        return parent.parent if parent.name == "config" else parent

    def _resolve_canonical_output_dir(self) -> Path:
        project_root = self._resolve_project_root()
        try:
            self.output_dir.resolve().relative_to(_ROOT.resolve())
        except ValueError:
            return project_root / "reports" / "svos"
        return _ROOT / "reports" / "svos"

    def _prepare_run(self, strategy: str | dict[str, Any], **payloads: Any) -> None:
        self._run_strategy_text = _strategy_text(strategy)
        self._run_input_payloads = {name: _as_dict(value) if value is not None else None for name, value in payloads.items()}
        catalog_path = self.registry_path or (_ROOT / "config" / "strategy_catalog.yaml")
        manifest = get_strategy_manifest(self.strategy_name, catalog_path)
        if manifest is None:
            return
        project_root = self._resolve_project_root()
        registry = StrategyRegistryService(root=project_root, catalog_path=catalog_path)
        versions_before = registry.versions(self.strategy_name)
        version = registry.ensure_spec_version(
            self.strategy_name,
            specification=self._run_strategy_text,
            actor="svos",
            reason="SVOS strategy specification snapshot",
        )
        self._strategy_id = str(version.manifest.get("strategy_id", self._strategy_id))
        self._strategy_version = version.version
        if versions_before:
            previous = str(versions_before[-1].get("version", ""))
            self._previous_version = previous or None
        self._platform = SVOSPlatform(root=project_root, catalog_path=catalog_path, registry=registry)

    def _validation_config_snapshot(self) -> dict[str, Any]:
        return {
            "minimum_trade_count": self.validation_config.minimum_trade_count,
            "minimum_profit_factor": self.validation_config.minimum_profit_factor,
            "maximum_drawdown": self.validation_config.maximum_drawdown,
            "minimum_expectancy": self.validation_config.minimum_expectancy,
            "regression_thresholds": self.validation_config.regression_thresholds,
        }

    def _write_canonical_report_package(self, result: SVOSRunResult) -> dict[str, Any]:
        package = write_stage_report_package(
            output_root=self._canonical_output_dir,
            strategy_name=self.strategy_name,
            strategy_id=self._strategy_id,
            strategy_version=self._strategy_version,
            strategy_text=self._run_strategy_text,
            stages=result.stages,
            promoted_stage=result.promoted_stage,
            validation_config=self._validation_config_snapshot(),
            input_payloads=self._run_input_payloads,
            release=result.release,
            previous_version=self._previous_version,
        )
        artifacts = [
            {
                "stage": "run_summary",
                "status": result.overall_status,
                "json_path": str(package.summary_json),
                "markdown_path": str(package.summary_markdown),
            }
        ]
        artifacts.extend(
            {
                "stage": item["stage"],
                "status": item["status"],
                "json_path": item["json_path"],
                "markdown_path": item["markdown_path"],
            }
            for item in package.stage_artifacts
        )
        artifacts.extend(
            {
                "stage": item["report_type"],
                "status": result.overall_status,
                "json_path": item["json_path"],
                "markdown_path": item["markdown_path"],
            }
            for item in package.supporting_artifacts
        )
        if self._platform is not None:
            for artifact in artifacts:
                for report_type, path_key in (("json", "json_path"), ("markdown", "markdown_path")):
                    self._platform.record_report_evidence(
                        strategy=self.strategy_name,
                        stage=artifact["stage"],
                        service="svos",
                        report_type=report_type,
                        artifact_path=artifact[path_key],
                        status=artifact["status"],
                        metadata={
                            "run_id": package.run_id,
                            "strategy_id": package.strategy_id,
                            "strategy_version": package.strategy_version,
                        },
                    )
        return {
            "run_id": package.run_id,
            "strategy_id": package.strategy_id,
            "strategy_version": package.strategy_version,
            "report_dir": str(package.report_dir),
            "summary_json": str(package.summary_json),
            "summary_markdown": str(package.summary_markdown),
        }

    def _enhance(self, audit: StageResult) -> StageResult:
        spec = audit.spec
        validation_report = audit.metadata.get("validation_report", {})
        validation_recommendations = list(validation_report.get("recommendations", []))
        document = ValidationStrategyDocument.from_text(spec.raw_text if spec is not None else "", source_path="")
        enhancement_plan = self.editor_engine.build_plan(
            document,
            [_validation_recommendation_from_dict(item) for item in validation_recommendations if isinstance(item, dict)],
            str(audit.metadata.get("readiness_decision", "")),
        )
        if audit.status != "PASS":
            return StageResult(
                phase=2,
                stage="enhancement",
                status="FIX" if enhancement_plan.questions else audit.status,
                issues=list(audit.issues),
                fix_instructions=_dedupe_text(list(audit.fix_instructions) + [item.proposed_revision for item in enhancement_plan.questions if item.proposed_revision]),
                next_stage=None,
                can_promote=False,
                spec=spec,
                clarifying_questions=_dedupe_text(list(audit.clarifying_questions) + [item.prompt for item in enhancement_plan.questions]),
                metadata={"source_stage": "audit", "enhancement_plan": enhancement_plan.to_dict()},
            )
        assert spec is not None
        recommendations = _dedupe_text(
            [str(item.get("message", "")).strip() for item in validation_recommendations if isinstance(item, dict)]
            + self._suggest_enhancements(spec)
        )
        return StageResult(
            phase=2,
            stage="enhancement",
            status="PASS",
            issues=[],
            fix_instructions=[],
            next_stage="replay",
            can_promote=True,
            spec=spec,
            clarifying_questions=[item.prompt for item in enhancement_plan.questions],
            metadata={
                "recommendations": recommendations,
                "source_stage": "audit",
                "audit_readiness_decision": audit.metadata.get("readiness_decision", ""),
                "enhancement_plan": enhancement_plan.to_dict(),
            },
        )

    def _validate_replay(self, replay: ReplayValidationInput | dict[str, Any] | None) -> StageResult:
        if replay is None:
            return _missing_stage_result(3, "replay", "replay payload", "backtest")
        result = self.validation_gate.validate_replay(replay)
        return _stage_from_validation_result(3, "replay", result, "backtest")

    def _validate_backtest(self, backtest: BacktestValidationInput | dict[str, Any] | None) -> StageResult:
        if backtest is None:
            return _missing_stage_result(4, "backtest", "backtest payload", "walk_forward")
        result = self.validation_gate.validate_backtest(backtest)
        return _stage_from_validation_result(4, "backtest", result, "walk_forward")

    def _validate_robustness(self, robustness: RobustnessValidationInput | dict[str, Any] | None) -> StageResult:
        if robustness is None:
            return _missing_stage_result(5, "robustness", "robustness evidence", "shadow")
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
        optional_checks = {
            "out_of_sample_passed": data.get("out_of_sample_passed"),
            "stress_test_passed": data.get("stress_test_passed"),
            "instrument_test_passed": data.get("instrument_test_passed"),
            "market_regime_passed": data.get("market_regime_passed"),
        }
        optional_missing = [name for name, value in optional_checks.items() if value is None]
        optional_failed = [name for name, value in optional_checks.items() if value is False]

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

        if optional_failed:
            for name in optional_failed:
                issues.append(
                    StrategyIssue(
                        code="robustness_optional_failed",
                        field=name,
                        severity="HIGH",
                        message=f"Optional robustness check failed: {name}",
                        suggestion=f"Fix the issue behind {name} before promotion.",
                    )
                )
                fix_instructions.append(f"Resolve optional robustness evidence: {name}.")
            if status == "PASS":
                status = "FAIL"

        return StageResult(
            phase=5,
            stage="robustness",
            status=status,
            issues=_dedupe_issues(issues),
            fix_instructions=_dedupe_text(fix_instructions),
            next_stage="virtual_demo",
            can_promote=status == "PASS",
            metadata={
                "regression": regression_result.to_dict() if regression_result is not None else None,
                "completed_successfully": completed,
                "checks": checks,
                "optional_checks": optional_checks,
                "optional_missing": optional_missing,
                "optional_failed": optional_failed,
            },
        )

    def _validate_virtual_demo(self, virtual_demo: VirtualDemoValidationInput | dict[str, Any] | None) -> StageResult:
        if virtual_demo is None:
            return _missing_stage_result(7, "virtual_demo", "virtual demo evidence", "production_approval")
        data = _as_dict(virtual_demo)
        issues: list[StrategyIssue] = []
        fix_instructions: list[str] = []

        completed = bool(data.get("completed_successfully", False))
        if not completed:
            issues.append(
                StrategyIssue(
                    code="virtual_demo_incomplete",
                    severity="HIGH",
                    message="Virtual demo validation did not complete successfully.",
                    suggestion="Re-run the virtual demo period until it completes cleanly.",
                )
            )
            fix_instructions.append("Re-run virtual demo validation to completion.")

        days_monitored = data.get("days_monitored")
        min_demo_days = int(data.get("min_demo_days", 14))
        if days_monitored is None:
            issues.append(
                StrategyIssue(
                    code="virtual_demo_missing_days",
                    severity="HIGH",
                    message="Missing virtual demo monitoring duration.",
                    suggestion="Provide the number of virtual demo trading days.",
                )
            )
            fix_instructions.append("Provide virtual demo trading duration.")
        elif int(days_monitored) < min_demo_days:
            issues.append(
                StrategyIssue(
                    code="virtual_demo_short_window",
                    severity="HIGH",
                    field="days_monitored",
                    message=f"Virtual demo monitoring window too short: {days_monitored} days.",
                    suggestion=f"Monitor the strategy for at least {min_demo_days} days.",
                )
            )
            fix_instructions.append(f"Extend virtual demo monitoring to at least {min_demo_days} days.")

        execution_report = _as_dict(data.get("execution_validation_report"))
        if not execution_report:
            issues.append(
                StrategyIssue(
                    code="virtual_demo_missing_execution_report",
                    severity="HIGH",
                    message="Virtual demo requires an execution validation report from the virtual broker process.",
                    suggestion="Run execution validation against the virtual broker and attach the report.",
                )
            )
            fix_instructions.append("Attach the virtual broker execution validation report.")
        else:
            execution_status = str(execution_report.get("status", "")).upper()
            readiness_status = str(execution_report.get("readiness_status", "")).upper()
            final_score = int(execution_report.get("final_score", 0) or 0)
            broker_simulation_passed = bool(execution_report.get("broker_simulation_passed", False))
            recovery_passed = bool(execution_report.get("recovery_passed", False))
            strategy_version_control_passed = bool(execution_report.get("strategy_version_control_passed", False))
            required_ready = bool(data.get("require_ready_for_demo", True))
            if required_ready and execution_status != "READY FOR DEMO":
                issues.append(
                    StrategyIssue(
                        code="virtual_demo_not_ready",
                        severity="HIGH",
                        message=f"Execution validation status is {execution_status or 'missing'}; expected READY FOR DEMO.",
                        suggestion="Run the virtual broker process until execution validation returns READY FOR DEMO.",
                    )
                )
                fix_instructions.append("Resolve execution validation readiness before promotion.")
            if final_score < 90:
                issues.append(
                    StrategyIssue(
                        code="virtual_demo_low_score",
                        severity="HIGH",
                        message=f"Execution validation final score too low: {final_score}.",
                        suggestion="Raise the execution validation score before promotion.",
                    )
                )
                fix_instructions.append("Increase the execution validation score to at least 90.")
            if not broker_simulation_passed:
                issues.append(
                    StrategyIssue(
                        code="virtual_demo_broker_simulation_failed",
                        severity="HIGH",
                        message="Virtual broker simulation did not pass.",
                        suggestion="Fix broker simulation behavior before continuing.",
                    )
                )
                fix_instructions.append("Fix the virtual broker simulation issues.")
            if not recovery_passed:
                issues.append(
                    StrategyIssue(
                        code="virtual_demo_recovery_failed",
                        severity="HIGH",
                        message="Recovery validation did not pass in the virtual demo run.",
                        suggestion="Fix restart/recovery behavior before continuing.",
                    )
                )
                fix_instructions.append("Fix recovery behavior before continuing.")
            if not strategy_version_control_passed:
                issues.append(
                    StrategyIssue(
                        code="virtual_demo_strategy_version_failed",
                        severity="HIGH",
                        message="Strategy version control did not pass in the virtual demo run.",
                        suggestion="Align strategy metadata and rules hash before promotion.",
                    )
                )
                fix_instructions.append("Align strategy version metadata before continuing.")
            data["execution_validation_status"] = execution_status
            data["execution_validation_readiness_status"] = readiness_status
            data["execution_validation_final_score"] = final_score

        research_metrics = _metric_dict(data.get("research_metrics") or {})
        live_metrics = _metric_dict(data.get("live_metrics") or {})
        if not research_metrics or not live_metrics:
            issues.append(
                StrategyIssue(
                    code="virtual_demo_missing_metrics",
                    severity="HIGH",
                    message="Virtual demo validation requires both research and live metrics.",
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
                                code="virtual_demo_metric_drift",
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
                                code="virtual_demo_drawdown_drift",
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
            phase=7,
            stage="virtual_demo",
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
                "execution_validation_report": execution_report or None,
                "virtual_demo_evidence": {
                    "expected_signals": data.get("expected_signals"),
                    "observed_signals": data.get("observed_signals"),
                    "expected_trades": data.get("expected_trades"),
                    "observed_trades": data.get("observed_trades"),
                    "execution_metrics": data.get("execution_metrics", {}),
                    "order_outcomes": data.get("order_outcomes", {}),
                    "risk_controls": data.get("risk_controls", {}),
                    "broker_comparison": data.get("broker_comparison", {}),
                    "tolerance_pct": float(data.get("tolerance_pct", 0.05)),
                },
            },
        )

    def _build_verification_ready(self, stages: list[StageResult]) -> StageResult:
        audit = next((stage for stage in stages if stage.stage == "audit"), None)
        robustness = next((stage for stage in stages if stage.stage == "robustness"), None)
        if audit is None or robustness is None:
            return _missing_stage_result(6, "verification_ready", "completed audit and robustness stages", "virtual_demo")

        passed_stages = [stage.stage for stage in stages if stage.status == "PASS"]
        affected_rules = []
        if audit.spec is not None:
            affected_rules = sorted(audit.spec.fields.keys())

        confidence_score = 1.0
        if robustness.metadata.get("regression") and isinstance(robustness.metadata["regression"], dict):
            regression_status = str(robustness.metadata["regression"].get("status", "PASS")).upper()
            if regression_status == "WARNING":
                confidence_score = 0.75
            elif regression_status == "FAIL":
                confidence_score = 0.25

        next_required_actions = [
            "Attach virtual broker execution evidence.",
            "Run the virtual demo monitoring window.",
            "Request production approval only after demo drift stays within tolerance.",
        ]
        recommendations = [
            "Freeze the current rules and parameters before demo exposure.",
            "Use the verification-ready artifact as the handoff point for execution validation.",
            "If any rule changes after this point, rerun replay, backtest, and robustness.",
        ]

        return StageResult(
            phase=6,
            stage="verification_ready",
            status="PASS",
            issues=[],
            fix_instructions=[],
            next_stage="virtual_demo",
            can_promote=True,
            spec=audit.spec,
            metadata={
                "research_ready": True,
                "verification_ready": True,
                "passed_stages": passed_stages,
                "root_cause_analysis": "No blocking research-stage issues remain.",
                "confidence_score": round(confidence_score, 2),
                "actionable_recommendations": recommendations,
                "affected_rules": affected_rules,
                "version_diff": {
                    "baseline_version": "1.0",
                    "current_version": "1.0",
                    "changed_fields": [],
                },
                "next_required_actions": next_required_actions,
            },
        )

    def _validate_production_approval(
        self,
        virtual_demo: VirtualDemoValidationInput | dict[str, Any] | None,
        *,
        allow_live_promotion: bool,
        promote: bool,
    ) -> StageResult:
        approved = can_deploy_strategy(self.strategy_name, target_stage="demo", path=self.registry_path)
        virtual_demo_payload = _as_dict(virtual_demo)
        has_placeholder = _contains_placeholder_marker(virtual_demo_payload)
        live_guard_blocked = not allow_live_promotion or not promote or has_placeholder
        blocking_reasons: list[str] = []
        if not allow_live_promotion:
            blocking_reasons.append("Missing explicit --allow-live-promotion flag.")
        if not promote:
            blocking_reasons.append("Pipeline promotion is disabled.")
        if has_placeholder:
            blocking_reasons.append("Virtual demo payload contains synthetic/sample/example placeholder markers.")
        if approved:
            return StageResult(
                phase=8,
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
            phase=8,
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
        raise DirectCatalogMutationError(
            f"SVOSRunner cannot promote directly to {stage!r}; record the run as evidence and request a governed transition."
        )

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

    def _write_stage_report(self, stages: list[StageResult], promoted_stage: str | None) -> None:
        if not stages:
            return
        stage = stages[-1]
        report_dir = self.output_dir / self.strategy_name / "stages"
        report_dir.mkdir(parents=True, exist_ok=True)

        stage_result = {
            "strategy": self.strategy_name,
            "overall_status": _overall_status(stages),
            "promoted_stage": promoted_stage,
            "stage_count": len(stages),
            "current_stage": stage.to_dict(),
            "stages": [item.to_dict() for item in stages],
            "created_at": _now(),
            "release": build_release_metadata(),
        }
        stem = f"{stage.phase:02d}_{stage.stage}"
        (report_dir / f"{stem}.json").write_text(
            json.dumps(stage_result, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        (report_dir / f"{stem}.md").write_text(_render_stage_markdown(stage_result), encoding="utf-8")

        index = {
            "strategy": self.strategy_name,
            "stages": [
                {
                    "phase": item.phase,
                    "stage": item.stage,
                    "status": item.status,
                    "can_promote": item.can_promote,
                    "next_stage": item.next_stage,
                    "created_at": item.created_at,
                }
                for item in stages
            ],
            "overall_status": _overall_status(stages),
            "promoted_stage": promoted_stage,
            "updated_at": _now(),
        }
        (report_dir / "index.json").write_text(
            json.dumps(index, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )

    def _notify_stage_observer(
        self,
        stage_observer: Any | None,
        stages: list[StageResult],
        promoted_stage: str | None,
    ) -> None:
        if stage_observer is None or not stages:
            return
        stage = stages[-1]
        stage_observer(stage, stages=list(stages), promoted_stage=promoted_stage)


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


def _extract_strategy_name(strategy: str | dict[str, Any]) -> str:
    if isinstance(strategy, dict):
        for key in ("strategy_name", "name", "id"):
            value = _clean_text(strategy.get(key))
            if value:
                return value
    return ""


def _detect_source_type(strategy: str | dict[str, Any]) -> str:
    if isinstance(strategy, dict):
        explicit = _clean_text(strategy.get("source_type"))
        if explicit:
            return explicit
        if any(key in strategy for key in ("yaml", "json")):
            return "structured"
        if any(key in strategy for key in ("code", "source_code", "script")):
            return "code"
        return "mapping"
    return "text/plain"


def _strategy_id(strategy_name: str, raw_text: str) -> str:
    del raw_text
    slug = re.sub(r"[^A-Za-z0-9]+", "-", strategy_name.strip().upper()).strip("-") or "UNNAMED"
    return slug


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


def _strategy_spec_from_validation_document(
    document: ValidationStrategyDocument,
    strategy_name: str,
    strategy: str | dict[str, Any],
    report: StrategyValidationReport,
) -> StrategySpec:
    available_data: list[str] = []
    required_data: list[str] = []
    if isinstance(strategy, dict):
        available_data = _normalize_data_tokens(strategy.get("available_data", []))
        required_data = _normalize_data_tokens(strategy.get("required_data", []))

    missing_fields = [
        finding.location
        for result in report.validator_results
        for finding in result.findings
        if finding.code == "missing_field" and finding.location
    ]
    return StrategySpec(
        name=strategy_name,
        raw_text=document.raw_text,
        fields={key: str(value) for key, value in document.extracted_fields.items()},
        missing_fields=_dedupe_text(missing_fields),
        inferred_fields=[],
        required_data=required_data,
        available_data=available_data,
    )


def _stage_status_from_validation_report(report: StrategyValidationReport) -> StageStatus:
    if report.readiness_decision == "READY_FOR_REPLAY":
        return "PASS"
    if report.readiness_decision in {"REQUIRES_REVISION", "INCOMPLETE"}:
        return "FIX"
    return "FAIL"


def _issue_severity_from_validation_severity(severity: str) -> str:
    value = str(severity or "").upper()
    if value == "ERROR":
        return "HIGH"
    if value in {"WARN", "WARNING"}:
        return "MEDIUM"
    return "LOW"


def _strategy_issues_from_validation_report(report: StrategyValidationReport) -> list[StrategyIssue]:
    issues: list[StrategyIssue] = []
    for result in report.validator_results:
        for finding in result.findings:
            issues.append(
                StrategyIssue(
                    code=finding.code,
                    field=finding.location,
                    severity=_issue_severity_from_validation_severity(finding.severity),
                    message=f"[{result.validator_name}] {finding.message}",
                    suggestion=str(finding.details.get("recommendation", "")).strip() if isinstance(finding.details, dict) else "",
                )
            )
    return _dedupe_issues(issues)


def _fix_instructions_from_validation_report(report: StrategyValidationReport) -> list[str]:
    instructions = [item.message for item in report.recommendations if item.message]
    return _dedupe_text(instructions)


def _clarifying_question_from_recommendation(item: ValidationRecommendation) -> str:
    message = item.message.strip()
    original = item.original.strip()
    improved = item.improved.strip()
    if original:
        return f"How should this rule be defined explicitly: {original}?"
    if improved:
        return f"Should the rule be clarified as: {improved}?"
    lowered = message.lower()
    if lowered.startswith("add an explicit "):
        target = message[len("Add an explicit ") :].rstrip(".")
        return f"What is the explicit {target.lower()}?"
    if lowered.startswith("document the "):
        target = message[len("Document the ") :].rstrip(".")
        return f"What is the explicit {target.lower()}?"
    if lowered.startswith("replace '"):
        return message.replace("Replace", "How should we replace", 1).rstrip(".") + "?"
    return message.rstrip(".") + "?"


def _clarifying_questions_from_validation_report(report: StrategyValidationReport) -> list[str]:
    questions = [_clarifying_question_from_recommendation(item) for item in report.recommendations]
    return _dedupe_text(questions)


def _validation_recommendation_from_dict(payload: dict[str, Any]) -> ValidationRecommendation:
    return ValidationRecommendation(
        code=str(payload.get("code", "")),
        message=str(payload.get("message", "")),
        priority=str(payload.get("priority", "MEDIUM")),
        original=str(payload.get("original", "")),
        improved=str(payload.get("improved", "")),
        reason=str(payload.get("reason", "")),
        expected_improvement=str(payload.get("expected_improvement", "")),
    )


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


def _display_stage_name(stage_name: str) -> str:
    return stage_name.replace("_", " ").title()


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
                f"## {_display_stage_name(stage.stage)}",
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


def _render_stage_markdown(stage_report: dict[str, Any]) -> str:
    current_stage = stage_report["current_stage"]
    lines = [
        f"# SVOS Stage Report - {stage_report['strategy']}",
        "",
        f"- Current Stage: `{_display_stage_name(current_stage['stage'])}`",
        f"- Phase: `{current_stage['phase']}`",
        f"- Status: **{current_stage['status']}**",
        f"- Overall Status So Far: **{stage_report['overall_status']}**",
        f"- Promoted Stage: `{stage_report['promoted_stage'] or 'n/a'}`",
        f"- Stage Count: `{stage_report['stage_count']}`",
        f"- Timestamp: `{stage_report['created_at']}`",
    ]
    if current_stage.get("next_stage"):
        lines.append(f"- Next Stage: `{current_stage['next_stage']}`")
    lines.append("")
    lines.append("## Current Stage Details")
    _append_stage_block(lines, current_stage)

    if len(stage_report["stages"]) > 1:
        lines.extend(["", "## Pipeline So Far"])
        for item in stage_report["stages"]:
            lines.extend(
                [
                    f"### {_display_stage_name(item['stage'])}",
                    f"- Phase: `{item['phase']}`",
                    f"- Status: **{item['status']}**",
                    f"- Can Promote: `{str(item['can_promote']).lower()}`",
                    f"- Next Stage: `{item['next_stage'] or 'n/a'}`",
                ]
            )
    return "\n".join(lines) + "\n"


def _append_stage_block(lines: list[str], stage: dict[str, Any]) -> None:
    if stage.get("clarifying_questions"):
        lines.append("- Clarifying Questions:")
        for question in stage["clarifying_questions"]:
            lines.append(f"  - {question}")
    if stage.get("fix_instructions"):
        lines.append("- Fix Instructions:")
        for item in stage["fix_instructions"]:
            lines.append(f"  - {item}")
    if stage.get("issues"):
        lines.append("- Issues:")
        for issue in stage["issues"]:
            lines.append(f"  - {issue['severity']}: {issue['message']}")
    enhancement_plan = stage.get("metadata", {}).get("enhancement_plan", {}) if isinstance(stage.get("metadata", {}), dict) else {}
    if enhancement_plan:
        lines.append("- Enhancement Plan:")
        if enhancement_plan.get("status"):
            lines.append(f"  - Status: `{enhancement_plan['status']}`")
        if enhancement_plan.get("summary"):
            lines.append(f"  - Summary: {enhancement_plan['summary']}")
        for question in enhancement_plan.get("questions", [])[:5]:
            prompt = question.get("prompt", "")
            if prompt:
                lines.append(f"  - Question: {prompt}")
            proposed = question.get("proposed_revision", "")
            if proposed:
                lines.append(f"    Proposed Revision: {proposed}")


def _overall_status(stages: list[StageResult]) -> StageStatus:
    overall: StageStatus = "PASS"
    for stage in stages:
        if stage.status == "FAIL":
            return "FAIL"
        if stage.status == "FIX" and overall != "FAIL":
            overall = "FIX"
    return overall

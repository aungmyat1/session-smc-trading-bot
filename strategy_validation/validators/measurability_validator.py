from __future__ import annotations

import re

from ..models import StrategyDocument, ValidationFinding, ValidationRecommendation, ValidatorResult
from ..module_base import BaseValidator


class MeasurabilityValidator(BaseValidator):
    name = "Measurability Validation"

    _COMPARATOR_RE = re.compile(r"(>=|<=|==|>|<|\bbetween\b|\bat least\b|\bwithin\b|\bmaximum\b|\bminimum\b|\bexactly\b|\d)")

    def _candidate_rules(self, document: StrategyDocument) -> list[str]:
        rules: list[str] = []
        for key in (
            "Entry Rules",
            "Confirmation Rules",
            "Exit Rules (TP / SL / BE / Trailing / Partial)",
            "Filters (Spread / Volatility / Session / News)",
        ):
            section = document.sections.get(key, "")
            if section:
                rules.extend([line.strip() for line in section.splitlines() if line.strip()])
        for field_name in ("entry_rules", "exit_rules", "risk_model", "stop_loss", "take_profit"):
            value = str(document.extracted_fields.get(field_name, "")).strip()
            if value:
                rules.extend([line.strip() for line in value.splitlines() if line.strip()])
        for key, value in document.key_values.items():
            normalized = key.strip().lower()
            if normalized in {"entry rules", "confirmation", "confirmation rules", "exit rules", "risk model", "stop loss", "take profit", "filters"}:
                rules.append(str(value).strip())
        rules.extend(document.list_items)
        return [rule for rule in rules if len(rule.split()) >= 3]

    def validate(self, document: StrategyDocument) -> ValidatorResult:
        measurable: list[str] = []
        non_measurable: list[str] = []
        findings: list[ValidationFinding] = []
        recommendations: list[ValidationRecommendation] = []

        for rule in self._candidate_rules(document):
            if self._COMPARATOR_RE.search(rule.lower()):
                measurable.append(rule)
            else:
                non_measurable.append(rule)

        for rule in non_measurable[:12]:
            findings.append(
                ValidationFinding(
                    code="non_measurable_rule",
                    message="Rule cannot be converted to objective logic without assumptions.",
                    severity="WARN",
                    evidence=rule,
                )
            )
            recommendations.append(
                ValidationRecommendation(
                    code="make_rule_measurable",
                    message="Rewrite the rule with thresholds, comparators, or explicit state transitions.",
                    priority="HIGH",
                    original=rule,
                    improved="Add a numeric threshold or exact comparison for this rule.",
                    reason="Replay and coding require objective criteria.",
                    expected_improvement="Improves testability and reproducibility.",
                )
            )

        total = len(measurable) + len(non_measurable)
        score = 0.0 if total == 0 else round((len(measurable) / total) * 100.0, 2)
        status = "PASS" if total and not non_measurable else "PARTIAL" if score >= 60 else "FAIL"
        return ValidatorResult(
            validator_name=self.name,
            score=score,
            status=status,
            findings=findings,
            recommendations=recommendations,
            metadata={
                "measurable_rules": measurable,
                "non_measurable_rules": non_measurable,
                "measurability_score": score,
            },
        )

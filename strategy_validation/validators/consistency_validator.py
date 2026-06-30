from __future__ import annotations

import re

from ..models import (
    StrategyDocument,
    ValidationFinding,
    ValidationRecommendation,
    ValidatorResult,
    ValidationStatus,
)
from ..module_base import BaseValidator


class LogicalConsistencyValidator(BaseValidator):
    name = "Logical Consistency Validation"

    def validate(self, document: StrategyDocument) -> ValidatorResult:
        text = document.raw_text.lower()
        findings: list[ValidationFinding] = []
        recommendations: list[ValidationRecommendation] = []

        if "trade only london" in text and "trade only asian" in text:
            findings.append(
                ValidationFinding(
                    code="conflicting_sessions",
                    message="The strategy restricts trading to both London-only and Asian-only sessions.",
                    severity="ERROR",
                )
            )

        if (
            re.search(r"maximum\s+2\s+trades?/day", text)
            and "unlimited entries" in text
        ):
            findings.append(
                ValidationFinding(
                    code="conflicting_trade_limits",
                    message="The strategy sets a daily trade cap and also claims unlimited entries.",
                    severity="ERROR",
                )
            )

        if "not implemented" in text and any(
            term in text for term in ("implemented", "must", "required")
        ):
            findings.append(
                ValidationFinding(
                    code="spec_implementation_mismatch",
                    message="The document mixes required behavior with 'not implemented' caveats.",
                    severity="WARN",
                )
            )

        exit_rules = str(document.extracted_fields.get("exit_rules", "")).lower()
        if "single tp only" in exit_rules and any(
            term in exit_rules
            for term in ("partial", "runner", "break even", "trailing")
        ):
            findings.append(
                ValidationFinding(
                    code="conflicting_exit_model",
                    message="Exit rules describe both a single take-profit model and multi-stage management.",
                    severity="ERROR",
                )
            )

        for finding in findings:
            recommendations.append(
                ValidationRecommendation(
                    code="resolve_conflict",
                    message=f"Resolve consistency issue: {finding.message}",
                    priority="HIGH" if finding.severity == "ERROR" else "MEDIUM",
                    reason="Conflicting logic prevents deterministic execution and validation.",
                    expected_improvement="Removes rule collisions before replay.",
                )
            )

        score = round(
            max(
                0.0,
                100.0
                - sum(30 if item.severity == "ERROR" else 15 for item in findings),
            ),
            2,
        )
        status: ValidationStatus = (
            "PASS"
            if not findings
            else (
                "FAIL"
                if any(item.severity == "ERROR" for item in findings)
                else "PARTIAL"
            )
        )
        return ValidatorResult(
            validator_name=self.name,
            score=score,
            status=status,
            findings=findings,
            recommendations=recommendations,
            metadata={"conflict_count": len(findings)},
        )

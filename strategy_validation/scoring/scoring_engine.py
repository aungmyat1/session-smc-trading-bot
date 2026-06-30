from __future__ import annotations

from ..models import ReadinessStatus, ValidationStatus, ValidatorResult


class ScoringEngine:
    WEIGHTS = {
        "Input Validation": 1.3,
        "Rule Completeness Validation": 1.1,
        "Ambiguity Detection": 1.0,
        "Logical Consistency Validation": 1.3,
        "Measurability Validation": 1.2,
        "Institutional Rule Validation": 1.0,
        "Risk Management Validation": 1.2,
        "Testability Validation": 1.2,
    }

    def aggregate_score(self, results: list[ValidatorResult]) -> float:
        if not results:
            return 0.0
        total_weight = sum(
            self.WEIGHTS.get(result.validator_name, 1.0) for result in results
        )
        weighted = sum(
            result.score * self.WEIGHTS.get(result.validator_name, 1.0)
            for result in results
        )
        return round(weighted / total_weight, 2)

    def overall_status(self, results: list[ValidatorResult]) -> ValidationStatus:
        if any(result.status == "FAIL" for result in results):
            return "FAIL"
        if any(result.status in {"PARTIAL", "WARN"} for result in results):
            return "PARTIAL"
        return "PASS"

    def readiness_decision(
        self, results: list[ValidatorResult], score: float
    ) -> ReadinessStatus:
        hard_fail = any(
            result.validator_name
            in {
                "Input Validation",
                "Logical Consistency Validation",
                "Risk Management Validation",
            }
            and result.status == "FAIL"
            for result in results
        )
        if hard_fail:
            return "REJECTED"
        if any(result.status == "FAIL" for result in results):
            return "INCOMPLETE"
        if score >= 85 and all(result.status == "PASS" for result in results):
            return "READY_FOR_REPLAY"
        if score >= 65:
            return "REQUIRES_REVISION"
        return "INCOMPLETE"

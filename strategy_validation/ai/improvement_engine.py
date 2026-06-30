from __future__ import annotations

from ..models import ValidationRecommendation, ValidatorResult


class SpecificationImprovementEngine:
    """Deterministic recommendation aggregator for weak specifications."""

    def build_recommendations(
        self, results: list[ValidatorResult]
    ) -> list[ValidationRecommendation]:
        merged: list[ValidationRecommendation] = []
        seen: set[tuple[str, str, str]] = set()
        for result in results:
            for item in result.recommendations:
                key = (item.code, item.message, item.original)
                if key in seen:
                    continue
                seen.add(key)
                merged.append(item)
        return merged

from __future__ import annotations

from enum import Enum


class StrategyStage(str, Enum):
    DRAFT = "DRAFT"
    INTAKE = "INTAKE"
    AUDIT = "AUDIT"
    REFINEMENT = "REFINEMENT"
    HISTORICAL_REPLAY = "HISTORICAL_REPLAY"
    STATISTICAL_VALIDATION = "STATISTICAL_VALIDATION"
    ROBUSTNESS_VALIDATION = "ROBUSTNESS_VALIDATION"
    VIRTUAL_DEMO = "VIRTUAL_DEMO"
    PRODUCTION_APPROVAL = "PRODUCTION_APPROVAL"
    REVALIDATION = "REVALIDATION"
    RETIRED = "RETIRED"


class LifecycleTransitionError(ValueError):
    """Raised when a strategy transition is not permitted."""


_ORDER = [
    StrategyStage.DRAFT,
    StrategyStage.INTAKE,
    StrategyStage.AUDIT,
    StrategyStage.REFINEMENT,
    StrategyStage.HISTORICAL_REPLAY,
    StrategyStage.STATISTICAL_VALIDATION,
    StrategyStage.ROBUSTNESS_VALIDATION,
    StrategyStage.VIRTUAL_DEMO,
    StrategyStage.PRODUCTION_APPROVAL,
    StrategyStage.REVALIDATION,
    StrategyStage.RETIRED,
]

_ALLOWED: dict[StrategyStage, set[StrategyStage]] = {
    current: ({_ORDER[index + 1]} if index < len(_ORDER) - 1 else set())
    for index, current in enumerate(_ORDER)
}
_ALLOWED[StrategyStage.REVALIDATION].update({StrategyStage.HISTORICAL_REPLAY, StrategyStage.RETIRED})
# Explicit research failure loops. These are corrective transitions, not
# promotions, and keep failed strategies away from execution stages.
_ALLOWED[StrategyStage.REFINEMENT].add(StrategyStage.AUDIT)
_ALLOWED[StrategyStage.HISTORICAL_REPLAY].add(StrategyStage.REFINEMENT)
_ALLOWED[StrategyStage.STATISTICAL_VALIDATION].add(StrategyStage.REFINEMENT)
_ALLOWED[StrategyStage.ROBUSTNESS_VALIDATION].add(StrategyStage.REFINEMENT)
_ALLOWED[StrategyStage.VIRTUAL_DEMO].update({StrategyStage.REFINEMENT, StrategyStage.HISTORICAL_REPLAY})
# Production Approval is record-only during platform construction. It exists in
# the vocabulary but cannot be entered by the lifecycle authority.
_ALLOWED[StrategyStage.VIRTUAL_DEMO].discard(StrategyStage.PRODUCTION_APPROVAL)

_LEGACY_STAGE_MAP = {
    "draft": StrategyStage.DRAFT,
    "research": StrategyStage.AUDIT,
    "replay": StrategyStage.HISTORICAL_REPLAY,
    "backtest": StrategyStage.STATISTICAL_VALIDATION,
    "walk_forward": StrategyStage.ROBUSTNESS_VALIDATION,
    "shadow": StrategyStage.VIRTUAL_DEMO,
    "demo": StrategyStage.VIRTUAL_DEMO,
    "live": StrategyStage.RETIRED,
    "retired": StrategyStage.RETIRED,
}


class StrategyLifecycleManager:
    """Canonical institutional lifecycle for the unified SVOS layer."""

    def stages(self) -> list[str]:
        return [stage.value for stage in _ORDER]

    def allowed_transitions(self, stage: str | StrategyStage) -> list[str]:
        current = self.normalize_stage(stage)
        return [item.value for item in sorted(_ALLOWED.get(current, set()), key=_ORDER.index)]

    def normalize_stage(self, stage: str | StrategyStage) -> StrategyStage:
        if isinstance(stage, StrategyStage):
            return stage
        value = str(stage or "").strip().upper()
        try:
            return StrategyStage(value)
        except ValueError as exc:
            raise LifecycleTransitionError(f"Unknown lifecycle stage: {stage!r}") from exc

    def infer_stage(self, manifest: dict[str, object] | None = None) -> StrategyStage:
        manifest = manifest or {}
        explicit = manifest.get("svos_stage")
        if explicit:
            return self.normalize_stage(str(explicit))
        legacy = str(manifest.get("status", "draft")).strip().lower()
        return _LEGACY_STAGE_MAP.get(legacy, StrategyStage.DRAFT)

    def validate_transition(self, from_stage: str | StrategyStage, to_stage: str | StrategyStage) -> None:
        current = self.normalize_stage(from_stage)
        target = self.normalize_stage(to_stage)
        if target not in _ALLOWED.get(current, set()):
            allowed = ", ".join(self.allowed_transitions(current)) or "none"
            raise LifecycleTransitionError(
                f"Illegal lifecycle transition: {current.value} -> {target.value}. Allowed next stages: {allowed}."
            )

    def validate_transition_from_names(self, strategy: str, to_stage: str) -> None:
        """Validate a transition from a strategy name string.

        Convenience method for LifecycleAuthority that performs the same
        validation as validate_transition() using only string names.
        The from_stage is not validated by the lifecycle vocabulary alone;
        this is a wrapper for string-stage validation.

        Raises LifecycleTransitionError if the stage name is invalid.
        """
        self.normalize_stage(to_stage)


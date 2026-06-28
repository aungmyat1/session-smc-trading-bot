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
    VERIFICATION_READY = "VERIFICATION_READY"
    EXECUTION_VALIDATION = "EXECUTION_VALIDATION"
    PAPER_TRADING = "PAPER_TRADING"
    LIVE_DEMO = "LIVE_DEMO"
    PRODUCTION_CANDIDATE = "PRODUCTION_CANDIDATE"
    PRODUCTION = "PRODUCTION"
    MONITORING = "MONITORING"
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
    StrategyStage.VERIFICATION_READY,
    StrategyStage.EXECUTION_VALIDATION,
    StrategyStage.PAPER_TRADING,
    StrategyStage.LIVE_DEMO,
    StrategyStage.PRODUCTION_CANDIDATE,
    StrategyStage.PRODUCTION,
    StrategyStage.MONITORING,
    StrategyStage.REVALIDATION,
    StrategyStage.RETIRED,
]

_ALLOWED: dict[StrategyStage, set[StrategyStage]] = {
    current: ({_ORDER[index + 1]} if index < len(_ORDER) - 1 else set())
    for index, current in enumerate(_ORDER)
}
_ALLOWED[StrategyStage.MONITORING].update({StrategyStage.REVALIDATION, StrategyStage.RETIRED})
_ALLOWED[StrategyStage.REVALIDATION].update({StrategyStage.HISTORICAL_REPLAY, StrategyStage.RETIRED})

_LEGACY_STAGE_MAP = {
    "draft": StrategyStage.DRAFT,
    "research": StrategyStage.AUDIT,
    "replay": StrategyStage.HISTORICAL_REPLAY,
    "backtest": StrategyStage.STATISTICAL_VALIDATION,
    "walk_forward": StrategyStage.ROBUSTNESS_VALIDATION,
    "shadow": StrategyStage.VIRTUAL_DEMO,
    "demo": StrategyStage.LIVE_DEMO,
    "live": StrategyStage.PRODUCTION,
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


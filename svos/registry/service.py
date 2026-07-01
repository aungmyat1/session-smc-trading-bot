from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from core.strategy_registry import get_strategy_manifest, list_catalog_strategies
from svos.lifecycle.manager import LifecycleTransitionError, StrategyLifecycleManager
from shared.models import EvidenceRecord, GateDecision, StrategyRecord, TransitionRecord, VersionRecord
from shared.serialization import append_jsonl, now_iso, read_json, read_jsonl, stable_manifest_hash, write_json


def _stable_strategy_id(strategy: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", strategy.strip().upper()).strip("-") or "UNNAMED"


def _next_patch_version(version: str) -> str:
    match = re.fullmatch(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", version.strip())
    if match is None:
        return "0.0.1"
    major = int(match.group(1))
    minor = int(match.group(2) or 0)
    patch = int(match.group(3) or 0) + 1
    return f"{major}.{minor}.{patch}"


class StrategyRegistryService:
    """Append-only registry history layered on top of the existing strategy catalog."""

    def __init__(
        self,
        *,
        root: Path | str,
        catalog_path: Path | str | None = None,
        lifecycle: StrategyLifecycleManager | None = None,
    ) -> None:
        self.root = Path(root)
        self.catalog_path = Path(catalog_path) if catalog_path is not None else self.root / "config" / "strategy_catalog.yaml"
        self.lifecycle = lifecycle or StrategyLifecycleManager()
        self.registry_root = self.root / "data" / "svos" / "registry"

    def _strategy_dir(self, strategy: str) -> Path:
        return self.registry_root / strategy

    def _state_path(self, strategy: str) -> Path:
        return self._strategy_dir(strategy) / "state.json"

    def _versions_path(self, strategy: str) -> Path:
        return self._strategy_dir(strategy) / "versions.jsonl"

    def _evidence_path(self, strategy: str) -> Path:
        return self._strategy_dir(strategy) / "evidence.jsonl"

    def _transitions_path(self, strategy: str) -> Path:
        return self._strategy_dir(strategy) / "transitions.jsonl"

    def ensure_strategy(self, strategy: str, actor: str = "system", reason: str = "bootstrap") -> StrategyRecord:
        manifest = get_strategy_manifest(strategy, self.catalog_path)
        if manifest is None:
            raise KeyError(f"strategy not found in catalog: {strategy}")
        versions = read_jsonl(self._versions_path(strategy))
        state = read_json(self._state_path(strategy), {})
        if not versions:
            version = self.record_version(strategy, manifest=manifest, actor=actor, reason=reason)
            stage = self.lifecycle.infer_stage(manifest).value
            state = {
                "strategy": strategy,
                "current_stage": stage,
                "legacy_status": str(manifest.get("status", "draft")),
                "current_version_id": version.version_id,
                "latest_version": version.version,
                "updated_at": version.created_at,
            }
            write_json(self._state_path(strategy), state)
        return self.get_strategy_record(strategy)

    def record_version(
        self,
        strategy: str,
        *,
        manifest: dict[str, Any] | None = None,
        actor: str = "system",
        reason: str = "snapshot",
    ) -> VersionRecord:
        manifest = dict(manifest or get_strategy_manifest(strategy, self.catalog_path) or {})
        if not manifest:
            raise KeyError(f"strategy not found in catalog: {strategy}")
        created_at = now_iso()
        version = str(manifest.get("version", "0"))
        version_id = stable_manifest_hash({"strategy": strategy, "version": version, "manifest": manifest, "created_at": created_at})
        record = VersionRecord(
            version_id=version_id,
            strategy=strategy,
            version=version,
            created_at=created_at,
            actor=actor,
            reason=reason,
            manifest=manifest,
        )
        append_jsonl(self._versions_path(strategy), record.to_dict())
        state = read_json(self._state_path(strategy), {})
        state.update(
            {
                "strategy": strategy,
                "legacy_status": str(manifest.get("status", "draft")),
                "current_version_id": version_id,
                "latest_version": version,
                "updated_at": created_at,
                "current_stage": state.get("current_stage", self.lifecycle.infer_stage(manifest).value),
            }
        )
        write_json(self._state_path(strategy), state)
        return record

    def ensure_spec_version(
        self,
        strategy: str,
        *,
        specification: str,
        actor: str = "svos",
        reason: str = "strategy specification registered",
    ) -> VersionRecord:
        """Register a stable strategy identity and version a changed specification."""
        current = self.ensure_strategy(strategy, actor=actor, reason="strategy registry initialized")
        versions = self.versions(strategy)
        manifest = dict(
            (versions[-1].get("manifest") if versions else None)
            or get_strategy_manifest(strategy, self.catalog_path)
            or {}
        )
        spec_hash = hashlib.sha256(specification.encode("utf-8")).hexdigest()
        previous_hash = str(manifest.get("strategy_spec_hash", ""))
        strategy_id = str(manifest.get("strategy_id", "")).strip() or _stable_strategy_id(strategy)
        version = str(manifest.get("version", current.latest_version or "0.0.0"))
        changed = bool(previous_hash and previous_hash != spec_hash)
        if changed:
            version = _next_patch_version(version)

        if previous_hash == spec_hash and manifest.get("strategy_id"):
            if versions:
                latest = versions[-1]
                return VersionRecord(
                    version_id=str(latest["version_id"]),
                    strategy=strategy,
                    version=str(latest.get("version", version)),
                    created_at=str(latest.get("created_at", "")),
                    actor=str(latest.get("actor", actor)),
                    reason=str(latest.get("reason", reason)),
                    manifest=dict(latest.get("manifest", manifest)),
                )

        updated = {
            **manifest,
            "strategy_id": strategy_id,
            "strategy_spec_hash": spec_hash,
            "version": version,
        }
        change_reason = f"{reason}; specification changed" if changed else reason
        return self.record_version(strategy, manifest=updated, actor=actor, reason=change_reason)

    def record_evidence(
        self,
        strategy: str,
        *,
        stage: str,
        service: str,
        report_type: str,
        artifact_path: str,
        artifact_hash: str,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> EvidenceRecord:
        current = self.ensure_strategy(strategy)
        recorded_at = now_iso()
        evidence_id = stable_manifest_hash(
            {
                "strategy": strategy,
                "stage": stage,
                "service": service,
                "report_type": report_type,
                "artifact_path": artifact_path,
                "artifact_hash": artifact_hash,
                "recorded_at": recorded_at,
            }
        )
        record = EvidenceRecord(
            evidence_id=evidence_id,
            strategy=strategy,
            stage=stage,
            service=service,
            status=status,
            report_type=report_type,
            artifact_path=artifact_path,
            artifact_hash=artifact_hash,
            recorded_at=recorded_at,
            metadata={
                "current_version_id": current.current_version_id,
                "strategy_version": current.latest_version,
                **(metadata or {}),
            },
        )
        append_jsonl(self._evidence_path(strategy), record.to_dict())
        state = read_json(self._state_path(strategy), {})
        state["last_evidence_at"] = recorded_at
        write_json(self._state_path(strategy), state)
        return record

    def transition(
        self,
        strategy: str,
        *,
        to_stage: str,
        actor: str = "system",
        reason: str = "",
        metadata: dict[str, Any] | None = None,
        governance_decision: GateDecision | None = None,
    ) -> TransitionRecord:
        current = self.ensure_strategy(strategy)
        self.lifecycle.validate_transition(current.current_stage, to_stage)
        if governance_decision is None:
            raise LifecycleTransitionError("Lifecycle transitions require an allowed governance gate decision.")
        if not governance_decision.allowed:
            raise LifecycleTransitionError("The governance gate decision denied this lifecycle transition.")
        if (
            governance_decision.strategy != strategy
            or governance_decision.from_stage != current.current_stage
            or governance_decision.to_stage != to_stage
            or governance_decision.current_version_id != current.current_version_id
        ):
            raise LifecycleTransitionError("The governance gate decision does not match the current strategy state.")
        recorded_at = now_iso()
        transition_id = stable_manifest_hash(
            {
                "strategy": strategy,
                "from_stage": current.current_stage,
                "to_stage": to_stage,
                "recorded_at": recorded_at,
                "reason": reason,
            }
        )
        record = TransitionRecord(
            transition_id=transition_id,
            strategy=strategy,
            from_stage=current.current_stage,
            to_stage=to_stage,
            recorded_at=recorded_at,
            actor=actor,
            reason=reason,
            metadata={"governance_decision_id": governance_decision.decision_id, **(metadata or {})},
        )
        append_jsonl(self._transitions_path(strategy), record.to_dict())
        state = read_json(self._state_path(strategy), {})
        state["current_stage"] = to_stage
        state["updated_at"] = recorded_at
        state["last_transition_at"] = recorded_at
        write_json(self._state_path(strategy), state)
        return record

    def versions(self, strategy: str) -> list[dict[str, Any]]:
        return read_jsonl(self._versions_path(strategy))

    def evidence(self, strategy: str) -> list[dict[str, Any]]:
        return read_jsonl(self._evidence_path(strategy))

    def transitions(self, strategy: str) -> list[dict[str, Any]]:
        return read_jsonl(self._transitions_path(strategy))

    def get_strategy_record(self, strategy: str) -> StrategyRecord:
        manifest = dict(get_strategy_manifest(strategy, self.catalog_path) or {})
        if not manifest:
            raise KeyError(f"strategy not found in catalog: {strategy}")
        state = read_json(self._state_path(strategy), {})
        versions = self.versions(strategy)
        evidence = self.evidence(strategy)
        transitions = self.transitions(strategy)
        current_stage = str(state.get("current_stage") or self.lifecycle.infer_stage(manifest).value)
        current_version_id = str(state.get("current_version_id") or (versions[-1]["version_id"] if versions else ""))
        latest_version = str(state.get("latest_version") or manifest.get("version", ""))
        return StrategyRecord(
            strategy=strategy,
            current_stage=current_stage,
            legacy_status=str(manifest.get("status", "draft")),
            current_version_id=current_version_id,
            latest_version=latest_version,
            version_count=len(versions),
            evidence_count=len(evidence),
            transition_count=len(transitions),
            last_transition_at=str(state.get("last_transition_at", "")),
            last_evidence_at=str(state.get("last_evidence_at", "")),
            manifest=manifest,
        )

    def summary(self) -> dict[str, Any]:
        strategies = []
        for strategy in list_catalog_strategies(self.catalog_path):
            try:
                strategies.append(self.ensure_strategy(strategy).to_dict())
            except KeyError:
                continue
        return {
            "strategy_count": len(strategies),
            "strategies": strategies,
            "lifecycle_stages": self.lifecycle.stages(),
        }

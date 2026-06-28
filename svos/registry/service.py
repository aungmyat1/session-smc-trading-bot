from __future__ import annotations

from pathlib import Path
from typing import Any

from core.strategy_registry import get_strategy_manifest, list_catalog_strategies, update_strategy_manifest
from svos.lifecycle.manager import StrategyLifecycleManager
from svos.shared.models import EvidenceRecord, StrategyRecord, TransitionRecord, VersionRecord
from svos.shared.support import append_jsonl, now_iso, read_json, read_jsonl, stable_manifest_hash, write_json


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
            update_strategy_manifest(
                strategy,
                {
                    "svos_stage": stage,
                    "svos_stage_updated_at": version.created_at,
                    "svos_registry_bootstrapped_at": version.created_at,
                },
                self.catalog_path,
            )
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
        self.ensure_strategy(strategy)
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
            metadata=metadata or {},
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
    ) -> TransitionRecord:
        current = self.ensure_strategy(strategy)
        self.lifecycle.validate_transition(current.current_stage, to_stage)
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
            metadata=metadata or {},
        )
        append_jsonl(self._transitions_path(strategy), record.to_dict())
        state = read_json(self._state_path(strategy), {})
        state["current_stage"] = to_stage
        state["updated_at"] = recorded_at
        state["last_transition_at"] = recorded_at
        write_json(self._state_path(strategy), state)
        update_strategy_manifest(
            strategy,
            {
                "svos_stage": to_stage,
                "svos_stage_updated_at": recorded_at,
                "svos_last_transition_reason": reason,
            },
            self.catalog_path,
        )
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

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class VersionRecord:
    version_id: str
    strategy: str
    version: str
    created_at: str
    actor: str
    reason: str
    manifest: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class EvidenceRecord:
    evidence_id: str
    strategy: str
    stage: str
    service: str
    status: str
    report_type: str
    artifact_path: str
    artifact_hash: str
    recorded_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TransitionRecord:
    transition_id: str
    strategy: str
    from_stage: str
    to_stage: str
    recorded_at: str
    actor: str
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class StrategyRecord:
    strategy: str
    current_stage: str
    legacy_status: str
    current_version_id: str
    latest_version: str
    version_count: int
    evidence_count: int
    transition_count: int
    last_transition_at: str
    last_evidence_at: str
    manifest: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

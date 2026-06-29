from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal

ValidationStatus = Literal["PASS", "FAIL", "PARTIAL", "WARN"]
ReadinessStatus = Literal["READY_FOR_REPLAY", "REQUIRES_REVISION", "INCOMPLETE", "REJECTED"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ValidationFinding:
    code: str
    message: str
    severity: str = "INFO"
    location: str = ""
    evidence: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ValidationRecommendation:
    code: str
    message: str
    priority: str = "MEDIUM"
    original: str = ""
    improved: str = ""
    reason: str = ""
    expected_improvement: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ValidatorResult:
    validator_name: str
    score: float
    status: ValidationStatus
    findings: list[ValidationFinding] = field(default_factory=list)
    recommendations: list[ValidationRecommendation] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["findings"] = [item.to_dict() for item in self.findings]
        payload["recommendations"] = [item.to_dict() for item in self.recommendations]
        return payload


@dataclass(frozen=True)
class AuditLogEntry:
    validator_name: str
    version: str
    document_hash: str
    created_at: str
    result_status: ValidationStatus
    result_score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StrategyDocument:
    strategy_name: str
    raw_text: str
    source_path: str = ""
    sections: dict[str, str] = field(default_factory=dict)
    key_values: dict[str, str] = field(default_factory=dict)
    list_items: list[str] = field(default_factory=list)
    extracted_fields: dict[str, Any] = field(default_factory=dict)

    @property
    def document_hash(self) -> str:
        return sha256(self.raw_text.encode("utf-8")).hexdigest()

    @classmethod
    def from_text(cls, text: str, source_path: str = "") -> "StrategyDocument":
        from .parser import parse_strategy_document

        return parse_strategy_document(text=text, source_path=source_path)

    @classmethod
    def from_file(cls, path: str | Path) -> "StrategyDocument":
        file_path = Path(path)
        return cls.from_text(file_path.read_text(encoding="utf-8"), source_path=str(file_path))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ValidationReport:
    strategy_name: str
    overall_score: float
    overall_status: ValidationStatus
    readiness_decision: ReadinessStatus
    validator_results: list[ValidatorResult]
    critical_issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommendations: list[ValidationRecommendation] = field(default_factory=list)
    audit_log: list[AuditLogEntry] = field(default_factory=list)
    summary: str = ""
    generated_at: str = field(default_factory=utc_now)
    source_path: str = ""
    document_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "overall_score": self.overall_score,
            "overall_status": self.overall_status,
            "readiness_decision": self.readiness_decision,
            "validator_results": [item.to_dict() for item in self.validator_results],
            "critical_issues": list(self.critical_issues),
            "warnings": list(self.warnings),
            "recommendations": [item.to_dict() for item in self.recommendations],
            "audit_log": [item.to_dict() for item in self.audit_log],
            "summary": self.summary,
            "generated_at": self.generated_at,
            "source_path": self.source_path,
            "document_hash": self.document_hash,
        }

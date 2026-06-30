"""Strategy Intake — Phase 0 of the SVOS qualification pipeline.

Responsibilities:
- Validate strategy identity, ownership, instruments, and timeframes.
- Verify the specification text is non-empty and parseable.
- Register the strategy version via StrategyRegistryService.
- Transition DRAFT → INTAKE via the governance layer.
- Produce a canonical intake report artifact and register it as evidence.
- Return a structured IntakeResult for downstream use.

This service never writes to a broker, never reads live data, and never
mutates lifecycle state except through the authorised SVOSPlatform gateway.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from svos.application.run_manifest import RunManifestBuilder
from svos.reports.builders import IntakeReportBuilder

_REQUIRED_CATALOG_FIELDS = ("symbols", "timeframes", "owner", "version")
_SPEC_MIN_LENGTH = 50


@dataclass(slots=True)
class IntakeFinding:
    code: str
    message: str
    severity: str = "ERROR"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class IntakeResult:
    strategy: str
    status: str  # PASS | FAIL
    version_id: str
    report_artifact: str  # absolute path to intake report JSON
    evidence_id: str
    manifest_id: str
    findings: list[IntakeFinding] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == "PASS"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["passed"] = self.passed
        return d


class IntakeService:
    """Validates, versions, and registers a strategy into the SVOS pipeline."""

    def __init__(self, platform: Any) -> None:
        self._platform = platform
        self._builder = IntakeReportBuilder(platform.root)
        self._manifest_builder = RunManifestBuilder(platform.root)

    def run(
        self,
        strategy: str,
        specification: str,
        *,
        actor: str = "svos-intake",
        dataset_id: str = "",
    ) -> IntakeResult:
        """Execute intake for the named strategy.

        Args:
            strategy: Strategy name as registered in the catalog.
            specification: Full strategy specification text (Markdown or plain text).
            actor: Identity of the caller recorded in audit trail.
            dataset_id: Optional dataset snapshot ID for the run manifest.

        Returns:
            IntakeResult with PASS or FAIL status and all audit artefacts.
        """
        findings: list[IntakeFinding] = []
        manifest_rec = self._manifest_builder.build(
            service="svos.intake",
            strategy=strategy,
            dataset_id=dataset_id,
            parameters={"actor": actor},
        )

        # ── validate specification ────────────────────────────────────────
        findings += self._validate_spec(specification)

        # ── validate catalog entry ────────────────────────────────────────
        from core.strategy_registry import get_strategy_manifest

        catalog_manifest = (
            get_strategy_manifest(strategy, self._platform.catalog_path) or {}
        )
        findings += self._validate_catalog(catalog_manifest)

        status = "FAIL" if any(f.severity == "ERROR" for f in findings) else "PASS"

        # ── register version ──────────────────────────────────────────────
        version_rec = self._platform.registry.ensure_spec_version(
            strategy,
            specification=specification,
            actor=actor,
            reason=f"intake:{status.lower()}",
        )

        # ── produce intake report artifact ────────────────────────────────
        report_path = self._builder.build_intake_report(
            strategy=strategy,
            version_id=version_rec.version_id,
            status=status,
            findings=[f.to_dict() for f in findings],
            specification_hash=self._spec_hash(specification),
            manifest=manifest_rec.to_dict(),
            catalog=dict(catalog_manifest),
        )

        # ── record evidence ───────────────────────────────────────────────
        evidence = self._platform.record_report_evidence(
            strategy=strategy,
            stage="INTAKE",
            service="svos.intake",
            report_type="intake_report.json",
            artifact_path=report_path,
            status=status,
            metadata={
                "version_id": version_rec.version_id,
                "manifest_id": manifest_rec.manifest_id,
                "finding_count": len(findings),
            },
        )

        # ── transition DRAFT → INTAKE (only when PASS) ────────────────────
        if status == "PASS":
            try:
                current = self._platform.registry.get_strategy_record(strategy)
                if current.current_stage in ("DRAFT",):
                    self._platform.audited_transition(
                        strategy,
                        to_stage="INTAKE",
                        actor=actor,
                        reason=f"Intake validation passed; version {version_rec.version}",
                    )
            except Exception as exc:
                # Governance may block if already past INTAKE — that is not an error
                if "Illegal lifecycle transition" not in str(exc):
                    raise

        evidence_id = str(
            evidence.get("evidence", {}).get("evidence_id", "")
            or evidence.get("evidence_id", "")
        )

        return IntakeResult(
            strategy=strategy,
            status=status,
            version_id=version_rec.version_id,
            report_artifact=str(report_path),
            evidence_id=evidence_id,
            manifest_id=manifest_rec.manifest_id,
            findings=findings,
            metadata={
                "version": version_rec.version,
                "catalog": dict(catalog_manifest),
            },
        )

    # ── validators ────────────────────────────────────────────────────────

    def _validate_spec(self, specification: str) -> list[IntakeFinding]:
        findings: list[IntakeFinding] = []
        text = (specification or "").strip()
        if not text:
            findings.append(
                IntakeFinding(
                    code="SPEC-001",
                    message="Strategy specification is empty.",
                )
            )
            return findings
        if len(text) < _SPEC_MIN_LENGTH:
            findings.append(
                IntakeFinding(
                    code="SPEC-002",
                    message=f"Specification is too short ({len(text)} chars); minimum {_SPEC_MIN_LENGTH}.",
                    severity="WARN",
                )
            )
        if not re.search(r"(entry|signal|setup|trigger)", text, re.IGNORECASE):
            findings.append(
                IntakeFinding(
                    code="SPEC-003",
                    message="Specification does not describe an entry condition.",
                    severity="WARN",
                )
            )
        if not re.search(r"(stop.?loss|sl\b|invalidat)", text, re.IGNORECASE):
            findings.append(
                IntakeFinding(
                    code="SPEC-004",
                    message="Specification does not define a stop-loss or invalidation rule.",
                    severity="WARN",
                )
            )
        if not re.search(
            r"(risk|lot.?size|position.?siz|0\.\d+%)", text, re.IGNORECASE
        ):
            findings.append(
                IntakeFinding(
                    code="SPEC-005",
                    message="Specification does not state a risk or position sizing rule.",
                    severity="WARN",
                )
            )
        return findings

    def _validate_catalog(self, manifest: dict[str, Any]) -> list[IntakeFinding]:
        findings: list[IntakeFinding] = []
        if not manifest:
            findings.append(
                IntakeFinding(
                    code="CAT-001",
                    message="Strategy is not registered in the catalog.",
                )
            )
            return findings
        for field_name in _REQUIRED_CATALOG_FIELDS:
            if not manifest.get(field_name):
                findings.append(
                    IntakeFinding(
                        code=f"CAT-{field_name.upper()}",
                        message=f"Catalog entry is missing required field: {field_name!r}.",
                    )
                )
        symbols = manifest.get("symbols", [])
        if not symbols or not isinstance(symbols, list):
            findings.append(
                IntakeFinding(
                    code="CAT-SYMBOLS",
                    message="Catalog entry must declare at least one instrument symbol.",
                )
            )
        timeframes = manifest.get("timeframes", [])
        if not timeframes or not isinstance(timeframes, list):
            findings.append(
                IntakeFinding(
                    code="CAT-TIMEFRAMES",
                    message="Catalog entry must declare at least one timeframe.",
                )
            )
        return findings

    @staticmethod
    def _spec_hash(specification: str) -> str:
        import hashlib

        return hashlib.sha256(specification.encode("utf-8")).hexdigest()

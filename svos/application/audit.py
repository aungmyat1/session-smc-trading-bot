"""Strategy Audit Integration — Phase 1 of the SVOS qualification pipeline.

Wraps the existing strategy_validation pipeline and connects its output to:
- the SVOS evidence repository (canonical audit report artifact)
- the governance lifecycle (INTAKE → AUDIT on PASS, INTAKE → REFINEMENT on FAIL)

The audit engine (strategy_validation.pipeline.StrategyValidationPipeline) is
unchanged. This service is a translation layer that converts a ValidationReport
into a qualified SVOS evidence record and drives the lifecycle transition.

Readiness mapping (from strategy_validation scoring):
  READY_FOR_REPLAY    → status PASS  → transition INTAKE → AUDIT
  REQUIRES_REVISION   → status FAIL  → transition INTAKE → REFINEMENT
  INCOMPLETE          → status FAIL  → transition INTAKE → REFINEMENT
  REJECTED            → status FAIL  → transition INTAKE → REFINEMENT
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from svos.application.run_manifest import RunManifest, RunManifestBuilder
from svos.reports.builders import AuditReportBuilder
from svos.shared.support import now_iso


_PASS_DECISIONS = {"READY_FOR_REPLAY"}


@dataclass(slots=True)
class AuditResult:
    strategy: str
    status: str                  # PASS | FAIL
    version_id: str
    readiness_decision: str
    overall_score: float
    report_artifact: str         # absolute path to audit report JSON
    evidence_id: str
    manifest_id: str
    critical_issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommendations: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == "PASS"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["passed"] = self.passed
        return d


class AuditIntegrationService:
    """Runs the strategy audit engine and integrates results with the SVOS platform."""

    def __init__(self, platform: Any) -> None:
        self._platform = platform
        self._builder = AuditReportBuilder(platform.root)
        self._manifest_builder = RunManifestBuilder(platform.root)

    def run(
        self,
        strategy: str,
        specification: str,
        *,
        actor: str = "svos-audit",
        dataset_id: str = "",
    ) -> AuditResult:
        """Execute the audit pipeline for the named strategy.

        Args:
            strategy: Strategy name registered in the SVOS catalog.
            specification: Full strategy specification text.
            actor: Identity of the caller recorded in the audit trail.
            dataset_id: Optional dataset snapshot ID for the run manifest.

        Returns:
            AuditResult with PASS/FAIL, full report artifact, and evidence ID.
        """
        manifest_rec = self._manifest_builder.build(
            service="svos.audit",
            strategy=strategy,
            dataset_id=dataset_id,
            parameters={"actor": actor},
        )

        # ── run the audit engine ──────────────────────────────────────────
        validation_report = self._run_engine(specification, strategy)

        readiness = str(validation_report.readiness_decision)
        status = "PASS" if readiness in _PASS_DECISIONS else "FAIL"
        overall_score = float(validation_report.overall_score)
        critical_issues = list(validation_report.critical_issues)
        warnings_list = list(validation_report.warnings)

        validator_results = [
            r.to_dict() if hasattr(r, "to_dict") else dict(r)
            for r in validation_report.validator_results
        ]
        recommendations = [
            r.to_dict() if hasattr(r, "to_dict") else dict(r)
            for r in validation_report.recommendations
        ]

        # ── ensure strategy is registered ────────────────────────────────
        current = self._platform.registry.ensure_strategy(strategy)

        # ── produce canonical audit report artifact ───────────────────────
        report_path = self._builder.build_audit_report(
            strategy=strategy,
            version_id=current.current_version_id,
            status=status,
            overall_score=overall_score,
            readiness_decision=readiness,
            validator_results=validator_results,
            critical_issues=critical_issues,
            warnings=warnings_list,
            recommendations=recommendations,
            manifest=manifest_rec.to_dict(),
        )

        # ── record evidence ───────────────────────────────────────────────
        evidence = self._platform.record_report_evidence(
            strategy=strategy,
            stage="AUDIT",
            service="svos.audit",
            report_type="audit_report.json",
            artifact_path=report_path,
            status=status,
            metadata={
                "version_id": current.current_version_id,
                "manifest_id": manifest_rec.manifest_id,
                "overall_score": overall_score,
                "readiness_decision": readiness,
            },
        )

        # ── drive lifecycle transition ────────────────────────────────────
        self._drive_lifecycle(strategy, status, actor, current, overall_score, readiness)

        evidence_id = str(
            evidence.get("evidence", {}).get("evidence_id", "")
            or evidence.get("evidence_id", "")
        )

        return AuditResult(
            strategy=strategy,
            status=status,
            version_id=current.current_version_id,
            readiness_decision=readiness,
            overall_score=overall_score,
            report_artifact=str(report_path),
            evidence_id=evidence_id,
            manifest_id=manifest_rec.manifest_id,
            critical_issues=critical_issues,
            warnings=warnings_list,
            recommendations=recommendations,
            metadata={
                "version": current.latest_version,
                "validator_count": len(validator_results),
            },
        )

    def _run_engine(self, specification: str, strategy: str):
        from strategy_validation.models import StrategyDocument
        from strategy_validation.pipeline.strategy_validation_pipeline import StrategyValidationPipeline

        document = StrategyDocument(
            strategy_name=strategy,
            raw_text=specification,
        )
        pipeline = StrategyValidationPipeline()
        return pipeline.run_document(document)

    def _drive_lifecycle(
        self,
        strategy: str,
        status: str,
        actor: str,
        current: Any,
        overall_score: float,
        readiness: str,
    ) -> None:
        current_stage = str(current.current_stage)
        if status == "PASS" and current_stage == "INTAKE":
            target = "AUDIT"
            reason = f"Strategy audit passed (score={overall_score:.1f}%, decision={readiness})"
        elif status == "FAIL" and current_stage in ("INTAKE", "AUDIT"):
            target = "REFINEMENT"
            reason = f"Strategy audit failed (score={overall_score:.1f}%, decision={readiness})"
        else:
            return

        try:
            self._platform.audited_transition(
                strategy,
                to_stage=target,
                actor=actor,
                reason=reason,
            )
        except Exception as exc:
            # If evidence is missing or stage is wrong, do not crash — the
            # AuditResult already records the status; caller can inspect it.
            if "No PASS evidence" not in str(exc) and "Illegal lifecycle" not in str(exc):
                raise

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from svos.application.audit import AuditIntegrationService
from svos.application.backtest import BacktestIntegrationService
from svos.application.intake import IntakeService
from svos.application.replay import ReplayIntegrationService
from svos.application.robustness import RobustnessIntegrationService
from svos.application.virtual_demo import VirtualDemoIntegrationService
from shared.serialization import now_iso, stable_manifest_hash

_PHASES = ("INTAKE", "AUDIT", "REPLAY", "BACKTEST", "ROBUSTNESS", "VIRTUAL_DEMO")


@dataclass
class PhaseOutcome:
    phase: str
    status: str
    evidence_id: str
    report_artifact: str
    manifest_id: str
    elapsed_s: float
    detail: dict


@dataclass
class PipelineResult:
    strategy: str
    status: str
    completed_phases: list[str]
    failed_phase: str | None
    phases: list[PhaseOutcome]
    approval_package_path: str
    evidence_summary: dict[str, str]
    generated_at: str

    @property
    def passed(self) -> bool:
        return self.status == "PASS"

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy,
            "status": self.status,
            "passed": self.passed,
            "completed_phases": self.completed_phases,
            "failed_phase": self.failed_phase,
            "phases": [
                {
                    "phase": p.phase,
                    "status": p.status,
                    "evidence_id": p.evidence_id,
                    "report_artifact": p.report_artifact,
                    "manifest_id": p.manifest_id,
                    "elapsed_s": p.elapsed_s,
                    "detail": p.detail,
                }
                for p in self.phases
            ],
            "approval_package_path": self.approval_package_path,
            "evidence_summary": self.evidence_summary,
            "generated_at": self.generated_at,
        }


class StrategyPipeline:
    def __init__(self, platform: Any) -> None:
        self._platform = platform
        self._intake = IntakeService(platform)
        self._audit = AuditIntegrationService(platform)
        self._replay = ReplayIntegrationService(platform)
        self._backtest = BacktestIntegrationService(platform)
        self._robustness = RobustnessIntegrationService(platform)
        self._virtual_demo = VirtualDemoIntegrationService(platform)

    def run(
        self,
        strategy: str,
        specification: str,
        *,
        trades: list[dict] | None = None,
        metrics: dict | None = None,
        robustness_trades: list[dict] | None = None,
        signals: list[dict] | None = None,
        actor: str = "svos-pipeline",
        dataset_id: str = "",
        expected_pf: float | None = None,
        symbol: str = "EURUSD",
    ) -> PipelineResult:
        phases: list[PhaseOutcome] = []
        completed: list[str] = []
        failed_phase: str | None = None
        version_id: str = ""

        def _run_phase(name: str, fn) -> PhaseOutcome:
            t0 = time.monotonic()
            result = fn()
            elapsed = time.monotonic() - t0
            return PhaseOutcome(
                phase=name,
                status="PASS" if result.passed else "FAIL",
                evidence_id=result.evidence_id,
                report_artifact=result.report_artifact,
                manifest_id=result.manifest_id,
                elapsed_s=round(elapsed, 3),
                detail=result.to_dict(),
            )

        phase_fns: list[tuple[str, Any]] = [
            (
                "INTAKE",
                lambda: self._intake.run(
                    strategy, specification, actor=actor, dataset_id=dataset_id
                ),
            ),
            (
                "AUDIT",
                lambda: self._audit.run(
                    strategy, specification, actor=actor, dataset_id=dataset_id
                ),
            ),
            (
                "REPLAY",
                lambda: self._replay.run(
                    strategy,
                    trades or [],
                    actor=actor,
                    dataset_id=dataset_id,
                ),
            ),
            (
                "BACKTEST",
                lambda: self._backtest.run(
                    strategy,
                    metrics or {},
                    actor=actor,
                    dataset_id=dataset_id,
                ),
            ),
            (
                "ROBUSTNESS",
                lambda: self._robustness.run(
                    strategy,
                    robustness_trades or trades or [],
                    actor=actor,
                    dataset_id=dataset_id,
                ),
            ),
            (
                "VIRTUAL_DEMO",
                lambda: self._virtual_demo.run(
                    strategy,
                    signals or [],
                    actor=actor,
                    dataset_id=dataset_id,
                    expected_pf=expected_pf,
                    symbol=symbol,
                ),
            ),
        ]

        for name, fn in phase_fns:
            if failed_phase is not None:
                phases.append(
                    PhaseOutcome(
                        phase=name,
                        status="SKIPPED",
                        evidence_id="",
                        report_artifact="",
                        manifest_id="",
                        elapsed_s=0.0,
                        detail={},
                    )
                )
                continue

            outcome = _run_phase(name, fn)
            phases.append(outcome)

            if outcome.status == "PASS":
                completed.append(name)
                if name == "INTAKE":
                    version_id = outcome.detail.get("version_id", "")
            else:
                failed_phase = name

        all_passed = failed_phase is None
        pipeline_status = "PASS" if all_passed else ("FAIL" if failed_phase else "PARTIAL")

        evidence_summary = {
            p.phase: p.evidence_id for p in phases if p.status == "PASS"
        }

        approval_path = ""
        if all_passed:
            approval_path = self._write_approval_package(
                strategy, version_id, phases, evidence_summary
            )

        return PipelineResult(
            strategy=strategy,
            status=pipeline_status,
            completed_phases=completed,
            failed_phase=failed_phase,
            phases=phases,
            approval_package_path=approval_path,
            evidence_summary=evidence_summary,
            generated_at=now_iso(),
        )

    def _write_approval_package(
        self,
        strategy: str,
        version_id: str,
        phases: list[PhaseOutcome],
        evidence_summary: dict[str, str],
    ) -> str:
        short_vid = version_id[:12] if version_id else "unknown"
        out_dir = Path("data/svos/approvals") / strategy
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"approval_{short_vid}.json"

        package = {
            "strategy": strategy,
            "version_id": version_id,
            "status": "APPROVED_PHASE5",
            "generated_at": now_iso(),
            "evidence_ids": evidence_summary,
            "report_artifacts": {p.phase: p.report_artifact for p in phases},
            "manifest_ids": {p.phase: p.manifest_id for p in phases},
        }
        package["manifest_hash"] = stable_manifest_hash(package)

        out_path.write_text(json.dumps(package, indent=2))
        return str(out_path)

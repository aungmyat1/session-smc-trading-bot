"""Manifest-driven research queue for replay/backtest/report workflows."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

from core.strategy_registry import get_strategy_manifest

_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_QUEUE_PATH = _ROOT / "config" / "research_queue.yaml"
_DEFAULT_OUTPUT_DIR = _ROOT / "reports" / "research_queue"


@dataclass
class ResearchStep:
    name: str
    command: list[str] = field(default_factory=list)
    cwd: Optional[str] = None
    blocked: bool = False
    reason: str = ""


@dataclass
class ResearchJob:
    job_id: str
    strategy: str
    steps: list[ResearchStep]
    symbol: str | None = None
    start: str | None = None
    end: str | None = None
    notes: str = ""


@dataclass
class StepResult:
    name: str
    skipped: bool
    returncode: int | None = None
    command: list[str] = field(default_factory=list)
    stdout_path: str | None = None
    stderr_path: str | None = None
    message: str = ""


@dataclass
class JobResult:
    job_id: str
    strategy: str
    status: str
    started_at: str
    finished_at: str
    manifest_status: str = ""
    manifest_approved: bool = False
    steps: list[StepResult] = field(default_factory=list)
    report_path: str | None = None


def load_research_queue(path: Path | str | None = None) -> list[ResearchJob]:
    """Load a manifest-driven research queue from YAML."""
    queue_path = Path(path) if path is not None else _DEFAULT_QUEUE_PATH
    if not queue_path.exists():
        return []
    with queue_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    jobs_data = payload.get("jobs", []) if isinstance(payload, dict) else []
    jobs: list[ResearchJob] = []
    for index, item in enumerate(jobs_data, start=1):
        if not isinstance(item, dict):
            continue
        steps_data = item.get("steps", [])
        steps: list[ResearchStep] = []
        for step in steps_data:
            if not isinstance(step, dict):
                continue
            command = step.get("command") or []
            if isinstance(command, str):
                command = [command]
            steps.append(
                ResearchStep(
                    name=str(step.get("name", "")).strip(),
                    command=[str(part) for part in command],
                    cwd=step.get("cwd"),
                    blocked=bool(step.get("blocked", False)),
                    reason=str(step.get("reason", "")),
                )
            )
        strategy = str(item.get("strategy", "")).strip()
        job_id = str(item.get("job_id") or item.get("id") or f"{strategy or 'job'}-{index}")
        jobs.append(
            ResearchJob(
                job_id=job_id,
                strategy=strategy,
                steps=steps,
                symbol=item.get("symbol"),
                start=item.get("start"),
                end=item.get("end"),
                notes=str(item.get("notes", "")),
            )
        )
    return jobs


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _run_command(command: list[str], cwd: Path, stdout_path: Path, stderr_path: Path) -> int:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        check=False,
        text=True,
        capture_output=True,
    )
    _write_text(stdout_path, completed.stdout or "")
    _write_text(stderr_path, completed.stderr or "")
    return int(completed.returncode)


def _render_report(job: ResearchJob, result: JobResult) -> str:
    lines = [
        f"# Research Job Report - {job.job_id}",
        "",
        f"- Strategy: `{job.strategy}`",
        f"- Manifest status: `{result.manifest_status}`",
        f"- Approved: `{str(result.manifest_approved).lower()}`",
        f"- Status: `{result.status}`",
        f"- Started at: `{result.started_at}`",
        f"- Finished at: `{result.finished_at}`",
    ]
    if job.symbol:
        lines.append(f"- Symbol: `{job.symbol}`")
    if job.start or job.end:
        lines.append(f"- Window: `{job.start or 'n/a'}` -> `{job.end or 'n/a'}`")
    if job.notes:
        lines.extend(["", "## Notes", job.notes])
    lines.extend(["", "## Steps"])
    for step in result.steps:
        if step.skipped:
            outcome = "blocked" if step.message.startswith("blocked") else "skipped"
            if step.message:
                outcome = f"{outcome} ({step.message})"
        else:
            outcome = f"exit={step.returncode}"
        lines.append(f"- {step.name}: {outcome}")
    return "\n".join(lines) + "\n"


def _result_payload(result: JobResult) -> dict[str, Any]:
    return {
        "job_id": result.job_id,
        "strategy": result.strategy,
        "status": result.status,
        "started_at": result.started_at,
        "finished_at": result.finished_at,
        "manifest_status": result.manifest_status,
        "manifest_approved": result.manifest_approved,
        "steps": [step.__dict__ for step in result.steps],
        "report_path": result.report_path,
    }


def run_research_job(
    job: ResearchJob,
    output_dir: Path | str | None = None,
    dry_run: bool = False,
    root: Path | None = None,
) -> JobResult:
    """Run one research job and collect step results."""
    root_path = root or _ROOT
    out_dir = Path(output_dir) if output_dir is not None else _DEFAULT_OUTPUT_DIR
    job_dir = out_dir / job.job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(timezone.utc).isoformat()
    manifest = get_strategy_manifest(job.strategy)
    manifest_status = str(manifest.get("status", "draft")) if manifest else "missing"
    manifest_approved = bool(manifest.get("approved", False)) if manifest else False

    result = JobResult(
        job_id=job.job_id,
        strategy=job.strategy,
        status="running",
        started_at=started_at,
        finished_at=started_at,
        manifest_status=manifest_status,
        manifest_approved=manifest_approved,
    )

    if manifest is None:
        result.status = "failed"
        result.finished_at = datetime.now(timezone.utc).isoformat()
        result.steps.append(
            StepResult(name="catalog", skipped=True, message="strategy not found in catalog")
        )
        report_path = job_dir / "report.md"
        result.report_path = str(report_path)
        _write_json(job_dir / "result.json", _result_payload(result))
        _write_text(report_path, _render_report(job, result))
        return result

    for step in job.steps:
        stdout_path = job_dir / f"{step.name}.stdout.log"
        stderr_path = job_dir / f"{step.name}.stderr.log"
        if step.name == "report":
            result.steps.append(
                StepResult(name=step.name, skipped=True, message="report generated inline")
            )
            continue
        if step.blocked:
            result.status = "blocked"
            result.steps.append(
                StepResult(
                    name=step.name,
                    skipped=True,
                    message=step.reason or "blocked by policy",
                )
            )
            break
        if not step.command:
            result.status = "failed"
            result.steps.append(
                StepResult(name=step.name, skipped=True, message="missing command")
            )
            break
        if dry_run:
            result.steps.append(
                StepResult(name=step.name, skipped=True, command=step.command, message="dry run")
            )
            continue
        rc = _run_command(step.command, Path(step.cwd) if step.cwd else root_path, stdout_path, stderr_path)
        result.steps.append(
            StepResult(
                name=step.name,
                skipped=False,
                returncode=rc,
                command=step.command,
                stdout_path=str(stdout_path),
                stderr_path=str(stderr_path),
            )
        )
        if rc != 0:
            result.status = "failed"
            break

    if result.status == "running":
        result.status = "passed"
    result.finished_at = datetime.now(timezone.utc).isoformat()
    report_path = job_dir / "report.md"
    result.report_path = str(report_path)
    _write_json(job_dir / "result.json", _result_payload(result))
    _write_text(report_path, _render_report(job, result))
    return result


def run_research_queue(
    path: Path | str | None = None,
    output_dir: Path | str | None = None,
    dry_run: bool = False,
) -> list[JobResult]:
    """Run every job in the queue sequentially."""
    results: list[JobResult] = []
    for job in load_research_queue(path):
        results.append(run_research_job(job, output_dir=output_dir, dry_run=dry_run))
    return results

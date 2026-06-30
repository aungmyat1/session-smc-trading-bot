from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dashboard.control_state import load_control_state, mark_report_reviewed
from dashboard.status_mapper import recommendation_badge
from scripts import generate_reports as report_cli

ROOT = Path(__file__).resolve().parents[1]
REPORTS_ROOT = ROOT / "reports"
REPORT_INDEX_PATH = REPORTS_ROOT / "index.json"

REPORT_TYPE_TO_DIR = {
    "daily": "daily",
    "weekly": "weekly",
    "monthly": "monthly",
    "strategy": "strategy",
    "risk": "risk",
    "execution": "execution",
    "system-health": "system_health",
    "incident": "incidents",
    "live-readiness": "live_readiness",
}

STATIC_REPORTS = {
    "strategy-audit-loop": Path("docs") / "SVOS_STRATEGY_AUDIT_LOOP_REPORT.md",
}


@dataclass
class ReportRecord:
    report_id: str
    report_type: str
    path: str
    created_at: str
    filename: str
    title: str


def _read_report_title(path: Path) -> str:
    try:
        first = path.read_text(encoding="utf-8").splitlines()[0].strip()
    except Exception:
        return path.stem
    return first.lstrip("# ").strip() or path.stem


def _build_record(path: Path, report_type: str) -> ReportRecord:
    rel = path.relative_to(ROOT).as_posix()
    return ReportRecord(
        report_id=rel.replace("/", "__"),
        report_type=report_type,
        path=rel,
        created_at=datetime.fromtimestamp(
            path.stat().st_mtime, tz=timezone.utc
        ).isoformat(),
        filename=path.name,
        title=_read_report_title(path),
    )


def scan_reports() -> list[ReportRecord]:
    records: list[ReportRecord] = []
    for report_type, dirname in REPORT_TYPE_TO_DIR.items():
        directory = REPORTS_ROOT / dirname
        if not directory.exists():
            continue
        for path in sorted(
            directory.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True
        ):
            records.append(_build_record(path, report_type))
    for report_type, relative_path in STATIC_REPORTS.items():
        path = ROOT / relative_path
        if path.exists():
            records.append(_build_record(path, report_type))
    svos_directory = REPORTS_ROOT / "svos"
    if svos_directory.exists():
        for path in sorted(
            svos_directory.glob("**/*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            records.append(_build_record(path, "svos-stage"))
    records.sort(key=lambda item: item.created_at, reverse=True)
    return records


def _safe_report_path(report_id: str) -> Path | None:
    relative = Path(report_id.replace("__", "/"))
    path = ROOT / relative
    try:
        resolved = path.resolve()
        root_resolved = ROOT.resolve()
    except Exception:
        return None
    if not resolved.is_file():
        return None
    if not str(resolved).startswith(str(root_resolved)):
        return None
    if resolved.suffix.lower() not in {".md", ".json", ".html"}:
        return None
    return resolved


def write_index() -> dict[str, Any]:
    records = scan_reports()
    latest: dict[str, dict[str, Any]] = {}
    for record in records:
        latest.setdefault(record.report_type, record.__dict__)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reports": [record.__dict__ for record in records],
        "latest": latest,
    }
    REPORT_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_INDEX_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    return payload


def load_index() -> dict[str, Any]:
    if not REPORT_INDEX_PATH.exists():
        return write_index()
    try:
        payload = json.loads(REPORT_INDEX_PATH.read_text(encoding="utf-8"))
    except Exception:
        return write_index()
    if not isinstance(payload, dict):
        return write_index()
    return payload


def latest_reports() -> dict[str, Any]:
    payload = write_index()
    control = load_control_state()
    latest = payload.get("latest", {})
    recommendation = "CONTINUE"
    for key in ("live-readiness", "daily", "risk", "system-health"):
        record = latest.get(key)
        if not record:
            continue
        text = read_report(record["report_id"]).get("content", "")
        if "Final verdict:" in text:
            marker = text.split("Final verdict:", 1)[1].split("`", 2)
            recommendation = recommendation_badge(
                marker[1] if len(marker) > 1 else "REVIEW"
            )
            break
        if "Final recommendation:" in text:
            marker = text.split("Final recommendation:", 1)[1].split("`", 2)
            recommendation = recommendation_badge(
                marker[1] if len(marker) > 1 else "REVIEW"
            )
            break
    return {
        "generated_at": payload.get("generated_at"),
        "latest": latest,
        "recommendation_badge": recommendation,
        "reviewed": control.get("reports_reviewed", {}),
    }


def read_report(report_id: str) -> dict[str, Any]:
    payload = load_index()
    for record in payload.get("reports", []):
        if record.get("report_id") != report_id:
            continue
        path = ROOT / record["path"]
        return {
            **record,
            "content": path.read_text(encoding="utf-8"),
        }
    fallback = _safe_report_path(report_id)
    if fallback is not None:
        rel = fallback.relative_to(ROOT).as_posix()
        return {
            **_build_record(fallback, "ad-hoc").__dict__,
            "report_id": report_id,
            "path": rel,
            "content": fallback.read_text(encoding="utf-8"),
        }
    raise FileNotFoundError(report_id)


def generate(report_type: str) -> dict[str, Any]:
    artifacts = report_cli.generate_many(report_type, root=ROOT)
    index = write_index()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "report_type": report_type,
        "artifacts": [
            {
                "report_type": artifact.report_type,
                "path": str(artifact.path.relative_to(ROOT)),
                "filename": artifact.path.name,
            }
            for artifact in artifacts
        ],
        "latest": index.get("latest", {}),
    }


def mark_reviewed(report_id: str) -> dict[str, Any]:
    state = mark_report_reviewed(report_id)
    return {
        "report_id": report_id,
        "reviewed_at": state["reports_reviewed"].get(report_id, ""),
    }

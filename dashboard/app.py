#!/usr/bin/env python3
# ruff: noqa: E402
"""
ISOP Control Panel — Dashboard API server.

Serves:
  GET /api/svos          — SVOS panel data (strategy catalog + last run)
  GET /api/evf           — EVF panel data (last validation report)
  GET /api/trades        — Live trade status (journal + open positions)
  GET /api/status        — System health summary
  GET /api/rgm           — Risk qualification and emergency state
  GET /api/governance    — Approval / promotion control-plane state
  GET /api/smo           — Monitoring, incidents, drift-facing summary
  GET /api/reports       — Report index
  GET /api/reports/latest
  GET /api/reports/<report_id>
  POST /api/reports/generate
  POST /api/reports/generate/all
  POST /api/emergency-stop
  POST /api/emergency-stop/clear
  POST /api/svos/run     — Trigger SVOS run (confirm token required)
  POST /api/evf/run      — Trigger EVF run  (confirm token required)

Run:
  pip install flask pyyaml
  python dashboard/app.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

_SUBPROCESS_TIMEOUT = int(os.getenv("DASHBOARD_SUBPROCESS_TIMEOUT", "120"))

try:
    from flask import Flask, jsonify, request, send_from_directory
    from flask_cors import CORS
except ImportError:
    print("Flask not installed. Run: pip install flask flask-cors")
    sys.exit(1)

from dashboard.runtime import dashboard_bind_host, dashboard_public_host, dashboard_url
from dashboard.auth import require_operator
from dashboard.audit_log import tail_audit_log, write_audit_log
from dashboard.control_state import activate_emergency_stop, clear_emergency_stop, load_control_state, mark_incident_reviewed
from dashboard.report_service import generate as generate_reports_payload
from dashboard.report_service import latest_reports, load_index, mark_reviewed, read_report
from dashboard.status_mapper import health_to_status
from dashboard import strategy_service, gemini_service, pipeline_service, live_dashboard_service
import scripts.health_check as health_check
from svos.api.service import SVOSOperationalAPI

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

app = Flask(__name__, static_folder=str(Path(__file__).parent / "static"))
_allowed_origins = [
    item.strip()
    for item in os.getenv(
        "DASHBOARD_ALLOWED_ORIGINS",
        "http://127.0.0.1:8080,http://localhost:8080",
    ).split(",")
    if item.strip()
]
CORS(app, resources={r"/api/*": {"origins": _allowed_origins}})

_CATALOG_PATH = _ROOT / "config" / "strategy_catalog.yaml"
_EVF_REPORTS_DIR = _ROOT / "execution_validation" / "reports"
_JOURNAL_PATHS = [
    _ROOT / "logs" / "trades.jsonl",
    _ROOT / "logs" / "adaptive_trades.jsonl",
    _ROOT / "logs" / "strategy_demo_trades.jsonl",
    _ROOT / "logs" / "st_a2_demo_trades.jsonl",
    _ROOT / "logs" / "portfolio_demo_trades.jsonl",
]
_SVOS_REPORTS_DIR = _ROOT / "reports" / "current_strategy_svos"
_SVOS_CANONICAL_REPORTS_DIR = _ROOT / "reports" / "svos"
_ARCHITECTURE_PATH = _ROOT / "docs" / "SYSTEM_ARCHITECTURE.md"
_BOT_LOG = _ROOT / "logs" / "bot.log"
_READINESS_REPORT_JSON = _ROOT / "reports" / "production_readiness_report.json"
_TESTING_REPORT_JSON = _ROOT / "reports" / "testing_report.json"
_QUALITY_REPORT_JSON = _ROOT / "reports" / "quality_report.json"
_STABILIZATION_STATUS_PATH = _ROOT / "docs" / "svos" / "STABILIZATION_STATUS.md"
_NEW_DASHBOARD_ROOT = _ROOT / "New Dashborad"
_NEW_DASHBOARD_DIST = _NEW_DASHBOARD_ROOT / "dist"
_LIVE_DASHBOARD_HTML = Path(__file__).parent / "live_dashboard.html"
_RUNNER_LOGS = [
    _ROOT / "logs" / "strategy_demo.log",
    _ROOT / "logs" / "st_a2_demo.log",
    _ROOT / "logs" / "st_a2_runner.log",
]
_RUNNER_LOG = _RUNNER_LOGS[-1]
_DEMO_STATE_PATH = _ROOT / "logs" / "strategy_demo_state.json"

_SVOS_STAGE_FILE_MAP = {
    "intake": ("00_intake.md", "00_intake.json"),
    "audit": ("01_audit.md", "01_audit.json"),
    "enhancement": ("02_enhancement.md", "02_enhancement.json"),
    "replay": ("03_replay.md", "03_replay.json"),
    "backtest": ("04_backtest.md", "04_backtest.json"),
    "robustness": ("05_robustness.md", "05_robustness.json"),
    "verification_ready": ("06_verification_ready.md", "06_verification_ready.json"),
    "virtual_demo": ("07_virtual_demo.md", "07_virtual_demo.json"),
    "production_approval": ("08_production_approval.md", "08_production_approval.json"),
}
# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_yaml(path: Path) -> dict[str, Any]:
    if yaml is None or not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _read_jsonl(path: Path, limit: int = 200) -> list[dict]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    records = []
    for line in lines[-limit:]:
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


def _latest_evf_report() -> dict[str, Any]:
    """Return the most-recent EVF JSON report or empty dict."""
    if not _EVF_REPORTS_DIR.exists():
        return {}
    candidates = sorted(_EVF_REPORTS_DIR.glob("**/*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in candidates:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
    return {}


def _latest_svos_report(strategy: str) -> dict[str, Any]:
    strategy_dir = _SVOS_REPORTS_DIR / strategy
    if not strategy_dir.exists():
        return {}
    candidates = sorted(strategy_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in candidates:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
    return {}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _demo_runner_state() -> dict[str, Any]:
    payload = _read_json(_DEMO_STATE_PATH)
    return payload if isinstance(payload, dict) else {}


def _demo_health_payload() -> dict[str, Any]:
    state = _demo_runner_state()
    records = _all_trades()
    latest_trade = records[0] if records else {}
    last_signal = state.get("last_signal") or {}
    return {
        "status": state.get("status", "stopped"),
        "broker": state.get("broker_status", "unknown"),
        "strategy": state.get("strategy_status", "inactive"),
        "execution_status": state.get("execution_status", state.get("status", "unknown")),
        "strategy_status": state.get("strategy_status", "inactive"),
        "broker_status": state.get("broker_status", "unknown"),
        "last_signal": last_signal.get("timestamp") or "",
        "last_trade": latest_trade.get("timestamp") or latest_trade.get("ts") or "",
        "updated_at": state.get("updated_at", ""),
    }


def _svos_stage_report_payload(strategy: str) -> dict[str, Any]:
    stage_dir = _SVOS_REPORTS_DIR / strategy / "stages"
    index_path = stage_dir / "index.json"
    index = _read_json(index_path)
    entries = index.get("stages", []) if isinstance(index.get("stages"), list) else []
    stage_reports: list[dict[str, Any]] = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        stage_name = str(entry.get("stage", "")).strip()
        file_pair = _SVOS_STAGE_FILE_MAP.get(stage_name)
        markdown_rel = ""
        json_rel = ""
        markdown_exists = False
        json_exists = False
        if file_pair:
            markdown_path = stage_dir / file_pair[0]
            json_path = stage_dir / file_pair[1]
            markdown_exists = markdown_path.exists()
            json_exists = json_path.exists()
            if markdown_exists:
                markdown_rel = markdown_path.relative_to(_ROOT).as_posix()
            if json_exists:
                json_rel = json_path.relative_to(_ROOT).as_posix()
        stage_reports.append({
            "phase": entry.get("phase"),
            "stage": stage_name,
            "status": entry.get("status", "UNKNOWN"),
            "can_promote": bool(entry.get("can_promote", False)),
            "next_stage": entry.get("next_stage"),
            "created_at": entry.get("created_at", ""),
            "markdown_path": markdown_rel,
            "json_path": json_rel,
            "markdown_report_id": markdown_rel.replace("/", "__") if markdown_rel else "",
            "json_report_id": json_rel.replace("/", "__") if json_rel else "",
            "has_markdown": markdown_exists,
            "has_json": json_exists,
            "label": stage_name.replace("_", " ").title(),
        })

    return {
        "strategy": strategy,
        "stage_index_path": index_path.relative_to(_ROOT).as_posix() if index_path.exists() else "",
        "stage_reports": stage_reports,
        "overall_status": index.get("overall_status", ""),
        "promoted_stage": index.get("promoted_stage"),
        "updated_at": index.get("updated_at", ""),
    }


def _report_path_payload(path_value: Any, fallback: Path) -> dict[str, Any]:
    path = Path(str(path_value)) if path_value else fallback
    if not path.is_absolute():
        path = _ROOT / path
    try:
        resolved = path.resolve()
        relative = resolved.relative_to(_ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return {"path": "", "report_id": "", "exists": False}
    return {
        "path": relative if resolved.is_file() else "",
        "report_id": relative.replace("/", "__") if resolved.is_file() else "",
        "exists": resolved.is_file(),
    }


def _latest_canonical_svos_payload(strategy: str) -> dict[str, Any]:
    if not _SVOS_CANONICAL_REPORTS_DIR.exists():
        return {}
    candidates = sorted(
        _SVOS_CANONICAL_REPORTS_DIR.glob("**/run_summary.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    summary: dict[str, Any] = {}
    summary_path: Path | None = None
    for candidate in candidates:
        payload = _read_json(candidate)
        if payload.get("strategy_name") == strategy or payload.get("strategy_id") == strategy:
            summary = payload
            summary_path = candidate
            break
    if summary_path is None:
        return {}

    stage_reports: list[dict[str, Any]] = []
    for entry in summary.get("stages", []):
        if not isinstance(entry, dict):
            continue
        stage = str(entry.get("stage", ""))
        json_fallback = summary_path.parent / f"{stage}.json"
        markdown_fallback = summary_path.parent / f"{stage}.md"
        json_report = _report_path_payload(entry.get("json_path"), json_fallback)
        markdown_report = _report_path_payload(entry.get("markdown_path"), markdown_fallback)
        detail = _read_json(_ROOT / json_report["path"]) if json_report["path"] else {}
        remediation = detail.get("remediation", {}) if isinstance(detail.get("remediation"), dict) else {}
        findings = detail.get("findings", []) if isinstance(detail.get("findings"), list) else []
        stage_reports.append(
            {
                "stage": stage,
                "label": entry.get("stage_label", stage.replace("_", " ").title()),
                "status": entry.get("status", "NOT_RUN"),
                "score": entry.get("score"),
                "promotion_allowed": bool(entry.get("promotion_allowed", False)),
                "report_id": entry.get("report_id", ""),
                "markdown_path": markdown_report["path"],
                "markdown_report_id": markdown_report["report_id"],
                "json_path": json_report["path"],
                "json_report_id": json_report["report_id"],
                "remediation_route": remediation.get("route", ""),
                "remediation_actions": remediation.get("actions", []),
                "finding_count": len(findings),
                "metrics": detail.get("metrics", {}),
                "thresholds": detail.get("thresholds", {}),
                "sections": detail.get("sections", {}),
                "visualizations": detail.get("visualizations", []),
                "decision": (detail.get("sections", {}) or {}).get("decision", {}),
                "next_action": (detail.get("sections", {}) or {}).get("next_action", ""),
            }
        )

    summary_markdown = _report_path_payload("", summary_path.with_suffix(".md"))
    summary_json = _report_path_payload(summary_path, summary_path)
    supporting_reports = []
    for stem, label in (
        ("00_strategy_summary", "New Strategy Summary"),
        ("strategy_evolution", "Strategy Evolution"),
        ("failure_analysis", "Failure Analysis"),
        ("improvement_report", "Improvement Report"),
        ("final_qualification", "Final Qualification"),
    ):
        json_report = _report_path_payload("", summary_path.parent / f"{stem}.json")
        markdown_report = _report_path_payload("", summary_path.parent / f"{stem}.md")
        if json_report["exists"] or markdown_report["exists"]:
            supporting_reports.append(
                {
                    "report_type": stem,
                    "label": label,
                    "json_report_id": json_report["report_id"],
                    "markdown_report_id": markdown_report["report_id"],
                }
            )
    return {
        "run_id": summary.get("run_id", ""),
        "strategy_id": summary.get("strategy_id", strategy),
        "strategy_version": summary.get("strategy_version", ""),
        "overall_status": summary.get("overall_status", ""),
        "latest_passed_stage": summary.get("latest_passed_stage", ""),
        "active_blocker": summary.get("active_blocker", ""),
        "next_task": summary.get("next_task", ""),
        "promoted_stage": summary.get("promoted_stage"),
        "generated_at": summary.get("generated_at", ""),
        "summary_markdown_report_id": summary_markdown["report_id"],
        "summary_json_report_id": summary_json["report_id"],
        "report_dir": summary_path.parent.relative_to(_ROOT).as_posix(),
        "stages": stage_reports,
        "supporting_reports": supporting_reports,
    }


def _all_trades() -> list[dict]:
    records = []
    for path in _JOURNAL_PATHS:
        records.extend(_read_jsonl(path))
    records.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    return records


def _trade_stats(records: list[dict]) -> dict[str, Any]:
    closed = [
        r for r in records
        if r.get("record_type") != "signal"
        and (r.get("result_r") is not None or r.get("result_R") is not None or r.get("r_multiple") is not None)
    ]
    if not closed:
        return {"total": 0, "wins": 0, "losses": 0, "win_rate": 0.0, "avg_r": 0.0, "total_r": 0.0}
    def _r_value(record: dict[str, Any]) -> float:
        raw = record.get("result_r", record.get("result_R", record.get("r_multiple", 0))) or 0
        try:
            return float(raw)
        except (TypeError, ValueError):
            return 0.0

    wins = [r for r in closed if _r_value(r) > 0]
    losses = [r for r in closed if _r_value(r) <= 0]
    total_r = sum(_r_value(r) for r in closed)
    avg_r = total_r / len(closed)
    win_rate = len(wins) / len(closed) * 100 if closed else 0
    return {
        "total": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 1),
        "avg_r": round(avg_r, 3),
        "total_r": round(total_r, 3),
    }


def _latest_architecture_status() -> dict[str, Any]:
    text = _ARCHITECTURE_PATH.read_text(encoding="utf-8") if _ARCHITECTURE_PATH.exists() else ""
    current = "SVOS transitional v1.7" if "SVOS transitional v1.7" in text else ""
    target = "ISOP v2" if "ISOP v2" in text else ""
    return {"current_architecture": current or "transitional", "target_architecture": target or "ISOP v2"}


def _stabilization_status() -> dict[str, Any]:
    text = _read_text(_STABILIZATION_STATUS_PATH)
    verdict = ""
    for line in text.splitlines():
        if line.startswith("Verdict:"):
            verdict = line.split("Verdict:", 1)[1].strip()
            break
    return {
        "path": str(_STABILIZATION_STATUS_PATH.relative_to(_ROOT)) if _STABILIZATION_STATUS_PATH.exists() else "",
        "verdict": verdict,
        "content": text,
    }


def _readiness_payload(platform_api: SVOSOperationalAPI | None = None) -> dict[str, Any]:
    readiness = _read_json(_READINESS_REPORT_JSON)
    testing = _read_json(_TESTING_REPORT_JSON)
    quality = _read_json(_QUALITY_REPORT_JSON)
    api = platform_api or _platform_api()
    persistence = api.platform.persistence_status()
    return {
        "production_readiness": readiness,
        "testing": testing,
        "quality": quality,
        "stabilization": _stabilization_status(),
        "persistence": persistence,
    }


def _latest_log_lines(limit: int = 200) -> list[str]:
    lines: list[str] = []
    for path in (_BOT_LOG, *_RUNNER_LOGS):
        if not path.exists():
            continue
        lines.extend(path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:])
    return lines[-limit:]


def _is_benign_runtime_line(line: str) -> bool:
    text = str(line or "").lower()
    return "engineio.client" in text and "packet queue is empty, aborting" in text


def _incident_summary(limit: int = 20) -> dict[str, Any]:
    lines = _latest_log_lines(600)
    incidents = [
        line for line in lines
        if any(token in line for token in ("ERROR", "CRITICAL", "FATAL", "WARN", "DISCONNECTED", "disconnect"))
        and not _is_benign_runtime_line(line)
    ]
    audit = tail_audit_log(limit=limit)
    return {
        "incident_count": len(incidents),
        "critical_count": sum(1 for line in incidents if "CRITICAL" in line or "FATAL" in line),
        "recent_incidents": incidents[-limit:],
        "recent_audit": audit[-limit:],
    }


def _incident_id(prefix: str, text: str) -> str:
    digest = hashlib.sha1(f"{prefix}:{text}".encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def _decorate_incidents(lines: list[str], reviewed: dict[str, str], prefix: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for line in lines:
        incident_id = _incident_id(prefix, line)
        items.append({
            "id": incident_id,
            "text": line,
            "reviewed_at": reviewed.get(incident_id, ""),
            "acknowledged": incident_id in reviewed,
        })
    return items


def _current_catalog_state() -> tuple[str, dict[str, Any], dict[str, Any]]:
    catalog = _read_yaml(_CATALOG_PATH)
    strategies = catalog.get("strategies", {})
    current = catalog.get("current_strategy", "")
    current_meta = strategies.get(current, {}) if isinstance(strategies, dict) else {}
    if not isinstance(current_meta, dict):
        current_meta = {}
    return current, current_meta, catalog


def _health_snapshot() -> dict[str, Any]:
    backend, _ = health_check._infer_db_backend()  # type: ignore[attr-defined]
    return {
        "runner": health_check.check_runner(),
        "risk": health_check.check_risk_engine(),
        "portfolio": health_check.check_portfolio(),
        "recovery": health_check.check_recovery(),
        "execution": health_check.check_execution(),
        "database": health_check.check_research_db(backend),
    }


def _platform_api() -> SVOSOperationalAPI:
    return SVOSOperationalAPI(
        root=_ROOT,
        catalog_path=_CATALOG_PATH,
        health_snapshot_factory=_health_snapshot,
        latest_reports_factory=latest_reports,
        control_state_factory=load_control_state,
    )


def _new_dashboard_overview() -> dict[str, Any]:
    api = _platform_api()
    overview = api.overview()
    reports = latest_reports()
    status = _readiness_payload(api)
    return {
        "current_strategy": overview.get("current_strategy", ""),
        "service_status": overview.get("service_status", {}),
        "registry": overview.get("registry", {}),
        "deployment": overview.get("deployment", {}),
        "monitoring": overview.get("monitoring", {}),
        "persistence": overview.get("persistence", {}),
        "reports": reports.get("latest", {}),
        "recommendation_badge": reports.get("recommendation_badge", "REVIEW"),
        "readiness": status,
        "fetched_at": _now_iso(),
    }


def _governance_payload() -> dict[str, Any]:
    current, current_meta, catalog = _current_catalog_state()
    validation_map = _read_yaml(_ROOT / "config" / "validation.yaml")
    architecture = _latest_architecture_status()
    return {
        "current_strategy": current,
        "strategy_status": current_meta.get("status", "unknown"),
        "approved": bool(current_meta.get("approved", False)),
        "deployment_target": current_meta.get("deployment_target", "unknown"),
        "last_svos_status": current_meta.get("last_svos_status", ""),
        "last_svos_verification_ready": bool(current_meta.get("last_svos_verification_ready", False)),
        "last_svos_promoted_stage": current_meta.get("last_svos_promoted_stage", ""),
        "promotion_map": validation_map.get("promotion_map", {}),
        "architecture": architecture,
        "strategy_count": len((catalog.get("strategies") or {})),
        "approval_status": "APPROVED" if current_meta.get("approved") else "PENDING",
    }


def _rgm_payload() -> dict[str, Any]:
    health = _health_snapshot()
    control = load_control_state()
    incidents = _incident_summary(limit=10)
    risk = health["risk"]
    portfolio = health["portfolio"]
    execution = health["execution"]
    breaches = []
    if risk.get("status") == "FAIL":
        breaches.append(risk.get("detail", "risk guard failed"))
    if portfolio.get("status") == "FAIL":
        breaches.append(portfolio.get("detail", "portfolio guard failed"))
    if control["emergency_stop"]["active"]:
        breaches.append(control["emergency_stop"]["reason"] or "dashboard emergency stop active")
    return {
        "risk_status": risk.get("status", "UNKNOWN"),
        "risk_summary": risk.get("detail", ""),
        "portfolio_status": portfolio.get("status", "UNKNOWN"),
        "portfolio_summary": portfolio.get("detail", ""),
        "execution_mode_status": execution.get("status", "UNKNOWN"),
        "recovery_status": health["recovery"].get("status", "UNKNOWN"),
        "emergency_stop": control["emergency_stop"],
        "incident_count": incidents["incident_count"],
        "risk_breaches": breaches,
        "qualification_status": "QUALIFIED" if not breaches and risk.get("status") == "PASS" else "REVIEW",
    }


def _smo_payload() -> dict[str, Any]:
    health = _health_snapshot()
    reports = latest_reports()
    incidents = _incident_summary(limit=20)
    control = load_control_state()
    emergency = control.get("emergency_stop", {})
    reviewed_incidents = control.get("incidents_reviewed", {})
    recent_incident_items = _decorate_incidents(incidents["recent_incidents"], reviewed_incidents, "incident")
    monitoring = health_to_status(health["runner"].get("status", "UNKNOWN"))
    if incidents["critical_count"] > 0 or health["database"].get("status") == "FAIL":
        monitoring = "ALERT"
    elif health["risk"].get("status") != "PASS":
        monitoring = "WATCH"
    return {
        "monitoring_status": monitoring,
        "runner_status": health["runner"],
        "database_status": health["database"],
        "risk_status": health["risk"],
        "execution_status": health["execution"],
        "incident_count": incidents["incident_count"],
        "critical_alerts": incidents["critical_count"],
        "recent_incidents": recent_incident_items,
        "recent_audit": incidents["recent_audit"],
        "emergency_stop": emergency,
        "control_timeline": [entry for entry in incidents["recent_audit"] if str(entry.get("action", "")).startswith("emergency_stop")],
        "incident_reviewed": reviewed_incidents,
        "unacknowledged_incident_count": sum(1 for item in recent_incident_items if not item["acknowledged"]),
        "latest_reports": reports.get("latest", {}),
        "recommendation_badge": reports.get("recommendation_badge", "REVIEW"),
    }


def _run_command(cmd: list[str], *, timeout: int = 120) -> tuple[int, str]:
    proc = subprocess.Popen(cmd, cwd=str(_ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise
    return proc.returncode or 0, out[-4000:]

# ---------------------------------------------------------------------------
# SVOS API
# ---------------------------------------------------------------------------

@app.route("/api/svos")
def api_svos():
    catalog = _read_yaml(_CATALOG_PATH)
    strategies = catalog.get("strategies", {})
    current = catalog.get("current_strategy", "")

    strategy_list = []
    for name, meta in strategies.items():
        if not isinstance(meta, dict):
            meta = {}
        strategy_list.append({
            "name": name,
            "status": meta.get("status", "unknown"),
            "version": meta.get("version", ""),
            "approved": meta.get("approved", False),
            "current": meta.get("current", False),
            "description": meta.get("description", ""),
            "symbols": meta.get("symbols", []),
            "timeframes": meta.get("timeframes", []),
            "requirements": meta.get("requirements", {}),
            "last_svos_at": meta.get("last_svos_at", ""),
            "last_svos_status": meta.get("last_svos_status", ""),
            "last_svos_promoted_stage": meta.get("last_svos_promoted_stage", ""),
        })

    current_report = _latest_svos_report(current) if current else {}
    stage_reports = _svos_stage_report_payload(current) if current else {"stage_reports": []}
    canonical_run = _latest_canonical_svos_payload(current) if current else {}

    return jsonify({
        "current_strategy": current,
        "strategies": strategy_list,
        "current_report": current_report,
        "stage_reports": stage_reports.get("stage_reports", []),
        "stage_report_index_path": stage_reports.get("stage_index_path", ""),
        "stage_report_updated_at": stage_reports.get("updated_at", ""),
        "canonical_run": canonical_run,
        "fetched_at": _now_iso(),
    })


@app.route("/api/svos/run", methods=["POST"])
@require_operator(app, "research_operator", "admin")
def api_svos_run():
    body = request.get_json(silent=True) or {}
    confirm = body.get("confirm_token", "")
    strategy = body.get("strategy", "")
    if confirm != f"CONFIRM-SVOS-{strategy}":
        write_audit_log("svos_run_denied", status="denied", detail={"strategy": strategy, "reason": "invalid_confirm_token"})
        return jsonify({"error": "Invalid or missing CONFIRM token", "required": f"CONFIRM-SVOS-{strategy}"}), 403

    cmd = [sys.executable, str(_ROOT / "scripts" / "run_current_strategy_svos.py"), "--strategy", strategy]
    try:
        rc, out = _run_command(cmd)
        write_audit_log("svos_run", status="completed", detail={"strategy": strategy, "returncode": rc})
        return jsonify({"status": "completed", "returncode": rc, "output": out})
    except subprocess.TimeoutExpired:
        write_audit_log("svos_run", status="timeout", detail={"strategy": strategy})
        return jsonify({"status": "timeout"}), 408
    except Exception as exc:
        write_audit_log("svos_run", status="error", detail={"strategy": strategy, "error": str(exc)})
        return jsonify({"error": str(exc)}), 500

# ---------------------------------------------------------------------------
# EVF API
# ---------------------------------------------------------------------------

@app.route("/api/evf")
def api_evf():
    report = _latest_evf_report()
    checks = report.get("checks", {})
    check_list = [
        {"name": k, "passed": v.get("passed", False), "message": v.get("message", ""), "score": v.get("score", 0)}
        for k, v in checks.items()
    ] if isinstance(checks, dict) else []

    return jsonify({
        "strategy": report.get("strategy", ""),
        "period": report.get("period", ""),
        "status": report.get("status", "UNKNOWN"),
        "final_score": report.get("final_score", 0),
        "created_at": report.get("created_at", ""),
        "signal_accuracy": report.get("signal_accuracy", 0),
        "order_accuracy": report.get("order_accuracy", 0),
        "risk_accuracy": report.get("risk_accuracy", 0),
        "slippage_average_pip": report.get("slippage_average_pip", 0),
        "slippage_p95_pip": report.get("slippage_p95_pip", 0),
        "execution_delay_ms_average": report.get("execution_delay_ms_average", 0),
        "duplicate_order_protection_passed": report.get("duplicate_order_protection_passed", False),
        "spread_handling_passed": report.get("spread_handling_passed", False),
        "slippage_passed": report.get("slippage_passed", False),
        "exit_management_passed": report.get("exit_management_passed", False),
        "recovery_passed": report.get("recovery_passed", False),
        "broker_simulation_passed": report.get("broker_simulation_passed", False),
        "checks": check_list,
        "fetched_at": _now_iso(),
    })


@app.route("/api/evf/run", methods=["POST"])
@require_operator(app, "research_operator", "admin")
def api_evf_run():
    body = request.get_json(silent=True) or {}
    confirm = body.get("confirm_token", "")
    strategy = body.get("strategy", "")
    payload_path = body.get("payload_path", "")
    if confirm != f"CONFIRM-EVF-{strategy}":
        write_audit_log("evf_run_denied", status="denied", detail={"strategy": strategy, "reason": "invalid_confirm_token"})
        return jsonify({"error": "Invalid or missing CONFIRM token", "required": f"CONFIRM-EVF-{strategy}"}), 403

    cmd = [sys.executable, str(_ROOT / "scripts" / "run_evf.py"), "--strategy", strategy]
    if payload_path:
        cmd += ["--payload", payload_path]
    try:
        rc, out = _run_command(cmd)
        write_audit_log("evf_run", status="completed", detail={"strategy": strategy, "returncode": rc, "payload_path": payload_path})
        return jsonify({"status": "completed", "returncode": rc, "output": out})
    except subprocess.TimeoutExpired:
        write_audit_log("evf_run", status="timeout", detail={"strategy": strategy})
        return jsonify({"status": "timeout"}), 408
    except Exception as exc:
        write_audit_log("evf_run", status="error", detail={"strategy": strategy, "error": str(exc)})
        return jsonify({"error": str(exc)}), 500

# ---------------------------------------------------------------------------
# Trade status API
# ---------------------------------------------------------------------------

@app.route("/api/trades")
def api_trades():
    records = _all_trades()
    stats = _trade_stats(records)
    recent = records[:50]
    return jsonify({
        "stats": stats,
        "recent": recent,
        "fetched_at": _now_iso(),
    })


@app.route("/api/demo-runner")
def api_demo_runner():
    return jsonify({
        "runner": _demo_runner_state(),
        "fetched_at": _now_iso(),
    })


@app.route("/health/demo")
def health_demo():
    return jsonify({**_demo_health_payload(), "fetched_at": _now_iso()})


@app.route("/api/status")
def api_status():
    current, current_meta, _ = _current_catalog_state()
    port = int(os.getenv("DASHBOARD_PORT", "8080"))
    bind_host = dashboard_bind_host()
    public_host = dashboard_public_host(bind_host)

    records = _all_trades()
    stats = _trade_stats(records)
    evf = _latest_evf_report()
    rgm = _rgm_payload()
    governance = _governance_payload()
    smo = _smo_payload()
    control = load_control_state()
    canonical_run = _latest_canonical_svos_payload(current) if current else {}
    demo_runner = _demo_runner_state()

    return jsonify({
        "system": "ONLINE",
        "current_strategy": current,
        "strategy_status": current_meta.get("status", "unknown"),
        "strategy_approved": current_meta.get("approved", False),
        "last_svos_status": canonical_run.get("overall_status") or current_meta.get("last_svos_status", ""),
        "last_svos_at": canonical_run.get("generated_at") or current_meta.get("last_svos_at", ""),
        "last_svos_active_blocker": canonical_run.get("active_blocker", ""),
        "evf_status": evf.get("status", "NO REPORT"),
        "evf_score": evf.get("final_score", 0),
        "trade_count": stats["total"],
        "win_rate": stats["win_rate"],
        "live_trading": os.getenv("LIVE_TRADING", "false").lower() == "true",
        "demo_runner_mode": demo_runner.get("mode", ""),
        "demo_runner_status": demo_runner.get("status", ""),
        "execution_status": demo_runner.get("execution_status", ""),
        "broker_status": demo_runner.get("broker_status", ""),
        "demo_runner_strategy": demo_runner.get("strategy", ""),
        "demo_runner_updated_at": demo_runner.get("updated_at", ""),
        "demo_only": demo_runner.get("demo_only"),
        "rgm_risk_status": rgm["qualification_status"],
        "governance_approval": governance["approval_status"],
        "smo_monitoring_status": smo["monitoring_status"],
        "emergency_stop_active": bool(control["emergency_stop"]["active"]),
        "emergency_stop_reason": control["emergency_stop"]["reason"],
        "dashboard_bind_host": bind_host,
        "dashboard_public_host": public_host,
        "dashboard_url": dashboard_url(public_host, port),
        "fetched_at": _now_iso(),
    })


@app.route("/api/platform")
def api_platform():
    return jsonify({**_platform_api().overview(), "fetched_at": _now_iso()})


@app.route("/api/platform/registry")
def api_platform_registry():
    return jsonify({**_platform_api().registry_snapshot(), "fetched_at": _now_iso()})


@app.route("/api/platform/strategies/<strategy>")
def api_platform_strategy(strategy: str):
    try:
        payload = _platform_api().strategy_snapshot(strategy)
    except KeyError:
        return jsonify({"error": "Strategy not found", "strategy": strategy}), 404
    return jsonify({**payload, "fetched_at": _now_iso()})


@app.route("/api/platform/readiness")
def api_platform_readiness():
    return jsonify({**_readiness_payload(), "fetched_at": _now_iso()})


@app.route("/api/new-dashboard/overview")
def api_new_dashboard_overview():
    return jsonify(_new_dashboard_overview())


@app.route("/api/new-dashboard/strategies", methods=["GET"])
def api_new_dashboard_strategies():
    return jsonify(strategy_service.list_strategies())


@app.route("/api/new-dashboard/strategies", methods=["POST"])
def api_new_dashboard_strategies_create():
    data = request.get_json(silent=True) or {}
    try:
        new_strat = strategy_service.create_strategy(data)
        write_audit_log("strategy_created", status="created", detail={"id": new_strat["id"], "name": new_strat["name"]})
        return jsonify(new_strat), 201
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/new-dashboard/strategies/<strategy_id>", methods=["GET"])
def api_new_dashboard_strategy(strategy_id: str):
    strat = strategy_service.get_strategy(strategy_id)
    if strat is None:
        return jsonify({"error": "Strategy not found", "id": strategy_id}), 404
    return jsonify(strat)


@app.route("/api/new-dashboard/strategies/<strategy_id>", methods=["PUT"])
def api_new_dashboard_strategy_update(strategy_id: str):
    patch = request.get_json(silent=True) or {}
    updated = strategy_service.update_strategy(strategy_id, patch)
    if updated is None:
        return jsonify({"error": "Strategy not found", "id": strategy_id}), 404
    return jsonify(updated)


@app.route("/api/new-dashboard/strategies/<strategy_id>/promote", methods=["POST"])
def api_new_dashboard_strategy_promote(strategy_id: str):
    promoted = strategy_service.promote_strategy(strategy_id)
    if promoted is None:
        return jsonify({"error": "Strategy not found", "id": strategy_id}), 404
    write_audit_log("strategy_promoted", status="promoted", detail={"id": strategy_id, "stage": promoted.get("status")})
    return jsonify(promoted)


@app.route("/api/new-dashboard/strategies/<strategy_id>/demote", methods=["POST"])
def api_new_dashboard_strategy_demote(strategy_id: str):
    body = request.get_json(silent=True) or {}
    target_stage = body.get("targetStage", "")
    reason = body.get("comments", body.get("reason", ""))
    demoted = strategy_service.demote_strategy(strategy_id, target_stage, reason)
    if demoted is None:
        return jsonify({"error": "Strategy not found", "id": strategy_id}), 404
    write_audit_log("strategy_demoted", status="demoted", detail={"id": strategy_id, "stage": demoted.get("status"), "reason": reason})
    return jsonify(demoted)


@app.route("/api/new-dashboard/gemini/parse", methods=["POST"])
def api_new_dashboard_gemini_parse():
    body = request.get_json(silent=True) or {}
    text = body.get("text", "")
    if not text:
        return jsonify({"error": "text field required"}), 400
    try:
        result = gemini_service.parse_strategy_idea(text)
        return jsonify(result)
    except RuntimeError as exc:
        if "GEMINI_API_KEY" in str(exc) or "not installed" in str(exc):
            return jsonify({"error": str(exc)}), 503
        return jsonify({"error": str(exc)}), 502
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/api/new-dashboard/gemini/explain-failure", methods=["POST"])
def api_new_dashboard_gemini_explain():
    body = request.get_json(silent=True) or {}
    trades = body.get("trades", [])
    try:
        result = gemini_service.explain_failure(trades)
        return jsonify(result)
    except RuntimeError as exc:
        if "GEMINI_API_KEY" in str(exc) or "not installed" in str(exc):
            return jsonify({"error": str(exc)}), 503
        return jsonify({"error": str(exc)}), 502
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/api/new-dashboard/strategies/<strategy_id>/pipeline-report", methods=["GET"])
def api_new_dashboard_pipeline_report(strategy_id: str):
    report = strategy_service.get_pipeline_report(strategy_id)
    if report is None:
        return jsonify({"error": "No SVOS pipeline report found for this strategy"}), 404
    return jsonify(report)


@app.route("/api/new-dashboard/strategies/<strategy_id>/run-pipeline", methods=["POST"])
def api_new_dashboard_run_pipeline(strategy_id: str):
    body = request.get_json(silent=True) or {}
    spec_text: str = body.get("spec", "").strip()

    if not spec_text:
        strat = strategy_service.get_strategy(strategy_id)
        if strat:
            spec_text = pipeline_service.build_spec_from_strategy(strat)

    if not spec_text:
        return jsonify({"error": "No strategy spec provided and none derivable from strategy rules"}), 400

    try:
        result = pipeline_service.run_pipeline(
            strategy_id,
            spec_text,
            replay=body.get("replay") or None,
            backtest=body.get("backtest") or None,
            robustness=body.get("robustness") or None,
            virtual_demo=body.get("virtual_demo") or None,
        )
        return jsonify(result)
    except Exception as exc:
        import traceback
        return jsonify({"error": str(exc), "trace": traceback.format_exc()}), 500


@app.route("/api/new-dashboard/reports")
def api_new_dashboard_reports():
    reports = load_index()
    return jsonify({
        "reports": reports.get("reports", []),
        "latest": reports.get("latest", {}),
        "generated_at": reports.get("generated_at", ""),
        "fetched_at": _now_iso(),
    })


@app.route("/api/live-dashboard")
def api_live_dashboard():
    chart_symbol = str(request.args.get("symbol", "")).strip() or None
    timeframe = str(request.args.get("timeframe", "M15")).strip() or "M15"
    count = request.args.get("count", default=120, type=int) or 120
    return jsonify(live_dashboard_service.load_snapshot(chart_symbol=chart_symbol, timeframe=timeframe, candle_count=max(10, min(count, 500))))


@app.route("/api/live-dashboard/positions/<position_id>/close", methods=["POST"])
@require_operator(app, "risk_operator", "admin")
def api_live_dashboard_close_position(position_id: str):
    try:
        payload = live_dashboard_service.close_position(position_id)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502
    write_audit_log(
        "live_dashboard_close_position",
        status="completed" if payload.get("ok") else "failed",
        detail={**payload, "actor": request.environ["svos.actor"]},
    )
    return jsonify({**payload, "fetched_at": _now_iso()})


@app.route("/api/live-dashboard/positions/<position_id>/protect", methods=["POST"])
@require_operator(app, "risk_operator", "admin")
def api_live_dashboard_modify_position(position_id: str):
    body = request.get_json(silent=True) or {}
    stop_loss = body.get("stop_loss")
    take_profit = body.get("take_profit")
    if stop_loss in (None, "") or take_profit in (None, ""):
        return jsonify({"error": "stop_loss and take_profit are required"}), 400
    try:
        payload = live_dashboard_service.modify_position(position_id, float(stop_loss), float(take_profit))
    except ValueError:
        return jsonify({"error": "stop_loss and take_profit must be numeric"}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502
    write_audit_log(
        "live_dashboard_modify_position",
        status="completed" if payload.get("ok") else "failed",
        detail={**payload, "actor": request.environ["svos.actor"]},
    )
    return jsonify({**payload, "fetched_at": _now_iso()})


@app.route("/api/live-dashboard/orders/<order_id>/cancel", methods=["POST"])
@require_operator(app, "risk_operator", "admin")
def api_live_dashboard_cancel_order(order_id: str):
    try:
        payload = live_dashboard_service.cancel_order(order_id)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502
    write_audit_log(
        "live_dashboard_cancel_order",
        status="completed" if payload.get("ok") else "failed",
        detail={**payload, "actor": request.environ["svos.actor"]},
    )
    return jsonify({**payload, "fetched_at": _now_iso()})


@app.route("/api/rgm")
def api_rgm():
    return jsonify({**_rgm_payload(), "fetched_at": _now_iso()})


@app.route("/api/governance")
def api_governance():
    return jsonify({**_governance_payload(), "fetched_at": _now_iso()})


@app.route("/api/smo")
def api_smo():
    return jsonify({**_smo_payload(), "fetched_at": _now_iso()})


@app.route("/api/reports")
def api_reports():
    payload = load_index()
    return jsonify({
        "generated_at": payload.get("generated_at", ""),
        "reports": payload.get("reports", []),
        "latest": payload.get("latest", {}),
        "fetched_at": _now_iso(),
    })


@app.route("/api/reports/latest")
def api_reports_latest():
    return jsonify({**latest_reports(), "fetched_at": _now_iso()})


@app.route("/api/reports/<path:report_id>")
def api_reports_by_id(report_id: str):
    if request.args.get("reviewed") == "1":
        return jsonify({"error": "Review mutation requires POST authentication"}), 405
    try:
        payload = read_report(report_id)
    except FileNotFoundError:
        return jsonify({"error": "Report not found", "report_id": report_id}), 404
    return jsonify({**payload, "reviewed_at": load_control_state().get("reports_reviewed", {}).get(report_id, ""), "fetched_at": _now_iso()})


@app.route("/api/reports/<path:report_id>/review", methods=["POST"])
@require_operator(app, "research_operator", "admin")
def api_reports_review(report_id: str):
    review = mark_reviewed(report_id)
    write_audit_log(
        "report_reviewed",
        status="completed",
        detail={**review, "actor": request.environ["svos.actor"]},
    )
    return jsonify({**review, "fetched_at": _now_iso()})


@app.route("/api/reports/generate", methods=["POST"])
@require_operator(app, "research_operator", "admin")
def api_reports_generate():
    body = request.get_json(silent=True) or {}
    report_type = str(body.get("type", "")).strip()
    if not report_type:
        return jsonify({"error": "Missing report type"}), 400
    try:
        payload = generate_reports_payload(report_type)
    except ValueError as exc:
        write_audit_log("report_generate", status="denied", detail={"report_type": report_type, "error": str(exc)})
        return jsonify({"error": str(exc)}), 400
    write_audit_log("report_generate", status="completed", detail={"report_type": report_type, "artifact_count": len(payload.get("artifacts", []))})
    return jsonify(payload)


@app.route("/api/incidents/ack", methods=["POST"])
@require_operator(app, "incident_operator", "admin")
def api_incidents_ack():
    body = request.get_json(silent=True) or {}
    incident_id = str(body.get("incident_id", "")).strip()
    if not incident_id:
        return jsonify({"error": "Missing incident_id"}), 400
    actor = request.environ["svos.actor"]
    review = mark_incident_reviewed(incident_id)
    reviewed_at = review.get("incidents_reviewed", {}).get(incident_id, "")
    write_audit_log("incident_acknowledged", status="completed", detail={"incident_id": incident_id, "reviewed_at": reviewed_at, "actor": actor})
    return jsonify({"incident_id": incident_id, "reviewed_at": reviewed_at, "fetched_at": _now_iso()})


@app.route("/api/reports/generate/all", methods=["POST"])
@require_operator(app, "research_operator", "admin")
def api_reports_generate_all():
    payload = generate_reports_payload("all")
    write_audit_log("report_generate_all", status="completed", detail={"artifact_count": len(payload.get("artifacts", []))})
    return jsonify(payload)


@app.route("/api/emergency-stop", methods=["POST"])
@require_operator(app, "risk_operator", "admin")
def api_emergency_stop():
    body = request.get_json(silent=True) or {}
    confirm = str(body.get("confirm_token", "")).strip()
    if confirm != "CONFIRM-EMERGENCY-STOP":
        write_audit_log("emergency_stop_denied", status="denied", detail={"reason": "invalid_confirm_token"})
        return jsonify({"error": "Invalid or missing CONFIRM token", "required": "CONFIRM-EMERGENCY-STOP"}), 403
    reason = str(body.get("reason", "Manual operator stop")).strip() or "Manual operator stop"
    state = activate_emergency_stop(reason=reason, activated_by=request.environ["svos.actor"])
    write_audit_log("emergency_stop", status="completed", detail=state["emergency_stop"])
    return jsonify({"status": "stopped", "emergency_stop": state["emergency_stop"], "fetched_at": _now_iso()})


@app.route("/api/emergency-stop/clear", methods=["POST"])
@require_operator(app, "admin")
def api_emergency_stop_clear():
    body = request.get_json(silent=True) or {}
    confirm = str(body.get("confirm_token", "")).strip()
    if confirm != "CONFIRM-CLEAR-EMERGENCY-STOP":
        write_audit_log("emergency_stop_clear_denied", status="denied", detail={"reason": "invalid_confirm_token"})
        return jsonify({"error": "Invalid or missing CONFIRM token", "required": "CONFIRM-CLEAR-EMERGENCY-STOP"}), 403
    reason = str(body.get("reason", "Operator review complete")).strip() or "Operator review complete"
    state = clear_emergency_stop(reason=reason, cleared_by=request.environ["svos.actor"])
    write_audit_log("emergency_stop_clear", status="completed", detail=state["emergency_stop"])
    return jsonify({"status": "cleared", "emergency_stop": state["emergency_stop"], "fetched_at": _now_iso()})

# ---------------------------------------------------------------------------
# Static dashboard
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    from flask import redirect
    return redirect("/new-dashboard/", code=302)


@app.route("/legacy")
def legacy_index():
    return send_from_directory(str(Path(__file__).parent), "index.html")


@app.route("/live-dashboard")
@app.route("/live-dashboard/")
def live_dashboard_index():
    return send_from_directory(str(Path(__file__).parent), _LIVE_DASHBOARD_HTML.name)


@app.route("/new-dashboard")
@app.route("/new-dashboard/")
def new_dashboard_index():
    if not _NEW_DASHBOARD_DIST.exists():
        return (
            jsonify(
                {
                    "error": "New dashboard frontend has not been built yet",
                    "required_build_dir": str(_NEW_DASHBOARD_DIST.relative_to(_ROOT)),
                }
            ),
            503,
        )
    return send_from_directory(str(_NEW_DASHBOARD_DIST), "index.html")


@app.route("/new-dashboard/<path:asset_path>")
def new_dashboard_assets(asset_path: str):
    if not _NEW_DASHBOARD_DIST.exists():
        return (
            jsonify(
                {
                    "error": "New dashboard frontend has not been built yet",
                    "required_build_dir": str(_NEW_DASHBOARD_DIST.relative_to(_ROOT)),
                }
            ),
            503,
        )
    dist_root = _NEW_DASHBOARD_DIST.resolve()
    target = (_NEW_DASHBOARD_DIST / asset_path).resolve()
    if target.is_relative_to(dist_root) and target.is_file():
        return send_from_directory(str(_NEW_DASHBOARD_DIST), asset_path)
    return send_from_directory(str(_NEW_DASHBOARD_DIST), "index.html")


if __name__ == "__main__":
    port = int(os.getenv("DASHBOARD_PORT", "8080"))
    bind_host = dashboard_bind_host()
    public_host = dashboard_public_host(bind_host)
    print(f"Dashboard running at {dashboard_url(public_host, port)} (bind={bind_host})")
    app.run(host=bind_host, port=port, debug=False)

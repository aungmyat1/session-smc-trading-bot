"""
Demo Validation Mode — report generator.

Reads execution/validation_session.py, execution/validation_metrics.py,
execution/risk_portfolio_store.py (EXISTING), and
execution/operations_recorder.py's get_recent_events/db_health_check
(EXISTING) and writes reports/demo_validation/*.json +
validation_report.md. Purely a report generator — it has no runtime/broker
side effects and does not run as a background service.

Public API:
    generate_report(validation_session_id, output_dir=Path("reports/demo_validation"))
        -> dict[str, Path]   # written file paths, for the caller to log/attach
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from execution.operations_recorder import db_health_check, get_recent_events, get_recent_runtimes
from execution.risk_portfolio_store import RiskPortfolioStore
from execution.validation_metrics import lifecycle_success_rate, stage_latency_stats
from execution.validation_session import ValidationSessionManager

_log = logging.getLogger("execution.validation_report")

_DEFAULT_OUTPUT_DIR = Path("reports") / "demo_validation"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, default=str), encoding="utf-8")


def generate_report(
    validation_session_id: str,
    output_dir: Path = _DEFAULT_OUTPUT_DIR,
    session_manager: ValidationSessionManager | None = None,
) -> dict[str, Path]:
    """Generate every reports/demo_validation/*.json file plus
    validation_report.md for one validation session. Returns the map of
    logical name -> written file path."""
    session_manager = session_manager or ValidationSessionManager()
    session = session_manager.resume(validation_session_id) or {"session_id": validation_session_id}

    latency = stage_latency_stats(validation_session_id)
    lifecycle = lifecycle_success_rate(validation_session_id)
    events = [e for e in get_recent_events(limit=500)]
    runtimes = get_recent_runtimes(limit=20)
    db_health = db_health_check()

    risk_store = RiskPortfolioStore()
    risk_state = risk_store.load_risk_state() or {}
    portfolio_state = risk_store.load_portfolio_state() or {}

    generated_at = datetime.now(timezone.utc).isoformat()

    session_summary = {"generated_at": generated_at, "session": session, "lifecycle": lifecycle}
    trade_lifecycle = {"generated_at": generated_at, "session_id": validation_session_id, "stages": latency}
    latency_summary = {"generated_at": generated_at, "session_id": validation_session_id, "latency_by_stage": latency}
    broker_health = {
        "generated_at": generated_at,
        "broker": session.get("broker"),
        "account": session.get("account"),
        "reconnect_events": [e for e in events if "reconnect" in str(e.get("event_type", ""))],
    }
    dashboard_health = {"generated_at": generated_at, "db_health": db_health, "recent_runtimes": runtimes}
    telegram_health = {
        "generated_at": generated_at,
        "alert_events": [e for e in events if str(e.get("event_type", "")).startswith("telegram_alert:")],
    }
    ledger_health = {"generated_at": generated_at, "risk_state": risk_state, "portfolio_state": portfolio_state}
    recovery_summary = {
        "generated_at": generated_at,
        "recovery_events": [e for e in events if e.get("type") == "recovery_checkpoint" or str(e.get("event_type", "")) == "recovery"],
    }

    output_dir = Path(output_dir)
    files = {
        "session_summary": output_dir / "session_summary.json",
        "trade_lifecycle": output_dir / "trade_lifecycle.json",
        "latency_summary": output_dir / "latency_summary.json",
        "broker_health": output_dir / "broker_health.json",
        "dashboard_health": output_dir / "dashboard_health.json",
        "telegram_health": output_dir / "telegram_health.json",
        "ledger_health": output_dir / "ledger_health.json",
        "recovery_summary": output_dir / "recovery_summary.json",
    }
    _write_json(files["session_summary"], session_summary)
    _write_json(files["trade_lifecycle"], trade_lifecycle)
    _write_json(files["latency_summary"], latency_summary)
    _write_json(files["broker_health"], broker_health)
    _write_json(files["dashboard_health"], dashboard_health)
    _write_json(files["telegram_health"], telegram_health)
    _write_json(files["ledger_health"], ledger_health)
    _write_json(files["recovery_summary"], recovery_summary)

    markdown_path = output_dir / "validation_report.md"
    markdown_path.write_text(
        _render_markdown(session, lifecycle, latency, db_health, generated_at),
        encoding="utf-8",
    )
    files["validation_report"] = markdown_path
    return files


def _render_markdown(
    session: dict[str, Any],
    lifecycle: dict[str, Any],
    latency: dict[str, Any],
    db_health: dict[str, Any],
    generated_at: str,
) -> str:
    lines = [
        f"# Demo Validation Report — {session.get('session_id', 'unknown')}",
        "",
        f"Generated: {generated_at}",
        "",
        "## Overview",
        f"- Operator: {session.get('operator', 'unknown')}",
        f"- Broker: {session.get('broker', 'unknown')}",
        f"- Account: {session.get('account', 'unknown')}",
        f"- Software version: {session.get('software_version', 'unknown')}",
        f"- Git commit: {session.get('git_commit', 'unknown')}",
        f"- Config hash: {session.get('config_hash', 'unknown')}",
        f"- Status: {session.get('status', 'unknown')}",
        f"- Started: {session.get('started_at', 'unknown')}",
        f"- Ended: {session.get('ended_at', 'in progress')}",
        "",
        "## Statistics",
        f"- Trades observed: {lifecycle.get('trade_count', 0)}",
        f"- Lifecycle stage rows: {lifecycle.get('stage_count', 0)}",
        f"- Failed stages: {lifecycle.get('failed_stage_count', 0)}",
        f"- Success rate: {lifecycle.get('success_rate')}",
        "",
        "## Latency by stage (ms)",
        "| stage | count | avg | max | p50 | p95 | p99 |",
        "|---|---|---|---|---|---|---|",
    ]
    for stage_name, stats in sorted(latency.items()):
        lines.append(
            f"| {stage_name} | {stats['count']} | {stats['avg_ms']} | {stats['max_ms']} | "
            f"{stats['p50_ms']} | {stats['p95_ms']} | {stats['p99_ms']} |"
        )
    lines += [
        "",
        "## Database health",
        f"- Reachable: {db_health.get('reachable')}",
        f"- Latency: {db_health.get('latency_ms')} ms",
        "",
        "## Failures",
        "See trade_lifecycle.json / recovery_summary.json for per-stage error detail.",
        "",
        "## Recommendations",
        (
            "Promotion readiness requires n>=20-50 successful demo trades with a stable "
            "success rate and no unresolved recovery orphans — see "
            "docs/operations/DEMO_VALIDATION_MODE.md's promotion checklist. This report "
            "alone is evidence, not a promotion decision."
        ),
        "",
        "## Promotion readiness",
        (
            "PENDING — insufficient trade volume for a promotion decision"
            if lifecycle.get("trade_count", 0) < 20
            else "See recommendations above; a human operator makes the promotion call."
        ),
    ]
    return "\n".join(lines) + "\n"

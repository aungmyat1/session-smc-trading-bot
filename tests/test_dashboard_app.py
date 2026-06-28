from __future__ import annotations

import json
from pathlib import Path

import pytest

import dashboard.app as dashboard_app
import dashboard.audit_log as audit_log
import dashboard.control_state as control_state
import dashboard.report_service as report_service
import scripts.generate_reports as generate_reports


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _setup_dashboard_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for rel in [
        "config",
        "logs",
        "reports/current_strategy_svos/ST-A2",
        "reports/daily",
        "reports/strategy",
        "reports/risk",
        "reports/execution",
        "reports/system_health",
        "reports/live_readiness",
        "reports/incidents",
        "execution_validation/reports/run1",
        "docs",
        "data",
    ]:
        (tmp_path / rel).mkdir(parents=True, exist_ok=True)

    _write(
        tmp_path / "config" / "strategy_catalog.yaml",
        """
current_strategy: ST-A2
strategies:
  ST-A2:
    status: walk_forward
    approved: true
    current: true
    version: "2.1"
    description: Session liquidity reversal production candidate
    symbols: [EURUSD, GBPUSD]
    timeframes: [M15, H4]
    requirements:
      replay: pass
      backtest: pass
    last_svos_at: "2026-06-28T04:00:00+00:00"
    last_svos_status: PASS
    last_svos_promoted_stage: backtest
    last_svos_verification_ready: true
    deployment_target: execution
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "config" / "validation.yaml",
        """
promotion_map:
  research: replay
  replay: backtest
  backtest: walk_forward
  walk_forward: shadow
  shadow: demo
  demo: live
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "config" / "research_engine.yaml",
        """
analytics:
  duckdb_path: research.db
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "docs" / "SYSTEM_ARCHITECTURE.md",
        "Current implementation: SVOS transitional v1.7\nTarget architecture: ISOP v2\n",
    )
    _write(
        tmp_path / "reports" / "current_strategy_svos" / "ST-A2" / "latest.json",
        json.dumps({"status": "PASS", "strategy": "ST-A2"}),
    )
    _write(
        tmp_path / "execution_validation" / "reports" / "run1" / "validation_report.json",
        json.dumps(
            {
                "strategy": "ST-A2",
                "period": "2026-06",
                "status": "READY FOR DEMO",
                "final_score": 91,
                "created_at": "2026-06-28T04:30:00+00:00",
                "signal_accuracy": 0.95,
                "order_accuracy": 0.92,
                "risk_accuracy": 0.98,
                "checks": {"latency": {"passed": True, "message": "ok", "score": 10}},
            }
        ),
    )
    _write(
        tmp_path / "logs" / "trades.jsonl",
        "\n".join(
            [
                json.dumps({"timestamp": "2026-06-28T04:00:00+00:00", "symbol": "EURUSD", "direction": "buy", "entry": 1.1, "strategy": "ST-A2", "result_r": 1.2}),
                json.dumps({"timestamp": "2026-06-28T05:00:00+00:00", "symbol": "GBPUSD", "direction": "sell", "entry": 1.25, "strategy": "ST-A2", "result_r": -0.5}),
            ]
        )
        + "\n",
    )
    _write(tmp_path / "logs" / "st_a2_runner.log", "2026-06-28 05:00:00 INFO runner alive\n")
    _write(
        tmp_path / "logs" / "bot.log",
        "\n".join(
            [
                "2026-06-28 05:00:00 INFO bot MetaAPI connected",
                "2026-06-28 05:05:00 WARN bot sample warning",
            ]
        )
        + "\n",
    )
    _write(tmp_path / "logs" / "bot_state.json", json.dumps({"halted": False, "halt_reason": "", "consecutive_losses": 1, "daily_loss_pct": 0.001}))
    _write(tmp_path / "reports" / "daily" / "daily_report_2026-06-28.md", "# Daily Trading Report\n\n- Final recommendation: `CONTINUE`\n")
    _write(tmp_path / "reports" / "strategy" / "strategy_report_2026-06-28_000000.md", "# Strategy Performance Report\n")
    _write(tmp_path / "reports" / "risk" / "risk_report_2026-06-28_000000.md", "# Risk Report\n")
    _write(tmp_path / "reports" / "execution" / "execution_report_2026-06-28_000000.md", "# Execution Quality Report\n")
    _write(tmp_path / "reports" / "system_health" / "system_health_report_2026-06-28_000000.md", "# System Health Report\n")
    _write(tmp_path / "reports" / "live_readiness" / "live_readiness_report_2026-06-28_000000.md", "# Live Readiness Report\n\n- Final verdict: `DEMO_READY`\n")
    _write(tmp_path / "reports" / "index.json", json.dumps({"generated_at": "", "latest": {}, "reports": []}))

    monkeypatch.setenv("DB_BACKEND", "duckdb")
    monkeypatch.setenv("LIVE_TRADING", "false")
    monkeypatch.setattr(dashboard_app, "_ROOT", tmp_path)
    monkeypatch.setattr(dashboard_app, "_CATALOG_PATH", tmp_path / "config" / "strategy_catalog.yaml")
    monkeypatch.setattr(dashboard_app, "_EVF_REPORTS_DIR", tmp_path / "execution_validation" / "reports")
    monkeypatch.setattr(dashboard_app, "_SVOS_REPORTS_DIR", tmp_path / "reports" / "current_strategy_svos")
    monkeypatch.setattr(dashboard_app, "_JOURNAL_PATHS", [tmp_path / "logs" / "trades.jsonl"])
    monkeypatch.setattr(dashboard_app, "_ARCHITECTURE_PATH", tmp_path / "docs" / "SYSTEM_ARCHITECTURE.md")
    monkeypatch.setattr(dashboard_app, "_BOT_LOG", tmp_path / "logs" / "bot.log")
    monkeypatch.setattr(dashboard_app, "_RUNNER_LOG", tmp_path / "logs" / "st_a2_runner.log")

    monkeypatch.setattr(audit_log, "ROOT", tmp_path)
    monkeypatch.setattr(audit_log, "AUDIT_LOG_PATH", tmp_path / "logs" / "dashboard_audit.jsonl")
    monkeypatch.setattr(control_state, "ROOT", tmp_path)
    monkeypatch.setattr(control_state, "CONTROL_STATE_PATH", tmp_path / "reports" / "control_state.json")
    monkeypatch.setattr(report_service, "ROOT", tmp_path)
    monkeypatch.setattr(report_service, "REPORTS_ROOT", tmp_path / "reports")
    monkeypatch.setattr(report_service, "REPORT_INDEX_PATH", tmp_path / "reports" / "index.json")

    monkeypatch.setattr(generate_reports, "ROOT", tmp_path)
    monkeypatch.setattr(generate_reports, "TRADE_EVENT_LOG", tmp_path / "logs" / "trades.jsonl")
    monkeypatch.setattr(generate_reports, "BOT_LOG", tmp_path / "logs" / "bot.log")
    monkeypatch.setattr(generate_reports, "RUNNER_LOG", tmp_path / "logs" / "st_a2_runner.log")
    monkeypatch.setattr(generate_reports, "DEMO_JOURNALS", [tmp_path / "logs" / "trades.jsonl"])
    monkeypatch.setattr(generate_reports, "TRADE_DB", tmp_path / "data" / "trade_journal.db")
    monkeypatch.setattr(generate_reports, "BOT_STATE", tmp_path / "logs" / "bot_state.json")
    monkeypatch.setattr(generate_reports, "EXECUTION_DAILY", tmp_path / "logs" / "execution_summary_daily.json")
    monkeypatch.setattr(generate_reports, "EXECUTION_WEEKLY", tmp_path / "logs" / "execution_summary_weekly.json")
    monkeypatch.setattr(generate_reports, "CATALOG", tmp_path / "config" / "strategy_catalog.yaml")
    monkeypatch.setattr(generate_reports, "DEMO_CONFIG", tmp_path / "config" / "demo.yaml")
    monkeypatch.setattr(generate_reports, "VALIDATION_CONFIG", tmp_path / "config" / "validation.yaml")
    monkeypatch.setattr(generate_reports.health_check, "_ROOT", tmp_path)
    _write(tmp_path / "config" / "demo.yaml", "execution:\n  mode: demo\n")

    monkeypatch.setattr(
        dashboard_app,
        "_health_snapshot",
        lambda: {
            "runner": {"status": "PASS", "detail": "runner ok"},
            "risk": {"status": "PASS", "detail": "risk ok"},
            "portfolio": {"status": "PASS", "detail": "portfolio ok"},
            "recovery": {"status": "PASS", "detail": "recovery ok"},
            "execution": {"status": "SHADOW", "detail": "mode=demo DEMO_ONLY=true"},
            "database": {"status": "SKIP", "detail": "duckdb runtime selected"},
        },
    )


@pytest.fixture
def client(tmp_path, monkeypatch):
    _setup_dashboard_repo(tmp_path, monkeypatch)
    dashboard_app.app.config.update(TESTING=True)
    return dashboard_app.app.test_client()


def test_dashboard_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"ISOP Control Panel" in response.data
    assert b"el.style.borderColor = '';" in response.data
    assert b"el.style.color = '';" in response.data


def test_existing_endpoints_still_work(client):
    assert client.get("/api/svos").status_code == 200
    assert client.get("/api/evf").status_code == 200
    assert client.get("/api/trades").status_code == 200
    assert client.get("/api/status").status_code == 200


def test_api_status_returns_online_and_never_live_in_tests(client):
    response = client.get("/api/status")
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["system"] == "ONLINE"
    assert "dashboard_url" in payload
    assert payload["live_trading"] is False


def test_new_isop_endpoints_work(client):
    rgm = client.get("/api/rgm")
    governance = client.get("/api/governance")
    smo = client.get("/api/smo")
    reports = client.get("/api/reports")
    platform = client.get("/api/platform")
    registry = client.get("/api/platform/registry")
    strategy = client.get("/api/platform/strategies/ST-A2")

    assert rgm.status_code == 200
    assert governance.status_code == 200
    assert smo.status_code == 200
    assert reports.status_code == 200
    assert platform.status_code == 200
    assert registry.status_code == 200
    assert strategy.status_code == 200

    assert rgm.get_json()["qualification_status"] == "QUALIFIED"
    assert governance.get_json()["approval_status"] == "APPROVED"
    assert "monitoring_status" in smo.get_json()
    assert "control_timeline" in smo.get_json()
    assert "unacknowledged_incident_count" in smo.get_json()
    assert "reports" in reports.get_json()
    assert platform.get_json()["service_status"]["research"] == "ONLINE"
    assert registry.get_json()["strategy_count"] >= 1
    assert strategy.get_json()["record"]["strategy"] == "ST-A2"


def test_reports_generate_is_read_only_and_does_not_call_live_broker_checks(client, monkeypatch):
    def _forbidden(*args, **kwargs):
        raise AssertionError("live broker checks must not run during report generation")

    monkeypatch.setattr(generate_reports.health_check, "check_broker", _forbidden)
    monkeypatch.setattr(generate_reports.health_check, "check_data_feed", _forbidden)

    response = client.post("/api/reports/generate", json={"type": "daily"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["report_type"] == "daily"
    assert payload["artifacts"]


def test_emergency_stop_requires_confirm_token(client):
    response = client.post("/api/emergency-stop", json={"reason": "manual pause"})
    assert response.status_code == 403
    assert response.get_json()["required"] == "CONFIRM-EMERGENCY-STOP"


def test_emergency_stop_clear_requires_confirm_token(client):
    response = client.post("/api/emergency-stop/clear", json={"reason": "resume"})
    assert response.status_code == 403
    assert response.get_json()["required"] == "CONFIRM-CLEAR-EMERGENCY-STOP"


def test_emergency_stop_can_be_cleared_with_confirm_token(client):
    stop_response = client.post(
        "/api/emergency-stop",
        json={"reason": "manual pause", "confirm_token": "CONFIRM-EMERGENCY-STOP"},
    )
    assert stop_response.status_code == 200
    assert stop_response.get_json()["emergency_stop"]["active"] is True

    clear_response = client.post(
        "/api/emergency-stop/clear",
        json={"reason": "review complete", "confirm_token": "CONFIRM-CLEAR-EMERGENCY-STOP"},
    )
    assert clear_response.status_code == 200
    payload = clear_response.get_json()
    assert payload["status"] == "cleared"
    assert payload["emergency_stop"]["active"] is False
    assert payload["emergency_stop"]["clear_reason"] == "review complete"

    smo_response = client.get("/api/smo")
    smo_payload = smo_response.get_json()
    assert any(entry["action"] == "emergency_stop" for entry in smo_payload["control_timeline"])
    assert any(entry["action"] == "emergency_stop_clear" for entry in smo_payload["control_timeline"])


def test_incident_acknowledgment_marks_incident_reviewed(client):
    smo_response = client.get("/api/smo")
    smo_payload = smo_response.get_json()
    assert smo_payload["recent_incidents"]
    incident = smo_payload["recent_incidents"][0]
    assert incident["acknowledged"] is False

    ack_response = client.post("/api/incidents/ack", json={"incident_id": incident["id"]})
    assert ack_response.status_code == 200
    ack_payload = ack_response.get_json()
    assert ack_payload["incident_id"] == incident["id"]
    assert ack_payload["reviewed_at"]

    updated = client.get("/api/smo").get_json()
    reviewed = next(item for item in updated["recent_incidents"] if item["id"] == incident["id"])
    assert reviewed["acknowledged"] is True


def test_incident_acknowledgment_requires_incident_id(client):
    response = client.post("/api/incidents/ack", json={})
    assert response.status_code == 400
    assert "Missing incident_id" in response.get_json()["error"]


def test_invalid_report_type_fails_cleanly(client):
    response = client.post("/api/reports/generate", json={"type": "bad-type"})
    assert response.status_code == 400
    assert "Unsupported report type" in response.get_json()["error"]

from __future__ import annotations

import json
from pathlib import Path

from agtrade.cli import main
from svos.deployment.service import DeploymentStatusService


def test_agtrade_research_status_summarizes_queue(tmp_path, capsys):
    queue_path = tmp_path / "research_queue.yaml"
    queue_path.write_text(
        """
jobs:
  - job_id: job-1
    strategy: ST-A2
    enabled: true
    steps:
      - name: replay
        command: ["python", "scripts/replay_2025.py"]
      - name: approval
        blocked: true
        reason: waiting for governance
  - job_id: job-2
    strategy: D2E3
    enabled: false
    steps:
      - name: backtest
        command: ["python", "scripts/backtest.py"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(["research", "status", "--queue", str(queue_path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["job_count"] == 2
    assert payload["enabled_job_count"] == 1
    assert payload["blocked_step_count"] == 1


def test_agtrade_strategy_audit_routes_to_existing_audit_cli(tmp_path, capsys):
    payload = {
        "strategy_text": """
Market: FX
Session: London
Bias: Bullish
Entry Trigger: Sweep
Confirmation: FVG
Invalidation: If price closes back below the sweep
Stop Loss: Below sweep
Take Profit: 2R
Risk: 0.3%
Filters: Session filter
Exit Rules: Close at target
""".strip(),
        "candles": [{"time": "2026-06-01T08:00:00Z", "open": 1, "high": 2, "low": 0.5, "close": 1.5}],
        "trades": [{"trade_id": "T1", "timestamp": "2026-06-01T08:15:00Z", "std_net_r": 0.5, "session": "London", "regime": "trending"}],
        "execution_report": {
            "status": "READY FOR DEMO",
            "readiness_status": "READY_FOR_DEMO",
            "final_score": 100,
            "broker_simulation_passed": True,
            "recovery_passed": True,
            "strategy_version_control_passed": True,
        },
        "historical_metrics": {"profit_factor": 1.45, "win_rate": 0.54, "expectancy": 0.42, "max_drawdown": 3.8},
        "live_metrics": {"profit_factor": 1.42, "win_rate": 0.53, "expectancy": 0.41, "max_drawdown": 3.9},
        "parameter_grid": {"best_profit_factor": 1.6, "runner_up_profit_factor": 1.25},
        "notes": {"risk": {"daily_dd_pct": 1.5, "weekly_dd_pct": 3.0, "monthly_dd_pct": 5.5, "portfolio_heat_pct": 0.5}},
    }
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(json.dumps(payload), encoding="utf-8")

    exit_code = main(["strategy", "audit", "--strategy", "ST-A2", "--payload", str(payload_path), "--outdir", str(tmp_path / "reports")])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "ST-A2" in captured.out


def test_agtrade_production_import_and_preflight_workflows(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("LIVE_TRADING", "false")
    monkeypatch.setenv("DEMO_ONLY", "true")
    monkeypatch.setenv("SVOS_PACKAGE_SIGNING_PRIVATE_KEY", "11" * 32)
    monkeypatch.setenv("SVOS_PACKAGE_VERIFYING_PUBLIC_KEY", "d04ab232742bb4ab3a1368bd4615e4e6d0224ab71a016baf8520a332c9778737")
    catalog = tmp_path / "config" / "strategy_catalog.yaml"
    catalog.parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "specs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "specs" / "st_a2.md").write_text("# ST-A2\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("flask==3.0.0\n", encoding="utf-8")
    catalog.write_text(
        """
current_strategy: ST-A2
strategies:
  ST-A2:
    status: production_approval
    svos_stage: PRODUCTION_APPROVAL
    approved: true
    approval:
      decision: APPROVED
      approved_at: "2026-01-01T00:00:00+00:00"
      expires_at: "2099-01-01T00:00:00+00:00"
      revoked: false
    adapter_id: ST-A2
    adapter_version: "2.1"
    parameters: {session: London}
    risk_policy: {policy_id: test-demo, max_risk_pct: 0.3}
    evidence: [{stage: VIRTUAL_DEMO, status: PASS, artifact_hash: fixture}]
    current: true
    version: "2.1"
    owner: quant
    description: Session liquidity reversal production candidate
    deployment_target: execution
    strategy_spec_path: docs/specs/st_a2.md
    symbols: [EURUSD, GBPUSD]
    timeframes: [M15, H4]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    deployment = DeploymentStatusService(root=tmp_path, catalog_path=catalog).create_deployment(
        strategy="ST-A2",
        actor="risk-operator",
    )

    import_exit = main(["production", "import", "--deployment-id", deployment["deployment_id"], "--root", str(tmp_path)])
    import_payload = json.loads(capsys.readouterr().out)

    preflight_exit = main(["production", "preflight", "--deployment-id", deployment["deployment_id"], "--root", str(tmp_path)])
    preflight_payload = json.loads(capsys.readouterr().out)
    activate_exit = main(["production", "activate", "--deployment-id", deployment["deployment_id"], "--root", str(tmp_path)])
    activate_payload = json.loads(capsys.readouterr().out)
    status_exit = main(["production", "status", "--deployment-id", deployment["deployment_id"], "--root", str(tmp_path)])
    status_payload = json.loads(capsys.readouterr().out)

    assert import_exit == 0
    assert preflight_exit == 0
    assert activate_exit == 0
    assert status_exit == 0
    assert Path(import_payload["staged_archive_path"]).exists()
    assert preflight_payload["verdict"] == "READY_DISABLED"
    assert activate_payload["activation_status"] == "STAGED_DISABLED"
    assert status_payload["overall_status"] == "STAGED_DISABLED"

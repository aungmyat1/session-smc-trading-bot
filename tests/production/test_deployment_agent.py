from __future__ import annotations

from pathlib import Path

from production.deployment_agent import ProductionDeploymentAgent
from svos.deployment.service import DeploymentStatusService


def _deployment(tmp_path: Path) -> dict:
    (tmp_path / "config").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "spec.md").write_text("# Strategy\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("flask==3.0.0\n", encoding="utf-8")
    catalog = tmp_path / "config" / "strategy_catalog.yaml"
    catalog.write_text(
        """current_strategy: Test
strategies:
  Test:
    status: production_approval
    svos_stage: PRODUCTION_APPROVAL
    approved: true
    version: 1.0.0
    deployment_target: production-disabled
    strategy_spec_path: docs/spec.md
    symbols: [EURUSD]
""",
        encoding="utf-8",
    )
    return DeploymentStatusService(root=tmp_path, catalog_path=catalog).create_deployment(strategy="Test")


def test_agent_runs_complete_disabled_deployment(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LIVE_TRADING", "false")
    monkeypatch.setenv("DEMO_ONLY", "true")
    deployment = _deployment(tmp_path)

    result = ProductionDeploymentAgent(root=tmp_path).deploy_disabled(deployment["deployment_id"])

    assert result["overall_status"] == "STAGED_DISABLED"
    assert result["activation"]["live_trading_enabled"] is False


def test_agent_poll_is_idempotent_after_state_changes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LIVE_TRADING", "false")
    monkeypatch.setenv("DEMO_ONLY", "true")
    _deployment(tmp_path)
    agent = ProductionDeploymentAgent(root=tmp_path)

    first = agent.poll_once()
    second = agent.poll_once()

    assert len(first) == 1
    assert second == []

"""Tests for svos/deployment/service.py"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch


from svos.deployment.service import DeploymentStatusService


def _catalog_text(approved: bool = False) -> str:
    return f"""
current_strategy: ST-DEPLOY
strategies:
  ST-DEPLOY:
    status: production
    approved: {str(approved).lower()}
    current: true
    version: "1.0"
    owner: quant
    description: Deploy test
    deployment_target: execution
    svos_stage: PRODUCTION
    symbols: [EURUSD]
    timeframes: [M15]
""".strip() + "\n"


def _make_service(tmp_path: Path, approved: bool = False) -> DeploymentStatusService:
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    catalog = tmp_path / "config" / "strategy_catalog.yaml"
    catalog.write_text(_catalog_text(approved), encoding="utf-8")
    return DeploymentStatusService(root=tmp_path, catalog_path=catalog)


def test_status_returns_current_strategy(tmp_path):
    svc = _make_service(tmp_path)
    result = svc.status()
    assert result["current_strategy"] == "ST-DEPLOY"


def test_status_deployment_target(tmp_path):
    svc = _make_service(tmp_path)
    result = svc.status()
    assert result["deployment_target"] == "execution"


def test_status_live_trading_false_by_default(tmp_path):
    svc = _make_service(tmp_path)
    with patch.dict(os.environ, {"LIVE_TRADING": "false"}):
        result = svc.status()
    assert result["live_trading"] is False


def test_status_live_trading_true_when_env_set(tmp_path):
    svc = _make_service(tmp_path)
    with patch.dict(os.environ, {"LIVE_TRADING": "true"}):
        result = svc.status()
    assert result["live_trading"] is True


def test_status_approved_field(tmp_path):
    svc = _make_service(tmp_path, approved=True)
    result = svc.status()
    assert result["approved"] is True


def test_status_not_approved_by_default(tmp_path):
    svc = _make_service(tmp_path, approved=False)
    result = svc.status()
    assert result["approved"] is False


def test_status_uses_default_catalog_path(tmp_path):
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config" / "strategy_catalog.yaml").write_text(
        _catalog_text(), encoding="utf-8"
    )
    svc = DeploymentStatusService(root=tmp_path)  # no catalog_path
    result = svc.status()
    assert isinstance(result, dict)
    assert "current_strategy" in result

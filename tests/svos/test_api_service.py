"""Tests for svos/api/service.py"""
from __future__ import annotations

from pathlib import Path

from svos.api.service import SVOSOperationalAPI


def _catalog_text() -> str:
    return """
current_strategy: ST-API
strategies:
  ST-API:
    status: walk_forward
    approved: false
    current: true
    version: "1.0"
    owner: quant
    description: API test strategy
    symbols: [EURUSD]
    timeframes: [M15]
""".strip() + "\n"


def _make_api(tmp_path: Path) -> SVOSOperationalAPI:
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    catalog = tmp_path / "config" / "strategy_catalog.yaml"
    catalog.write_text(_catalog_text(), encoding="utf-8")
    return SVOSOperationalAPI(
        root=tmp_path,
        catalog_path=catalog,
        health_snapshot_factory=lambda: {"broker": {"status": "OK"}},
        latest_reports_factory=lambda: {"last_audit": "2024-01-01"},
        control_state_factory=lambda: {"emergency_stop": {"active": False}},
    )


def test_overview_returns_all_sections(tmp_path):
    api = _make_api(tmp_path)
    result = api.overview()
    assert "current_strategy" in result
    assert "registry" in result
    assert "deployment" in result
    assert "monitoring" in result
    assert "reports" in result
    assert "emergency_stop" in result
    assert "service_status" in result


def test_overview_current_strategy(tmp_path):
    api = _make_api(tmp_path)
    result = api.overview()
    assert result["current_strategy"] == "ST-API"


def test_overview_service_status_online(tmp_path):
    api = _make_api(tmp_path)
    result = api.overview()
    assert result["service_status"]["research"] == "ONLINE"
    assert result["service_status"]["governance"] == "ONLINE"


def test_registry_snapshot(tmp_path):
    api = _make_api(tmp_path)
    result = api.registry_snapshot()
    assert isinstance(result, dict)
    assert "strategy_count" in result


def test_strategy_snapshot(tmp_path):
    api = _make_api(tmp_path)
    result = api.strategy_snapshot("ST-API")
    assert "record" in result
    assert "versions" in result


def test_api_uses_default_catalog(tmp_path):
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config" / "strategy_catalog.yaml").write_text(
        _catalog_text(), encoding="utf-8"
    )
    api = SVOSOperationalAPI(
        root=tmp_path,
        health_snapshot_factory=lambda: {},
        latest_reports_factory=lambda: {},
        control_state_factory=lambda: {},
    )
    result = api.overview()
    assert isinstance(result, dict)

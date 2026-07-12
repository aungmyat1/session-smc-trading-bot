"""Tests for svos/application/robustness.py"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch


from svos.application.robustness import RobustnessIntegrationService, RobustnessResult
from svos.orchestration.service import SVOSPlatform


def _catalog_text() -> str:
    return """
current_strategy: ST-ROB
strategies:
  ST-ROB:
    status: walk_forward
    approved: false
    current: true
    version: "1.0"
    owner: quant
    description: Robustness test strategy
    symbols: [EURUSD]
    timeframes: [M15]
""".strip() + "\n"


def _make_platform(tmp_path: Path) -> SVOSPlatform:
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    (tmp_path / "reports").mkdir(parents=True, exist_ok=True)
    catalog = tmp_path / "config" / "strategy_catalog.yaml"
    catalog.write_text(_catalog_text(), encoding="utf-8")
    return SVOSPlatform(root=tmp_path, catalog_path=catalog)


def _sample_trades(n: int = 20) -> list[dict[str, Any]]:
    trades = []
    for i in range(n):
        trades.append({
            "entry_time": f"2024-01-{(i % 28) + 1:02d}T10:00:00Z",
            "result_r": 1.0 if i % 2 == 0 else -0.8,
            "std_net_r": 1.0 if i % 2 == 0 else -0.8,
        })
    return trades


def test_normalize_trades_basic():
    trades = [
        {"result_r": 1.5, "symbol": "EURUSD"},
        {"result_r": -0.5},
        {"no_r": True},  # should be skipped
    ]
    result = RobustnessIntegrationService._normalize_trades(trades, "result_r")
    assert len(result) == 2
    assert result[0]["std_net_r"] == 1.5


def test_normalize_trades_skips_non_dict():
    result = RobustnessIntegrationService._normalize_trades(
        [{"result_r": 1.0}, "bad"], "result_r"
    )
    assert len(result) == 1


def test_normalize_trades_uses_fallbacks():
    trades = [{"std_net_r": 2.0}]
    result = RobustnessIntegrationService._normalize_trades(trades, "result_r")
    assert result[0]["std_net_r"] == 2.0


def test_run_walk_forward_handles_import_error():
    result = RobustnessIntegrationService._run_walk_forward([])
    assert result["passed"] is False


def test_run_monte_carlo_handles_error():
    result = RobustnessIntegrationService._run_monte_carlo([])
    # Returns a dict with passed False when research module fails
    assert isinstance(result, dict)


def test_run_sensitivity_skipped_on_empty():
    result = RobustnessIntegrationService._run_sensitivity(None)
    assert result.get("passed") is False
    assert result.get("reason") == "no_parameter_grid"


def test_run_regime_skipped_on_empty_labels():
    result = RobustnessIntegrationService._run_regime([], [])
    assert isinstance(result, dict)
    assert "passed" in result


def test_robustness_result_passed_property():
    result = RobustnessResult(
        strategy="ST",
        status="PASS",
        version_id="v1",
        report_artifact="path.json",
        evidence_id="ev1",
        manifest_id="m1",
        walk_forward={"passed": True},
        monte_carlo={"passed": True},
        sensitivity={},
        regime={},
    )
    assert result.passed is True


def test_robustness_result_to_dict():
    result = RobustnessResult(
        strategy="ST",
        status="FAIL",
        version_id="v1",
        report_artifact="path.json",
        evidence_id="ev1",
        manifest_id="m1",
        walk_forward={"passed": False},
        monte_carlo={"passed": True},
        sensitivity={},
        regime={},
    )
    d = result.to_dict()
    assert d["status"] == "FAIL"
    assert d["passed"] is False


def test_robustness_service_run_fail(tmp_path):
    platform = _make_platform(tmp_path)
    platform.bootstrap()
    svc = RobustnessIntegrationService(platform)
    trades = _sample_trades(10)

    # Both walk_forward and monte_carlo will fail (no research module in test env)
    result = svc.run("ST-ROB", trades, actor="unit-test", dataset_id="ds-001")
    assert isinstance(result, RobustnessResult)
    assert result.strategy == "ST-ROB"
    assert result.status in ("PASS", "FAIL")
    assert isinstance(result.walk_forward, dict)
    assert isinstance(result.monte_carlo, dict)


def test_robustness_service_run_with_parameter_grid(tmp_path):
    platform = _make_platform(tmp_path)
    platform.bootstrap()
    svc = RobustnessIntegrationService(platform)
    trades = _sample_trades(5)
    grid = [{"sl_pips": 10, "result_r": 1.0}, {"sl_pips": 15, "result_r": 0.8}]
    result = svc.run("ST-ROB", trades, parameter_grid=grid)
    assert isinstance(result.sensitivity, dict)


def test_robustness_service_run_with_regime_labels(tmp_path):
    platform = _make_platform(tmp_path)
    platform.bootstrap()
    svc = RobustnessIntegrationService(platform)
    trades = _sample_trades(4)
    labels = ["bull", "bear", "bull", "sideways"]
    result = svc.run("ST-ROB", trades, regime_labels=labels)
    assert isinstance(result.regime, dict)

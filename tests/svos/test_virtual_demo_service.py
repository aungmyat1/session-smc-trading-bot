"""Tests for svos/application/virtual_demo.py"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


from svos.application.virtual_demo import (
    VirtualDemoIntegrationService,
    VirtualDemoResult,
    _DRIFT_THRESHOLD,
    _MIN_SIGNALS,
)
from svos.orchestration.service import SVOSPlatform


def _catalog_text(stage: str = "walk_forward") -> str:
    return f"""
current_strategy: ST-VD
strategies:
  ST-VD:
    status: {stage}
    approved: false
    current: true
    version: "1.0"
    owner: quant
    description: Virtual demo test
    symbols: [EURUSD]
    timeframes: [M15]
""".strip() + "\n"


def _make_platform(tmp_path: Path, stage: str = "walk_forward") -> SVOSPlatform:
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    (tmp_path / "reports").mkdir(parents=True, exist_ok=True)
    catalog = tmp_path / "config" / "strategy_catalog.yaml"
    catalog.write_text(_catalog_text(stage), encoding="utf-8")
    return SVOSPlatform(root=tmp_path, catalog_path=catalog)


def _sample_signals(n: int = 8) -> list[dict[str, Any]]:
    signals = []
    for i in range(n):
        entry = 1.1000 + i * 0.0010
        signals.append({
            "entry_price": entry,
            "stop_loss": entry - 0.0010,
            "take_profit": entry + 0.0020,
            "side": "long" if i % 2 == 0 else "short",
            "result_r": 2.0 if i % 3 != 0 else -1.0,
            "entry_time": f"2024-01-{(i % 28) + 1:02d}T09:00:00Z",
        })
    return signals


def test_virtual_demo_result_passed():
    r = VirtualDemoResult(
        strategy="ST",
        status="PASS",
        version_id="v1",
        signal_count=10,
        filled_count=9,
        report_artifact="path.json",
        evidence_id="ev1",
        manifest_id="m1",
    )
    assert r.passed is True


def test_virtual_demo_result_failed():
    r = VirtualDemoResult(
        strategy="ST",
        status="FAIL",
        version_id="v1",
        signal_count=3,
        filled_count=2,
        report_artifact="path.json",
        evidence_id="ev1",
        manifest_id="m1",
    )
    assert r.passed is False


def test_virtual_demo_result_to_dict():
    r = VirtualDemoResult(
        strategy="ST",
        status="PASS",
        version_id="v1",
        signal_count=10,
        filled_count=9,
        report_artifact="p.json",
        evidence_id="ev1",
        manifest_id="m1",
    )
    d = r.to_dict()
    assert d["status"] == "PASS"
    assert d["passed"] is True
    assert d["signal_count"] == 10


def test_parse_ts_none():
    from svos.application.virtual_demo import VirtualDemoIntegrationService
    assert VirtualDemoIntegrationService._parse_ts(None) is None


def test_parse_ts_datetime_with_tz():
    from svos.application.virtual_demo import VirtualDemoIntegrationService
    dt = datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc)
    result = VirtualDemoIntegrationService._parse_ts(dt)
    assert result == dt


def test_parse_ts_datetime_without_tz():
    from svos.application.virtual_demo import VirtualDemoIntegrationService
    dt = datetime(2024, 1, 1, 9, 0)
    result = VirtualDemoIntegrationService._parse_ts(dt)
    assert result.tzinfo is not None


def test_parse_ts_iso_string():
    from svos.application.virtual_demo import VirtualDemoIntegrationService
    result = VirtualDemoIntegrationService._parse_ts("2024-01-15T10:00:00Z")
    assert result is not None
    assert result.year == 2024


def test_parse_ts_invalid_string():
    from svos.application.virtual_demo import VirtualDemoIntegrationService
    result = VirtualDemoIntegrationService._parse_ts("not-a-date")
    assert result is None


def test_virtual_demo_service_run_too_few_signals(tmp_path):
    platform = _make_platform(tmp_path)
    platform.bootstrap()
    svc = VirtualDemoIntegrationService(platform)
    # fewer than _MIN_SIGNALS → FAIL
    signals = _sample_signals(2)
    result = svc.run("ST-VD", signals, actor="unit-test")
    assert isinstance(result, VirtualDemoResult)
    assert result.status == "FAIL"


def test_virtual_demo_service_run_adequate_signals(tmp_path):
    platform = _make_platform(tmp_path)
    platform.bootstrap()
    svc = VirtualDemoIntegrationService(platform)
    signals = _sample_signals(10)
    result = svc.run("ST-VD", signals, actor="unit-test", symbol="EURUSD")
    assert isinstance(result, VirtualDemoResult)
    assert result.strategy == "ST-VD"
    assert result.signal_count == 10
    assert result.status in ("PASS", "FAIL")


def test_virtual_demo_service_with_expected_pf(tmp_path):
    platform = _make_platform(tmp_path)
    platform.bootstrap()
    svc = VirtualDemoIntegrationService(platform)
    signals = _sample_signals(10)
    result = svc.run("ST-VD", signals, actor="unit-test", expected_pf=2.0)
    # Should include pf_drift check
    assert isinstance(result, VirtualDemoResult)


def test_drift_threshold_constant():
    assert _DRIFT_THRESHOLD == 0.10


def test_min_signals_constant():
    assert _MIN_SIGNALS == 5

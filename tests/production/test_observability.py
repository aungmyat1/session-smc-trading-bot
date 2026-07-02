from __future__ import annotations

from production.observability import ProductionObservabilityService


def test_health_and_prometheus_metrics_are_live_disabled(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LIVE_TRADING", "false")
    monkeypatch.setenv("DEMO_ONLY", "true")
    service = ProductionObservabilityService(root=tmp_path)
    service.heartbeat(metadata={"broker": "connected"})

    health = service.health()
    metrics = service.metrics()

    assert health["status"] == "PASS"
    assert health["heartbeat"]["metadata"]["broker"] == "connected"
    assert "agtrade_health 1" in metrics
    assert "agtrade_live_trading 0" in metrics


def test_health_fails_if_live_policy_is_enabled(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LIVE_TRADING", "true")
    monkeypatch.setenv("DEMO_ONLY", "false")
    service = ProductionObservabilityService(root=tmp_path)

    assert service.health()["status"] == "FAIL"

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import dashboard.status_server as status_server

ROOT = Path(__file__).resolve().parents[1]


def test_vps_health_check_passes_last_tick_via_argv_and_uses_shared_staleness_threshold():
    script = (ROOT / "scripts" / "vps_health_check.sh").read_text(encoding="utf-8")

    assert 'STALE_TICK_S="${STALE_TICK_S:-180}"' in script
    assert "datetime.fromisoformat('$last_tick'" not in script
    assert 'python3 - "$last_tick"' in script


def test_vps_health_check_service_does_not_load_dashboard_secret_env():
    unit = (ROOT / "deploy" / "gcp-vm1" / "systemd" / "vps-health-check.service").read_text(encoding="utf-8")

    assert "live-dashboard.env" not in unit
    assert "SVOS_OPERATOR_TOKEN" not in unit


def test_strategy_release_uses_available_github_cli_instead_of_invalid_action():
    workflow = (ROOT / ".github" / "workflows" / "strategy-release.yml").read_text(encoding="utf-8")

    assert "cli/cli-action@v3" not in workflow
    assert "gh --version" in workflow


def test_system2_operational_json_endpoints_require_auth(monkeypatch):
    monkeypatch.setenv("SVOS_OPERATOR_TOKEN", "test-operator-token")
    client = TestClient(status_server.app)

    for path in ("/api/system2/readiness", "/api/system2/monitoring"):
        unauthenticated = client.get(path)
        assert unauthenticated.status_code == 401

        authenticated = client.get(
            path,
            headers={"Authorization": "Bearer test-operator-token", "X-SVOS-Actor": "tester"},
        )
        assert authenticated.status_code == 200

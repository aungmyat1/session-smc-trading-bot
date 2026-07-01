from __future__ import annotations

from execution.control_plane import TradingPermissionService


def test_permission_service_blocks_on_emergency_stop(tmp_path):
    calls: list[dict] = []

    def _load():
        return {
            "operating_mode": "NORMAL",
            "emergency_stop": {"active": True, "reason": "manual pause", "scope": "block_only"},
            "health": {"safe_mode": {"active": False}, "critical_unknown": False},
            "reconciliation": {"status": "in_sync", "severity": "info", "summary": "", "block_new_trading": False},
            "maintenance": {"active": False, "reason": ""},
            "updated_at": "",
        }

    def _save(payload):
        calls.append(payload)
        return payload

    service = TradingPermissionService(root=tmp_path, environment="demo", control_state_loader=_load, control_state_saver=_save)

    snapshot = service.evaluate(governance_result=type("Gov", (), {"allowed": True, "audit_ref": "abc"})(), broker_connected=True)

    assert snapshot.trading_allowed is False
    assert snapshot.mode == "EMERGENCY_STOP"
    assert calls[-1]["trading_permission"]["mode"] == "EMERGENCY_STOP"


def test_permission_service_blocks_on_governance_denial(tmp_path):
    service = TradingPermissionService(
        root=tmp_path,
        environment="demo",
        control_state_loader=lambda: {
            "operating_mode": "NORMAL",
            "emergency_stop": {"active": False},
            "health": {"safe_mode": {"active": False}, "critical_unknown": False},
            "reconciliation": {"status": "in_sync", "severity": "info", "summary": "", "block_new_trading": False},
            "maintenance": {"active": False, "reason": ""},
            "updated_at": "",
        },
        control_state_saver=lambda payload: payload,
    )

    snapshot = service.evaluate(
        governance_result=type("Gov", (), {"allowed": False, "reason_code": "DEPLOYMENT_NOT_APPROVED", "audit_ref": "ref"})(),
        broker_connected=True,
    )

    assert snapshot.trading_allowed is False
    assert snapshot.mode == "BLOCK_NEW"
    assert "governance:DEPLOYMENT_NOT_APPROVED" in snapshot.reasons

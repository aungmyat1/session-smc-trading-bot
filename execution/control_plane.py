from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from dashboard.control_state import load_control_state, save_control_state


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class EmergencyAction:
    scope: str
    initiator: str
    reason: str
    requested_at: str
    acknowledged_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TradingPermissionSnapshot:
    trading_allowed: bool
    mode: str
    close_only: bool
    reasons: list[str] = field(default_factory=list)
    source_versions: dict[str, Any] = field(default_factory=dict)
    updated_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TradingPermissionService:
    """Resolve the runtime trade-permission state from control, health, and governance inputs."""

    def __init__(
        self,
        *,
        root: Path | str,
        environment: str = "shadow",
        control_state_loader: Callable[[], dict[str, Any]] = load_control_state,
        control_state_saver: Callable[[dict[str, Any]], dict[str, Any]] = save_control_state,
    ) -> None:
        self.root = Path(root)
        self.environment = environment.strip().lower() or "shadow"
        self._load = control_state_loader
        self._save = control_state_saver

    def evaluate(
        self,
        *,
        governance_result: Any | None = None,
        broker_connected: bool | None = None,
        maintenance_active: bool | None = None,
    ) -> TradingPermissionSnapshot:
        state = self._load()
        reasons: list[str] = []
        mode = str(state.get("operating_mode", "NORMAL")).upper()
        close_only = False
        allow = True

        emergency = state.get("emergency_stop", {})
        if emergency.get("active"):
            mode = "EMERGENCY_STOP"
            allow = False
            close_only = str(emergency.get("scope", "block_only")).strip().lower() == "close_positions"
            reasons.append(f"emergency_stop:{str(emergency.get('reason', 'manual stop')).strip() or 'manual stop'}")

        if allow:
            safe_mode = state.get("health", {}).get("safe_mode", {})
            if safe_mode.get("active"):
                mode = "SAFE_MODE"
                allow = False
                reasons.append(f"safe_mode:{str(safe_mode.get('reason', 'health degradation')).strip() or 'health degradation'}")

        if allow:
            reconciliation = state.get("reconciliation", {})
            severity = str(reconciliation.get("severity", "info")).strip().lower()
            if reconciliation.get("block_new_trading") or severity == "critical":
                mode = "BLOCK_NEW"
                allow = False
                reasons.append(
                    f"reconciliation:{str(reconciliation.get('summary', 'critical mismatch')).strip() or 'critical mismatch'}"
                )

        if allow and governance_result is not None and not bool(getattr(governance_result, "allowed", False)):
            mode = "BLOCK_NEW"
            allow = False
            reasons.append(f"governance:{getattr(governance_result, 'reason_code', 'denied')}")

        if allow and broker_connected is False:
            mode = "BLOCK_NEW"
            allow = False
            reasons.append("broker:disconnected")

        maintenance_state = state.get("maintenance", {})
        maintenance_flag = maintenance_state.get("active") if maintenance_active is None else maintenance_active
        if allow and maintenance_flag:
            mode = "BLOCK_NEW"
            allow = False
            reasons.append(f"maintenance:{str(maintenance_state.get('reason', 'scheduled')).strip() or 'scheduled'}")

        if self.environment in {"demo", "live"} and state.get("health", {}).get("critical_unknown", False):
            mode = "BLOCK_NEW"
            allow = False
            reasons.append("health:critical_unknown")

        snapshot = TradingPermissionSnapshot(
            trading_allowed=allow,
            mode=mode,
            close_only=close_only,
            reasons=reasons,
            source_versions={
                "environment": self.environment,
                "control_updated_at": state.get("updated_at", ""),
                "governance_audit_ref": getattr(governance_result, "audit_ref", ""),
            },
        )
        state["trading_permission"] = snapshot.to_dict()
        self._save(state)
        return snapshot

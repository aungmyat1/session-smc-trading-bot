"""Dependency-free production health, heartbeat, and Prometheus exposition."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shared.serialization import now_iso, read_json, write_json


class ProductionObservabilityService:
    def __init__(self, *, root: Path | str) -> None:
        self.root = Path(root)
        self.heartbeat_path = self.root / "data" / "production" / "heartbeat.json"
        self.agent_path = self.root / "data" / "production" / "deployment_agent.json"

    def heartbeat(self, *, component: str = "production-runtime", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {"component": component, "timestamp": now_iso(), "unix_time": time.time(), "metadata": metadata or {}}
        write_json(self.heartbeat_path, payload)
        return payload

    def health(self) -> dict[str, Any]:
        heartbeat = read_json(self.heartbeat_path, {})
        age = self._age_seconds(str(heartbeat.get("timestamp", "")))
        threshold = int(os.getenv("PRODUCTION_HEARTBEAT_MAX_AGE_SECONDS", "120"))
        live = os.getenv("LIVE_TRADING", "false").lower() == "true"
        demo_only = os.getenv("DEMO_ONLY", "true").lower() == "true"
        heartbeat_status = "UNKNOWN" if age is None else ("PASS" if age <= threshold else "FAIL")
        policy_ok = not live and demo_only
        status = "PASS" if policy_ok and heartbeat_status != "FAIL" else "FAIL"
        return {
            "status": status,
            "checked_at": now_iso(),
            "policy": {"status": "PASS" if policy_ok else "FAIL", "live_trading": live, "demo_only": demo_only},
            "heartbeat": {**heartbeat, "status": heartbeat_status, "age_seconds": age, "max_age_seconds": threshold},
            "deployment_agent": read_json(self.agent_path, {}),
        }

    def metrics(self) -> str:
        health = self.health()
        heartbeat = health["heartbeat"]
        age = heartbeat.get("age_seconds")
        lines = [
            "# HELP agtrade_health Production health state (1 healthy).",
            "# TYPE agtrade_health gauge",
            f"agtrade_health {1 if health['status'] == 'PASS' else 0}",
            "# HELP agtrade_live_trading Live trading policy flag.",
            "# TYPE agtrade_live_trading gauge",
            f"agtrade_live_trading {1 if health['policy']['live_trading'] else 0}",
            "# HELP agtrade_heartbeat_age_seconds Age of the latest runtime heartbeat.",
            "# TYPE agtrade_heartbeat_age_seconds gauge",
            f"agtrade_heartbeat_age_seconds {float(age) if age is not None else -1}",
            "# HELP agtrade_broker_writes_enabled Broker write capability (must remain 0).",
            "# TYPE agtrade_broker_writes_enabled gauge",
            "agtrade_broker_writes_enabled 0",
        ]
        metric_state = read_json(self.root / "data" / "production" / "metrics.json", {})
        for name in ("stale_prices", "rejected_intents", "order_outcomes", "reconciliation_drift", "recovery_blocked", "audit_failures"):
            value = float(metric_state.get(name, 0))
            lines.extend((f"# TYPE agtrade_{name} gauge", f"agtrade_{name} {value}"))
        return "\n".join(lines) + "\n"

    @staticmethod
    def structured_event(event: str, *, level: str = "INFO", **fields: Any) -> str:
        return json.dumps({"timestamp": now_iso(), "level": level, "event": event, **fields}, sort_keys=True)

    @staticmethod
    def _age_seconds(value: str) -> float | None:
        if not value:
            return None
        try:
            stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return max(0.0, (datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds())

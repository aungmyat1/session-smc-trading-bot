from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


class MonitoringStatusService:
    """Aggregates operational health and incident signals for dashboards and APIs."""

    def __init__(
        self,
        *,
        root: Path | str,
        health_snapshot_factory: Callable[[], dict[str, Any]],
    ) -> None:
        self.root = Path(root)
        self.health_snapshot_factory = health_snapshot_factory

    def snapshot(self) -> dict[str, Any]:
        health = self.health_snapshot_factory()
        logs = self._recent_log_lines(limit=300)
        incidents = [
            line for line in logs
            if any(token in line for token in ("ERROR", "CRITICAL", "WARN", "DISCONNECTED", "disconnect"))
            and not self._is_benign_runtime_line(line)
        ]
        monitoring_status = "HEALTHY"
        if any(item.get("status") == "FAIL" for item in health.values() if isinstance(item, dict)):
            monitoring_status = "ALERT"
        elif incidents:
            monitoring_status = "WATCH"
        return {
            "monitoring_status": monitoring_status,
            "health": health,
            "incident_count": len(incidents),
            "recent_incidents": incidents[-20:],
        }

    @staticmethod
    def _is_benign_runtime_line(line: str) -> bool:
        text = str(line or "").lower()
        return "engineio.client" in text and "packet queue is empty, aborting" in text

    def _recent_log_lines(self, limit: int = 200) -> list[str]:
        paths = [
            self.root / "logs" / "bot.log",
            self.root / "logs" / "strategy_demo.log",
            self.root / "logs" / "st_a2_demo.log",
            self.root / "logs" / "st_a2_runner.log",
        ]
        lines: list[str] = []
        for path in paths:
            if not path.exists():
                continue
            try:
                lines.extend(path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:])
            except Exception:
                continue
        return lines[-limit:]

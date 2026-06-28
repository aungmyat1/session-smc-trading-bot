from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AUDIT_LOG_PATH = ROOT / "logs" / "dashboard_audit.jsonl"


def write_audit_log(action: str, *, status: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "status": status,
        "detail": detail or {},
    }
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")
    return record


def tail_audit_log(limit: int = 50) -> list[dict[str, Any]]:
    if not AUDIT_LOG_PATH.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in AUDIT_LOG_PATH.read_text(encoding="utf-8").splitlines()[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records

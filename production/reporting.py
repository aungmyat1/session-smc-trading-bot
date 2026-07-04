"""Deterministic paired JSON/Markdown operating reports."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


class OperationsReportService:
    TYPES = frozenset({"daily", "session", "health", "risk", "recovery"})

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def write(self, report_type: str, report_id: str, payload: Mapping[str, Any]) -> dict[str, str]:
        if report_type not in self.TYPES:
            raise ValueError("unsupported operations report type")
        canonical = {"schema": "system2-operations-report/v1", "report_id": report_id, "report_type": report_type, **dict(payload)}
        raw = (json.dumps(canonical, indent=2, sort_keys=True, default=str) + "\n").encode()
        digest = hashlib.sha256(raw).hexdigest()
        folder = self.root / report_type
        folder.mkdir(parents=True, exist_ok=True)
        json_path, md_path = folder / f"{report_id}.json", folder / f"{report_id}.md"
        json_path.write_bytes(raw)
        lines = [f"# {report_type.title()} Report", "", f"Report ID: `{report_id}`", f"SHA-256: `{digest}`", "", "```json", json.dumps(canonical, indent=2, sort_keys=True, default=str), "```", ""]
        md_path.write_text("\n".join(lines), encoding="utf-8")
        return {"json": str(json_path), "markdown": str(md_path), "sha256": digest}

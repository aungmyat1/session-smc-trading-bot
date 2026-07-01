from __future__ import annotations

import json

from scripts.registry_audit import build_audit, write_outputs


def test_registry_audit_writes_all_formats(tmp_path):
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config" / "strategy_catalog.yaml").write_text(
        """
current_strategy: null
strategies:
  AuditStrat:
    status: shadow
    approved: false
    version: "0.1"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    audit = build_audit(tmp_path)
    outputs = write_outputs(audit, tmp_path / "reports")

    assert len(outputs) == 3
    payload = json.loads((tmp_path / "reports" / "registry_audit.json").read_text(encoding="utf-8"))
    assert payload["strategy_count"] == 1

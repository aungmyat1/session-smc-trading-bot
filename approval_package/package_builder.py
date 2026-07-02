from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from approval_package.package_signature import sign_files

REQUIRED_EVIDENCE = ("strategy_spec.yaml", "backtest_report.md", "replay_report.md", "risk_report.md", "validation_summary.json")


def build_approval_package(
    output_dir: Path | str,
    *,
    evidence: dict[str, Path | str],
    validation_summary: dict[str, Any] | None = None,
    expires_at: datetime,
    signing_key: str | None = None,
) -> Path:
    """Build an APPROVED package only after explicit passing evidence is supplied."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    for name in REQUIRED_EVIDENCE:
        if name == "validation_summary.json" and validation_summary is not None:
            (directory / name).write_text(json.dumps(validation_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            continue
        source = evidence.get(name)
        if source is None or not Path(source).is_file():
            raise ValueError(f"missing approval evidence: {name}")
        shutil.copyfile(source, directory / name)
    summary = json.loads((directory / "validation_summary.json").read_text(encoding="utf-8"))
    if str(summary.get("risk_check", "")).upper() != "PASS" or str(summary.get("validation", "")).upper() != "PASS":
        raise ValueError("validation and risk_check must both PASS")
    now = datetime.now(timezone.utc)
    expiry = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
    if expiry <= now:
        raise ValueError("package expiry must be in the future")
    status = {"approval_status": "APPROVED", "approved_at": now.isoformat(), "expires_at": expiry.isoformat()}
    (directory / "approval_status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    unsigned = {path.name: path.read_bytes() for path in directory.iterdir() if path.is_file() and path.name != "signature.txt"}
    signature = sign_files(unsigned, signing_key)
    (directory / "signature.txt").write_text(json.dumps(signature, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return directory

#!/usr/bin/env python3
# ruff: noqa: E402
"""Validate immutable strategy-package/v2 archives without extracting them."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.strategy_package import validate_canonical_package

def validate_archive(path: Path, *, signing_key: str | None = None) -> dict[str, Any]:
    result = validate_canonical_package(
        path,
        signing_key=signing_key if signing_key is not None else os.getenv("SVOS_PACKAGE_VERIFYING_PUBLIC_KEY", ""),
    )
    return {"valid": result.valid, "errors": list(result.reasons), "manifest": result.manifest}


def _self_test() -> int:
    from datetime import datetime, timedelta, timezone
    from tempfile import TemporaryDirectory

    from shared.strategy_package import build_canonical_package

    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "package.tar.gz"
        now = datetime.now(timezone.utc)
        build_canonical_package(
            path,
            strategy_id="SELF-TEST",
            strategy_version="1.0.0",
            adapter_id="self-test",
            adapter_version="1.0.0",
            strategy_spec="strategy_id: SELF-TEST\n",
            parameters={"symbols": ["EURUSD"], "period": 1},
            risk_policy={"max_risk_pct": 0.1},
            evidence={"test": "PASS"},
            governance_snapshot={"strategies": {"SELF-TEST": {"latest_version": "1.0.0", "evidence_count": 1, "decision_count": 0, "approval_count": 1, "latest_approval": None}}},
            approval={"decision": "APPROVED", "approved_at": now.isoformat(), "expires_at": (now + timedelta(days=1)).isoformat(), "revoked": False},
            signing_key="11" * 32,
        )
        public_key = "d04ab232742bb4ab3a1368bd4615e4e6d0224ab71a016baf8520a332c9778737"
        return 0 if validate_archive(path, signing_key=public_key)["valid"] else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", nargs="?", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return _self_test()
    if args.archive is None:
        parser.error("archive is required unless --self-test is used")
    result = validate_archive(args.archive)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

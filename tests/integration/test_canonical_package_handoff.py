from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import ANY, patch

import pytest

from approval_package.package_builder import build_approval_package
from scripts.migrate_strategy_package import migrate_legacy_package
from shared.strategy_package import build_canonical_package, validate_canonical_package


def test_legacy_package_migration_preserves_provenance(tmp_path: Path) -> None:
    legacy_key = "legacy-key"
    canonical_private_key = "11" * 32
    canonical_public_key = "d04ab232742bb4ab3a1368bd4615e4e6d0224ab71a016baf8520a332c9778737"
    evidence = {}
    for name, content in {
        "strategy_spec.yaml": "strategy_id: ST-A2\nversion: 2.1.0\n",
        "backtest_report.md": "PASS\n",
        "replay_report.md": "PASS\n",
        "risk_report.md": "PASS\n",
    }.items():
        path = tmp_path / name
        path.write_text(content, encoding="utf-8")
        evidence[name] = path
    legacy = build_approval_package(
        tmp_path / "legacy",
        evidence=evidence,
        validation_summary={"validation": "PASS", "risk_check": "PASS"},
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        signing_key=legacy_key,
    )
    status_path = legacy / "approval_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status["strategy_id"] = "ST-A2"
    status["strategy_version"] = "2.1.0"
    status_path.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # The legacy signature must cover the enriched identity metadata.
    from approval_package.package_signature import sign_files

    unsigned = {path.name: path.read_bytes() for path in legacy.iterdir() if path.name != "signature.txt"}
    (legacy / "signature.txt").write_text(json.dumps(sign_files(unsigned, legacy_key), indent=2, sort_keys=True) + "\n")

    migrated = migrate_legacy_package(
        legacy,
        tmp_path / "canonical.tar.gz",
        adapter_id="ST2Adapter",
        adapter_version="2.1.0",
        parameters={"symbols": ["EURUSD"], "session": "London"},
        risk_policy={"policy_id": "demo-v1", "max_risk_pct": 0.3},
        legacy_signing_key=legacy_key,
        canonical_signing_key=canonical_private_key,
    )
    result = validate_canonical_package(migrated.archive_path, signing_key=canonical_public_key)
    assert result.valid, result.reasons


def test_portfolio_accepts_canonical_package_before_runtime_start(tmp_path: Path, monkeypatch) -> None:
    from scripts import run_portfolio

    private_key = "11" * 32
    public_key = "d04ab232742bb4ab3a1368bd4615e4e6d0224ab71a016baf8520a332c9778737"
    package = build_canonical_package(
        tmp_path / "canonical.tar.gz",
        strategy_id="ST-A2",
        strategy_version="2.1.0",
        adapter_id="ST2Adapter",
        adapter_version="2.1.0",
        strategy_spec="strategy_id: ST-A2\nversion: 2.1.0\n",
        parameters={"symbols": ["EURUSD"], "session": "London"},
        risk_policy={"policy_id": "demo-v1", "max_risk_pct": 0.3},
        evidence={"replay": "PASS"},
        approval={"decision": "APPROVED", "approved_at": "2026-01-01T00:00:00+00:00", "expires_at": "2099-01-01T00:00:00+00:00", "revoked": False},
        signing_key=private_key,
    )
    monkeypatch.setenv("SVOS_PACKAGE_VERIFYING_PUBLIC_KEY", public_key)
    with (
        patch("sys.argv", ["run_portfolio.py", "--mode", "demo", "--strategy-package", package.archive_path, "--strategy-id", "ST-A2"]),
        patch.object(run_portfolio, "validate_strategy_identity") as identity,
        patch.object(run_portfolio, "run") as runtime,
        patch.object(run_portfolio, "_ROOT", tmp_path),
    ):
        identity.return_value.strategy_id = "ST-A2"
        identity.return_value.require_valid.return_value = None
        run_portfolio.main()
    runtime.assert_awaited_once_with("demo", 60, "ST-A2", ANY, ANY)


def test_invalid_canonical_package_is_rejected_before_runtime_start(tmp_path: Path, monkeypatch) -> None:
    from scripts import run_portfolio

    path = tmp_path / "invalid.tar.gz"
    path.write_bytes(b"not a package")
    monkeypatch.setenv("SVOS_PACKAGE_VERIFYING_PUBLIC_KEY", "d04ab232742bb4ab3a1368bd4615e4e6d0224ab71a016baf8520a332c9778737")
    with (
        patch("sys.argv", ["run_portfolio.py", "--mode", "demo", "--strategy-package", str(path)]),
        patch.object(run_portfolio, "run") as runtime,
        patch.object(run_portfolio, "_ROOT", tmp_path),
        pytest.raises(SystemExit),
    ):
        run_portfolio.main()
    runtime.assert_not_awaited()

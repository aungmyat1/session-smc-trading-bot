from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from approval_package.package_validator import validate_package
from scripts.build_demo_package_fixture import DEMO_FIXTURE_SIGNING_KEY, build_fixture
from scripts.run_demo_smoke_test import run_preflight
from scripts.validate_strategy_identity import validate_strategy_identity

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "tests" / "fixtures" / "demo_approved_package"
REGISTRY = ROOT / "tests" / "fixtures" / "svos_demo_registry"


def _hashes(directory: Path) -> dict[str, str]:
    return {item.name: hashlib.sha256(item.read_bytes()).hexdigest() for item in sorted(directory.iterdir()) if item.is_file()}


def test_demo_package_fixture_is_deterministic(tmp_path: Path) -> None:
    first = build_fixture(tmp_path / "first", tmp_path / "registry-a" / "ST-A2")
    second = build_fixture(tmp_path / "second", tmp_path / "registry-b" / "ST-A2")
    assert _hashes(first) == _hashes(second)
    assert _hashes(PACKAGE) == _hashes(first)


def test_demo_package_passes_validation() -> None:
    result = validate_package(PACKAGE, signing_key=DEMO_FIXTURE_SIGNING_KEY)
    assert result.valid, result.reasons


def test_demo_package_identity_matches_test_registry() -> None:
    result = validate_strategy_identity(root=ROOT, package_path=PACKAGE, runner_strategy_id="ST-A2", registry_root=REGISTRY)
    assert result.valid, result.mismatches


def test_package_identity_mismatch_stops_preflight(tmp_path: Path) -> None:
    result = validate_strategy_identity(root=ROOT, package_path=PACKAGE, runner_strategy_id="NYMomentum", registry_root=REGISTRY)
    assert not result.valid
    with pytest.raises(PermissionError, match="strategy identity rejected"):
        from scripts.run_portfolio import _ensure_strategy_package

        _ensure_strategy_package(
            str(PACKAGE),
            "NYMomentum",
            signing_key=DEMO_FIXTURE_SIGNING_KEY,
            root=ROOT,
            registry_root=REGISTRY,
        )


def test_live_mode_is_rejected_before_smoke_preflight(tmp_path: Path) -> None:
    with pytest.raises(PermissionError, match="live mode is blocked"):
        run_preflight(
            package_path=PACKAGE,
            signing_key=DEMO_FIXTURE_SIGNING_KEY,
            output_dir=tmp_path,
            registry_root=REGISTRY,
            mode="live",
        )
    assert not (tmp_path / "demo_smoke_report.json").exists()
    assert not (tmp_path / "demo_smoke_report.md").exists()


def test_offline_smoke_test_passes_without_broker_or_order_and_writes_reports(tmp_path: Path) -> None:
    result = run_preflight(
        package_path=PACKAGE,
        signing_key=DEMO_FIXTURE_SIGNING_KEY,
        output_dir=tmp_path,
        registry_root=REGISTRY,
    )
    assert result.passed, result.failures
    assert result.broker_connection_attempted is False
    assert result.order_submission_attempted is False
    assert result.live_trading_enabled is False
    assert (tmp_path / "demo_smoke_report.json").is_file()
    assert (tmp_path / "demo_smoke_report.md").is_file()

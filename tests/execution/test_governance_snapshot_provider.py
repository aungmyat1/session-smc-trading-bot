from __future__ import annotations

import json
from pathlib import Path

from execution.governance_snapshot import GovernanceSnapshot
from execution.governance_snapshot_provider import GovernanceSnapshotProvider
from shared.strategy_package import build_canonical_package

PRIVATE_KEY = "11" * 32
APPROVAL = {
    "decision": "APPROVED",
    "approved_at": "2026-01-01T00:00:00+00:00",
    "expires_at": "2099-01-01T00:00:00+00:00",
    "revoked": False,
}
GOVERNANCE_SNAPSHOT = {
    "strategies": {
        "ST-A2": {
            "latest_version": "2.1.0",
            "evidence_count": 3,
            "decision_count": 2,
            "approval_count": 1,
            "latest_approval": {"decision": "APPROVED"},
        }
    }
}


def _build_package(path: Path):
    return build_canonical_package(
        path,
        strategy_id="ST-A2",
        strategy_version="2.1.0",
        adapter_id="ST2Adapter",
        adapter_version="2.1.0",
        strategy_spec="strategy_id: ST-A2\n",
        parameters={"symbols": ["EURUSD"], "session": "London"},
        risk_policy={"policy_id": "demo-v1"},
        evidence={"replay": {"status": "PASS"}},
        governance_snapshot=GOVERNANCE_SNAPSHOT,
        approval=APPROVAL,
        signing_key=PRIVATE_KEY,
    )


def test_missing_loose_snapshot_returns_none(tmp_path: Path) -> None:
    provider = GovernanceSnapshotProvider(root=tmp_path)
    assert provider.get("ST-A2") is None


def test_loose_snapshot_file_is_read_when_no_package_given(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "strategy_snapshots.json"
    snapshot_path.write_text(json.dumps({"strategies": {"ST-A2": GOVERNANCE_SNAPSHOT["strategies"]["ST-A2"]}}), encoding="utf-8")

    provider = GovernanceSnapshotProvider(root=tmp_path, snapshot_path=snapshot_path)
    snapshot = provider.get("ST-A2")

    assert isinstance(snapshot, GovernanceSnapshot)
    assert snapshot.latest_version == "2.1.0"
    assert snapshot.evidence_count == 3


def test_snapshot_is_read_from_verified_package(tmp_path: Path) -> None:
    build = _build_package(tmp_path / "package.tar.gz")

    provider = GovernanceSnapshotProvider(root=tmp_path, package_path=build.archive_path)
    snapshot = provider.get("ST-A2")

    assert isinstance(snapshot, GovernanceSnapshot)
    assert snapshot.latest_version == "2.1.0"
    assert snapshot.evidence_count == 3
    assert snapshot.decision_count == 2
    assert snapshot.approval_count == 1
    assert snapshot.latest_approval == {"decision": "APPROVED"}


def test_package_preferred_over_loose_file_when_both_available(tmp_path: Path) -> None:
    build = _build_package(tmp_path / "package.tar.gz")
    snapshot_path = tmp_path / "strategy_snapshots.json"
    snapshot_path.write_text(
        json.dumps({"strategies": {"ST-A2": {"latest_version": "9.9.9", "evidence_count": 0, "decision_count": 0, "approval_count": 0, "latest_approval": None}}}),
        encoding="utf-8",
    )

    provider = GovernanceSnapshotProvider(root=tmp_path, snapshot_path=snapshot_path, package_path=build.archive_path)
    snapshot = provider.get("ST-A2")

    assert snapshot is not None
    assert snapshot.latest_version == "2.1.0"


def test_missing_package_falls_back_to_loose_file(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "strategy_snapshots.json"
    snapshot_path.write_text(json.dumps({"strategies": {"ST-A2": GOVERNANCE_SNAPSHOT["strategies"]["ST-A2"]}}), encoding="utf-8")

    provider = GovernanceSnapshotProvider(
        root=tmp_path,
        snapshot_path=snapshot_path,
        package_path=tmp_path / "does-not-exist.tar.gz",
    )
    snapshot = provider.get("ST-A2")

    assert snapshot is not None
    assert snapshot.latest_version == "2.1.0"


def test_malformed_package_degrades_gracefully_never_raises(tmp_path: Path) -> None:
    bad_package = tmp_path / "bad.tar.gz"
    bad_package.write_bytes(b"not a real archive")

    provider = GovernanceSnapshotProvider(root=tmp_path, package_path=bad_package)
    assert provider.get("ST-A2") is None

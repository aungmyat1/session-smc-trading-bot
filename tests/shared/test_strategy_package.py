from __future__ import annotations

import gzip
import io
import json
import tarfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from shared.strategy_package import build_canonical_package, validate_canonical_package

PRIVATE_KEY = "11" * 32
PUBLIC_KEY = "d04ab232742bb4ab3a1368bd4615e4e6d0224ab71a016baf8520a332c9778737"
APPROVAL = {
    "decision": "APPROVED",
    "approved_at": "2026-01-01T00:00:00+00:00",
    "expires_at": "2099-01-01T00:00:00+00:00",
    "revoked": False,
    "authority": "test-governance",
}


GOVERNANCE_SNAPSHOT = {
    "strategies": {
        "ST-A2": {
            "latest_version": "2.1.0",
            "evidence_count": 3,
            "decision_count": 2,
            "approval_count": 1,
            "latest_approval": {"decision": "APPROVED", "current_version_id": "v1"},
        }
    }
}


def _build(path: Path, *, governance_snapshot: dict | None = None):
    return build_canonical_package(
        path,
        strategy_id="ST-A2",
        strategy_version="2.1.0",
        adapter_id="ST2Adapter",
        adapter_version="2.1.0",
        strategy_spec="strategy_id: ST-A2\nversion: 2.1.0\n",
        parameters={"symbols": ["EURUSD"], "session": "London", "pair": "EURUSD"},
        risk_policy={"policy_id": "demo-v1", "max_risk_pct": 0.3},
        evidence={"replay": {"status": "PASS", "sha256": "a" * 64}},
        governance_snapshot=governance_snapshot if governance_snapshot is not None else GOVERNANCE_SNAPSHOT,
        approval=APPROVAL,
        signing_key=PRIVATE_KEY,
        provenance={"source_format": "test-fixture"},
    )


def _replace_member(path: Path, member_name: str, value: bytes) -> None:
    with tarfile.open(path, "r:gz") as source:
        files = {name: source.extractfile(name).read() for name in source.getnames()}
    files[member_name] = value
    raw = io.BytesIO()
    with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w") as archive:
            for name, content in sorted(files.items()):
                info = tarfile.TarInfo(name)
                info.size = len(content)
                info.mode = 0o444
                info.mtime = 0
                archive.addfile(info, io.BytesIO(content))
    path.write_bytes(raw.getvalue())


def test_canonical_build_is_deterministic_and_valid(tmp_path: Path) -> None:
    first = _build(tmp_path / "first.tar.gz")
    second = _build(tmp_path / "second.tar.gz")

    assert first.package_id == second.package_id
    assert first.archive_sha256 == second.archive_sha256
    assert (tmp_path / "first.tar.gz").read_bytes() == (tmp_path / "second.tar.gz").read_bytes()
    result = validate_canonical_package(first.archive_path, signing_key=PUBLIC_KEY)
    assert result.valid, result.reasons
    assert result.archive_sha256 == first.archive_sha256

    schema = json.loads((Path(__file__).resolve().parents[2] / "schemas" / "strategy-package-v2.schema.json").read_text())
    Draft202012Validator(schema).validate(result.manifest)


@pytest.mark.parametrize(
    ("member", "payload"),
    [
        ("strategy_spec.md", b"strategy_id: OTHER\n"),
        ("parameters.json", b'{"session":"New York"}\n'),
        ("risk_policy.json", b'{"max_risk_pct":99}\n'),
        ("evidence_manifest.json", b'{"replay":{"status":"FAIL"}}\n'),
        ("governance_snapshot.json", b'{"strategies":{"ST-A2":{"latest_version":"9.9.9"}}}\n'),
        ("approval.json", b'{"decision":"REJECTED","revoked":false}\n'),
    ],
)
def test_every_semantic_member_is_signature_protected(tmp_path: Path, member: str, payload: bytes) -> None:
    build = _build(tmp_path / "package.tar.gz")
    _replace_member(Path(build.archive_path), member, payload)
    result = validate_canonical_package(build.archive_path, signing_key=PUBLIC_KEY)
    assert not result.valid
    assert any("hash" in reason or "signature" in reason for reason in result.reasons)


def test_expiry_revocation_identity_adapter_and_key_fail_closed(tmp_path: Path) -> None:
    build = _build(tmp_path / "package.tar.gz")
    path = build.archive_path

    assert not validate_canonical_package(path, signing_key="wrong").valid
    assert not validate_canonical_package(path, signing_key=PUBLIC_KEY, now=datetime(2100, 1, 1, tzinfo=timezone.utc)).valid
    assert not validate_canonical_package(path, signing_key=PUBLIC_KEY, revoked_package_ids={build.package_id}).valid
    assert not validate_canonical_package(path, signing_key=PUBLIC_KEY, expected_strategy_id="OTHER").valid
    assert not validate_canonical_package(path, signing_key=PUBLIC_KEY, expected_adapter_version="9.9.9").valid


def test_builder_rejects_missing_governed_contracts(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="signing key"):
        build_canonical_package(
            tmp_path / "invalid.tar.gz",
            strategy_id="ST-A2",
            strategy_version="2.1.0",
            adapter_id="ST2Adapter",
            adapter_version="2.1.0",
            strategy_spec="strategy_id: ST-A2\n",
            parameters={"symbols": ["EURUSD"], "session": "London"},
            risk_policy={"max_risk_pct": 0.3},
            evidence={"replay": "PASS"},
            governance_snapshot={"strategies": {"ST-A2": {}}},
            approval=APPROVAL,
            signing_key="",
        )


def test_builder_rejects_empty_governance_snapshot(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="governance snapshot"):
        build_canonical_package(
            tmp_path / "invalid.tar.gz",
            strategy_id="ST-A2",
            strategy_version="2.1.0",
            adapter_id="ST2Adapter",
            adapter_version="2.1.0",
            strategy_spec="strategy_id: ST-A2\n",
            parameters={"symbols": ["EURUSD"], "session": "London"},
            risk_policy={"max_risk_pct": 0.3},
            evidence={"replay": "PASS"},
            governance_snapshot={},
            approval=APPROVAL,
            signing_key=PRIVATE_KEY,
        )


def test_package_includes_governance_snapshot_member_and_manifest_reflects_it(tmp_path: Path) -> None:
    build = _build(tmp_path / "package.tar.gz")

    with tarfile.open(build.archive_path, "r:gz") as archive:
        names = sorted(archive.getnames())
        member = archive.extractfile("governance_snapshot.json")
        payload = json.loads(member.read().decode("utf-8"))

    assert "governance_snapshot.json" in names
    assert payload == GOVERNANCE_SNAPSHOT
    assert "governance_snapshot.json" in build.manifest["members"]

    result = validate_canonical_package(build.archive_path, signing_key=PUBLIC_KEY)
    assert result.valid, result.reasons


def test_package_missing_governance_snapshot_member_is_rejected(tmp_path: Path) -> None:
    build = _build(tmp_path / "package.tar.gz")
    path = Path(build.archive_path)

    with tarfile.open(path, "r:gz") as source:
        files = {name: source.extractfile(name).read() for name in source.getnames() if name != "governance_snapshot.json"}
    raw = io.BytesIO()
    with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w") as archive:
            for name, content in sorted(files.items()):
                info = tarfile.TarInfo(name)
                info.size = len(content)
                info.mode = 0o444
                info.mtime = 0
                archive.addfile(info, io.BytesIO(content))
    path.write_bytes(raw.getvalue())

    result = validate_canonical_package(path, signing_key=PUBLIC_KEY)
    assert not result.valid
    assert any("missing required members" in reason and "governance_snapshot.json" in reason for reason in result.reasons)


def test_runtime_api_version_mismatch_is_rejected(tmp_path: Path) -> None:
    build = _build(tmp_path / "package.tar.gz")
    path = Path(build.archive_path)

    with tarfile.open(path, "r:gz") as source:
        manifest = json.loads(source.extractfile("manifest.json").read())
    manifest["runtime_api_version"] = "system2-runtime/v1"
    _replace_member(path, "manifest.json", (json.dumps(manifest, sort_keys=True) + "\n").encode("utf-8"))

    result = validate_canonical_package(path, signing_key=PUBLIC_KEY)
    assert not result.valid
    assert any("runtime_api_version" in reason for reason in result.reasons)

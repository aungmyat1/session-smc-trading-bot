from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from production.engine.runtime import RuntimeAuthority, RuntimeOwnershipError, RuntimeState
from shared.strategy_package import build_canonical_package

PRIVATE_KEY = "11" * 32
PUBLIC_KEY = "d04ab232742bb4ab3a1368bd4615e4e6d0224ab71a016baf8520a332c9778737"


def _package(tmp_path: Path, *, expires_at: str = "2099-01-01T00:00:00+00:00") -> Path:
    build = build_canonical_package(
        tmp_path / "runtime-package.tar.gz",
        strategy_id="ST-A2",
        strategy_version="2.1.0",
        adapter_id="ST2Adapter",
        adapter_version="2.1.0",
        strategy_spec="# Runtime fixture\n",
        parameters={"symbols": ["EURUSD"], "session": "London"},
        risk_policy={"policy_id": "demo-v1", "live_trading_enabled": False},
        evidence={"virtual_demo": {"status": "PASS"}},
        approval={"decision": "APPROVED", "approved_at": "2026-01-01T00:00:00+00:00", "expires_at": expires_at, "revoked": False},
        signing_key=PRIVATE_KEY,
    )
    return Path(build.archive_path)


@pytest.mark.asyncio
async def test_valid_package_starts_one_authoritative_runtime_and_reports_state(tmp_path: Path) -> None:
    package = _package(tmp_path)
    observed = []
    authority = RuntimeAuthority(root=tmp_path, package_path=package, verifying_public_key=PUBLIC_KEY, expected_strategy_id="ST-A2")

    async def runtime(context) -> None:
        observed.append((authority.snapshot().state, context.package_id, context.broker_adapter, context.risk_enforcer))

    await authority.run(runtime)

    assert observed and observed[0][0] == RuntimeState.RUNNING
    assert observed[0][1]
    assert observed[0][2:] == ("vantage-demo", "demo-risk-firewall")
    assert authority.snapshot().state == RuntimeState.STOPPED
    assert authority.persisted_state()["state"] == "STOPPED"
    assert not authority.lock_path.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["unsigned", "expired", "revoked", "mismatch"])
async def test_invalid_packages_are_rejected_before_runtime_callback(tmp_path: Path, failure: str) -> None:
    package = _package(tmp_path, expires_at="2026-02-01T00:00:00+00:00" if failure == "expired" else "2099-01-01T00:00:00+00:00")
    key = "22" * 32 if failure == "unsigned" else PUBLIC_KEY
    expected = "OTHER" if failure == "mismatch" else "ST-A2"
    if failure == "revoked":
        from shared.strategy_package import validate_canonical_package

        package_id = validate_canonical_package(package, signing_key=PUBLIC_KEY).package_id
        revocations = tmp_path / "data" / "production" / "revoked_packages.json"
        revocations.parent.mkdir(parents=True)
        revocations.write_text(f'{{"package_ids":["{package_id}"]}}\n', encoding="utf-8")
    called = False
    authority = RuntimeAuthority(root=tmp_path, package_path=package, verifying_public_key=key, expected_strategy_id=expected)

    async def runtime(_context) -> None:
        nonlocal called
        called = True

    with pytest.raises(PermissionError):
        await authority.run(runtime)
    assert called is False
    assert authority.snapshot().state == RuntimeState.REJECTED
    assert not authority.lock_path.exists()


@pytest.mark.asyncio
async def test_duplicate_runtime_owner_is_rejected(tmp_path: Path) -> None:
    package = _package(tmp_path)
    entered = asyncio.Event()
    release = asyncio.Event()
    first = RuntimeAuthority(root=tmp_path, package_path=package, verifying_public_key=PUBLIC_KEY)
    second = RuntimeAuthority(root=tmp_path, package_path=package, verifying_public_key=PUBLIC_KEY)

    async def holding_runtime(_context) -> None:
        entered.set()
        await release.wait()

    first_task = asyncio.create_task(first.run(holding_runtime))
    await entered.wait()
    state_before = first.state_path.read_bytes()
    events_before = first.events_path.read_bytes()
    with pytest.raises(RuntimeOwnershipError):
        await second.run(lambda _context: asyncio.sleep(0))
    assert first.state_path.read_bytes() == state_before
    assert first.events_path.read_bytes() == events_before
    release.set()
    await first_task
    assert first.snapshot().state == RuntimeState.STOPPED


@pytest.mark.asyncio
async def test_cancellation_performs_safe_shutdown_and_releases_ownership(tmp_path: Path) -> None:
    package = _package(tmp_path)
    entered = asyncio.Event()
    authority = RuntimeAuthority(root=tmp_path, package_path=package, verifying_public_key=PUBLIC_KEY)

    async def runtime(_context) -> None:
        entered.set()
        await asyncio.Event().wait()

    task = asyncio.create_task(authority.run(runtime))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert authority.snapshot().state == RuntimeState.STOPPED
    assert not authority.lock_path.exists()
    events = authority.events_path.read_text(encoding="utf-8")
    assert "runtime_ownership_released" in events
    assert "safe shutdown complete" in events

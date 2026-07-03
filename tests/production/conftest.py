from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def canonical_package_signing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SVOS_PACKAGE_SIGNING_PRIVATE_KEY", "11" * 32)
    monkeypatch.setenv("SVOS_PACKAGE_VERIFYING_PUBLIC_KEY", "d04ab232742bb4ab3a1368bd4615e4e6d0224ab71a016baf8520a332c9778737")

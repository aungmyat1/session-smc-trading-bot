"""Read-only loader for `GovernanceSnapshot` audit data.

This module has zero `svos.*` imports. It reads governance snapshot data from
one of two sources and returns snapshots by strategy name:

1. A verified `strategy-package/v2` archive's `governance_snapshot.json`
   member (built by SVOS at package time -- see
   `svos/deployment/service.py`'s `build_strategy_package` and
   `svos/governance/snapshot.py`). This is plumbing only: this provider does
   not perform package signature/expiry verification itself -- that already
   happens upstream (e.g. `production/verifier.py`) before a package is
   trusted. When a `package_path` is supplied, this is preferred whenever it
   yields data.
2. The loose, pre-exported snapshot file (produced by
   `scripts/export_governance_snapshot.py`, which does have SVOS access) --
   the existing dev-workflow path for strategies that don't have a built
   package yet. This path is unchanged: when no `package_path` is supplied
   (the default), behavior is identical to before this source was added.

Missing or malformed data from either source degrades gracefully to `None` --
callers must treat a missing snapshot as "no audit metadata available", never
as a reason to change an execution decision.
"""

from __future__ import annotations

import json
import tarfile
from pathlib import Path
from typing import Any

from execution.governance_snapshot import GovernanceSnapshot

DEFAULT_SNAPSHOT_PATH = Path("artifacts/svos/strategy_snapshots.json")
PACKAGED_SNAPSHOT_MEMBER = "governance_snapshot.json"


class GovernanceSnapshotProvider:
    """Loads governance snapshots from a packaged archive and/or a JSON export file."""

    def __init__(
        self,
        *,
        root: Path | str,
        snapshot_path: Path | str | None = None,
        package_path: Path | str | None = None,
    ) -> None:
        self.root = Path(root)
        self.snapshot_path = (
            Path(snapshot_path) if snapshot_path is not None else self.root / DEFAULT_SNAPSHOT_PATH
        )
        self.package_path = Path(package_path) if package_path is not None else None

    def _strategies_dict(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            return {}
        strategies = data.get("strategies", data)
        return strategies if isinstance(strategies, dict) else {}

    def _load_from_package(self) -> dict[str, Any]:
        if self.package_path is None:
            return {}
        try:
            with tarfile.open(self.package_path, "r:gz") as archive:
                member = archive.extractfile(PACKAGED_SNAPSHOT_MEMBER)
                if member is None:
                    return {}
                data = json.loads(member.read().decode("utf-8"))
        except (OSError, tarfile.TarError, KeyError, ValueError, UnicodeDecodeError):
            return {}
        return self._strategies_dict(data)

    def _load_from_loose_file(self) -> dict[str, Any]:
        try:
            raw = self.snapshot_path.read_text(encoding="utf-8")
        except OSError:
            return {}
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return {}
        return self._strategies_dict(data)

    def _load_payload(self) -> dict[str, Any]:
        packaged = self._load_from_package()
        if packaged:
            return packaged
        return self._load_from_loose_file()

    def get(self, strategy_name: str) -> GovernanceSnapshot | None:
        """Return the snapshot for `strategy_name`, or None if unavailable."""
        strategies = self._load_payload()
        entry = strategies.get(strategy_name)
        if not isinstance(entry, dict):
            return None
        try:
            return GovernanceSnapshot(
                strategy_name=strategy_name,
                latest_version=entry.get("latest_version"),
                evidence_count=int(entry.get("evidence_count", 0) or 0),
                decision_count=int(entry.get("decision_count", 0) or 0),
                approval_count=int(entry.get("approval_count", 0) or 0),
                latest_approval=entry.get("latest_approval"),
            )
        except (TypeError, ValueError):
            return None

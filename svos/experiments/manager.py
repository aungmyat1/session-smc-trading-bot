"""Experiment manager — pre-registration and lifecycle tracking for research trials.

Every parameter change or strategy variant gets a row here BEFORE the pipeline run.
Results are appended after completion. Storage is append-only JSONL, matching the
pattern used by StrategyRegistryService.

Usage::

    mgr = ExperimentManager(root="/path/to/project")
    rec = mgr.register("ST-A2", hypothesis="Wider SL reduces false exits", parameters={"sl_pips": 3}, actor="quant")
    # ... run pipeline ...
    mgr.complete(rec.experiment_id, run_id="abc123", status="FAIL", verdict="PF_2x < 1.0", metadata={})
"""

from __future__ import annotations

import builtins
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from svos.shared.support import append_jsonl, now_iso, read_jsonl


@dataclass(slots=True)
class ExperimentRecord:
    experiment_id: str
    strategy: str
    hypothesis: str
    parameters: dict[str, Any]
    run_id: str
    status: str          # PENDING | RUNNING | PASS | FAIL | INCONCLUSIVE
    verdict: str
    registered_at: str
    completed_at: str | None
    metadata: dict[str, Any] = field(default_factory=dict)
    actor: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExperimentManager:
    """Append-only experiment register for SVOS research trials.

    Data is stored as JSONL under:
        <root>/data/svos/experiments/<strategy>/experiments.jsonl
    """

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root)

    def _path(self, strategy: str) -> Path:
        return self._root / "data" / "svos" / "experiments" / strategy / "experiments.jsonl"

    def _experiment_id(self, strategy: str, hypothesis: str, parameters: dict[str, Any]) -> str:
        raw = json.dumps(
            {"strategy": strategy, "hypothesis": hypothesis, "parameters": parameters},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def register(
        self,
        strategy: str,
        hypothesis: str,
        parameters: dict[str, Any],
        *,
        actor: str,
    ) -> ExperimentRecord:
        """Pre-register an experiment before the pipeline run.

        The experiment_id is deterministic: identical strategy + hypothesis +
        parameters produce the same ID, so accidental re-registration is idempotent.

        Raises:
            ValueError: if strategy, hypothesis, or actor are empty.
        """
        if not strategy:
            raise ValueError("strategy must not be empty")
        if not hypothesis:
            raise ValueError("hypothesis must not be empty")
        if not actor:
            raise ValueError("actor must not be empty")

        experiment_id = self._experiment_id(strategy, hypothesis, parameters)

        # Idempotent: if already registered with same ID, return existing record
        existing = self._find(strategy, experiment_id)
        if existing is not None:
            return existing

        rec = ExperimentRecord(
            experiment_id=experiment_id,
            strategy=strategy,
            hypothesis=hypothesis,
            parameters=parameters,
            run_id="",
            status="PENDING",
            verdict="",
            registered_at=now_iso(),
            completed_at=None,
            metadata={},
            actor=actor,
        )
        append_jsonl(self._path(strategy), rec.to_dict())
        return rec

    def complete(
        self,
        experiment_id: str,
        *,
        run_id: str,
        status: str,
        verdict: str,
        metadata: dict[str, Any] | None = None,
    ) -> ExperimentRecord:
        """Mark an experiment as complete and append the updated record.

        JSONL is append-only: completion writes a new entry with the same ID.
        `get()` and `list()` return the most-recent entry for each ID.

        Raises:
            KeyError: if the experiment_id is not found for any strategy.
            ValueError: if status is not a recognised terminal value.
        """
        valid_statuses = {"PASS", "FAIL", "INCONCLUSIVE", "RUNNING"}
        if status not in valid_statuses:
            raise ValueError(f"status must be one of {valid_statuses}, got {status!r}")

        # Search across all strategy journals for this experiment_id
        rec = self._find_any(experiment_id)
        if rec is None:
            raise KeyError(f"experiment_id not found: {experiment_id}")

        updated = ExperimentRecord(
            experiment_id=rec.experiment_id,
            strategy=rec.strategy,
            hypothesis=rec.hypothesis,
            parameters=rec.parameters,
            run_id=run_id,
            status=status,
            verdict=verdict,
            registered_at=rec.registered_at,
            completed_at=now_iso(),
            metadata=metadata or {},
            actor=rec.actor,
        )
        append_jsonl(self._path(rec.strategy), updated.to_dict())
        return updated

    def get(self, experiment_id: str) -> ExperimentRecord:
        """Return the most-recent record for the given experiment_id.

        Raises:
            KeyError: if not found in any strategy journal.
        """
        rec = self._find_any(experiment_id)
        if rec is None:
            raise KeyError(f"experiment_id not found: {experiment_id}")
        return rec

    def list(self, strategy: str | None = None) -> list[dict[str, Any]]:
        """Return the most-recent record per experiment_id, optionally filtered by strategy.

        Results are ordered by registered_at ascending.
        """
        if strategy is not None:
            return self._dedup_latest(read_jsonl(self._path(strategy)))

        # Scan all strategy subdirectories
        experiments_root = self._root / "data" / "svos" / "experiments"
        all_rows: list[dict[str, Any]] = []
        if experiments_root.exists():
            for sub in experiments_root.iterdir():
                if sub.is_dir():
                    all_rows.extend(read_jsonl(sub / "experiments.jsonl"))
        return self._dedup_latest(all_rows)

    # ── internals ──────────────────────────────────────────────────────────

    def _find(self, strategy: str, experiment_id: str) -> ExperimentRecord | None:
        rows = read_jsonl(self._path(strategy))
        latest: dict[str, Any] | None = None
        for row in rows:
            if row.get("experiment_id") == experiment_id:
                latest = row
        return _row_to_record(latest) if latest else None

    def _find_any(self, experiment_id: str) -> ExperimentRecord | None:
        experiments_root = self._root / "data" / "svos" / "experiments"
        if not experiments_root.exists():
            return None
        latest: dict[str, Any] | None = None
        for sub in experiments_root.iterdir():
            if not sub.is_dir():
                continue
            for row in read_jsonl(sub / "experiments.jsonl"):
                if row.get("experiment_id") == experiment_id:
                    latest = row
        return _row_to_record(latest) if latest else None

    @staticmethod
    def _dedup_latest(rows: builtins.list[dict[str, Any]]) -> builtins.list[dict[str, Any]]:
        seen: dict[str, dict[str, Any]] = {}
        for row in rows:
            eid = row.get("experiment_id", "")
            if eid:
                seen[eid] = row
        return sorted(seen.values(), key=lambda r: r.get("registered_at", ""))


def _row_to_record(row: dict[str, Any]) -> ExperimentRecord:
    return ExperimentRecord(
        experiment_id=row.get("experiment_id", ""),
        strategy=row.get("strategy", ""),
        hypothesis=row.get("hypothesis", ""),
        parameters=row.get("parameters", {}),
        run_id=row.get("run_id", ""),
        status=row.get("status", "PENDING"),
        verdict=row.get("verdict", ""),
        registered_at=row.get("registered_at", ""),
        completed_at=row.get("completed_at"),
        metadata=row.get("metadata", {}),
        actor=row.get("actor", ""),
    )

"""Generated read-only YAML compatibility projection from PostgreSQL."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Callable

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import StageState, StrategyEntity, StrategyVersion


def write_catalog_projection(
    session_factory: Callable[[], Session],
    destination: Path | str,
) -> Path:
    """Atomically replace a compatibility projection; never use it for writes."""
    output = Path(destination)
    with session_factory() as session:
        rows = session.execute(
            select(StrategyEntity, StageState, StrategyVersion)
            .join(StageState, StageState.strategy_id == StrategyEntity.id)
            .join(StrategyVersion, StrategyVersion.id == StageState.current_version_id)
            .order_by(StrategyEntity.slug)
        ).all()
    payload = {
        "generated_projection": True,
        "current_strategy": None,
        "strategies": {
            entity.slug: {
                "status": state.current_stage,
                "approved": False,
                "current": False,
                "version": version.version,
                "owner": entity.owner,
                "strategy_id": str(entity.id),
                "strategy_spec_hash": version.spec_hash,
            }
            for entity, state, version in rows
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", dir=output.parent, prefix=".catalog-", encoding="utf-8", delete=False) as handle:
        yaml.safe_dump(payload, handle, sort_keys=False)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    try:
        os.replace(temporary, output)
        output.chmod(0o444)
    finally:
        temporary.unlink(missing_ok=True)
    return output

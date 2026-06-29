"""Idempotent import of legacy YAML catalog records as non-qualifying state."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import LegacyImport, StageState, StrategyEntity, StrategyVersion


@dataclass(frozen=True, slots=True)
class ImportResult:
    source_sha256: str
    imported: bool
    strategy_count: int


class LegacyCatalogImporter:
    """Import identity/spec snapshots without granting lifecycle qualification."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def import_catalog(self, path: Path | str, *, actor: str) -> ImportResult:
        if not actor.strip():
            raise ValueError("actor is required")
        source = Path(path)
        raw = source.read_bytes()
        source_hash = hashlib.sha256(raw).hexdigest()
        payload = yaml.safe_load(raw) or {}
        strategies = payload.get("strategies") or {}
        if not isinstance(strategies, dict):
            raise ValueError("catalog strategies must be a mapping")

        with self.session_factory() as session:
            with session.begin():
                existing = session.scalar(
                    select(LegacyImport).where(
                        LegacyImport.source_path == str(source.resolve()),
                        LegacyImport.source_sha256 == source_hash,
                        LegacyImport.record_type == "strategy_catalog",
                    )
                )
                if existing is not None:
                    return ImportResult(source_hash, False, existing.record_count)

                imported = 0
                for name, raw_manifest in strategies.items():
                    manifest = raw_manifest if isinstance(raw_manifest, dict) else {}
                    slug = str(name).strip()
                    entity = session.scalar(select(StrategyEntity).where(StrategyEntity.slug == slug))
                    if entity is None:
                        entity = StrategyEntity(name=slug, slug=slug, owner=str(manifest.get("owner", "")) or None)
                        session.add(entity)
                        session.flush()
                    version_label = str(manifest.get("version", "0.0.0"))
                    version = session.scalar(
                        select(StrategyVersion).where(
                            StrategyVersion.strategy_id == entity.id,
                            StrategyVersion.version == version_label,
                        )
                    )
                    if version is None:
                        canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
                        version = StrategyVersion(
                            strategy_id=entity.id,
                            version=version_label,
                            spec_hash=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
                            rules_json=manifest,
                            notes="LEGACY_IMPORTED — cannot satisfy qualification gates",
                            created_by=actor,
                        )
                        session.add(version)
                        session.flush()
                    state = session.scalar(select(StageState).where(StageState.strategy_id == entity.id))
                    if state is None:
                        session.add(
                            StageState(
                                strategy_id=entity.id,
                                current_stage="DRAFT",
                                current_version_id=version.id,
                                opt_lock=0,
                                updated_by=actor,
                            )
                        )
                    imported += 1

                timestamp = datetime.fromtimestamp(source.stat().st_mtime, tz=timezone.utc)
                session.add(
                    LegacyImport(
                        source_path=str(source.resolve()),
                        source_sha256=source_hash,
                        source_timestamp=timestamp,
                        record_type="strategy_catalog",
                        record_count=imported,
                        imported_by=actor,
                    )
                )
            return ImportResult(source_hash, True, imported)

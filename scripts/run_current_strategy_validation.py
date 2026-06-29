#!/usr/bin/env python3
"""Run validation for the catalog's current strategy without auto-promotion.

This is the minimum-friction revalidation path for a demo-stage strategy:
1. Pin the requested strategy as the current catalog target.
2. Run replay/backtest/regression validation with promotion disabled.
3. Persist the validation outcome back into the catalog metadata.
4. Optionally mirror the strategy state into the research PostgreSQL table.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from db.runtime import normalize_database_url
from core.strategy_registry import (
    get_current_strategy_name,
    get_strategy_manifest,
)
from research.validation.engine import ValidationRunner, load_validation_config

try:
    import psycopg2
    from psycopg2.extras import Json
except Exception:  # pragma: no cover - optional dependency/runtime availability
    psycopg2 = None
    Json = None


def _load_json(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    file_path = Path(path)
    if not file_path.exists():
        return {}
    return json.loads(file_path.read_text(encoding="utf-8"))


def _load_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload = _load_json(args.payload)
    if payload:
        return payload
    return {
        "replay": _load_json(args.replay_json),
        "backtest": _load_json(args.backtest_json),
        "latest_metrics": _load_json(args.latest_json),
        "previous_metrics": _load_json(args.previous_json),
    }


def _has_validation_input(args: argparse.Namespace) -> bool:
    return any(
        [
            args.payload,
            args.replay_json,
            args.backtest_json,
            args.latest_json,
            args.previous_json,
        ]
    )


def _latest_validation_report(report_root: Path, strategy: str) -> Path | None:
    strategy_dir = report_root / strategy
    if not strategy_dir.exists():
        return None
    reports = sorted(strategy_dir.glob("*/validation.json"))
    return reports[-1].parent if reports else None


def _sync_catalog_to_postgres(catalog_path: Path, database_url: str) -> dict[str, Any]:
    if psycopg2 is None:
        return {"synced": False, "reason": "psycopg2 unavailable"}

    payload = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or {}
    strategies = payload.get("strategies", {})
    current_strategy = payload.get("current_strategy")

    database_url = normalize_database_url(database_url)
    try:
        conn = psycopg2.connect(database_url)
    except Exception as exc:  # pragma: no cover - database may be absent locally
        return {"synced": False, "reason": str(exc)}

    synced = 0
    try:
        with conn:
            with conn.cursor() as cur:
                for name, manifest in strategies.items():
                    if not isinstance(manifest, dict):
                        continue
                    version = str(manifest.get("version", "1.0"))
                    description = str(manifest.get("description", ""))
                    status = str(manifest.get("status", "draft"))
                    rules_json = {
                        "current": name == current_strategy,
                        "catalog_status": status,
                        "owner": manifest.get("owner"),
                        "symbols": manifest.get("symbols", []),
                        "timeframes": manifest.get("timeframes", []),
                        "deployment_target": manifest.get("deployment_target"),
                        "verification": {
                            "last_revalidated_at": manifest.get("last_revalidated_at"),
                            "last_revalidation_status": manifest.get("last_revalidation_status"),
                            "last_revalidation_report": manifest.get("last_revalidation_report"),
                            "validation_mode": manifest.get("validation_mode"),
                        },
                    }
                    cur.execute(
                        """
                        INSERT INTO research.strategies
                            (strategy_name, version, description, rules_json, status)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (strategy_name, version) DO UPDATE SET
                            description = EXCLUDED.description,
                            rules_json = EXCLUDED.rules_json,
                            status = EXCLUDED.status
                        """,
                        (
                            name,
                            version,
                            description,
                            Json(rules_json),
                            status,
                        ),
                    )
                    synced += 1
    finally:
        conn.close()

    return {"synced": True, "strategies": synced, "current_strategy": current_strategy}


def main() -> int:
    parser = argparse.ArgumentParser(description="Revalidate the catalog's current strategy")
    parser.add_argument("--strategy", help="Strategy to mark as current before revalidation")
    parser.add_argument("--catalog", default="config/strategy_catalog.yaml", help="Strategy catalog YAML")
    parser.add_argument("--payload", help="Combined JSON payload with replay/backtest/latest metrics")
    parser.add_argument("--replay-json", help="Replay validation payload JSON")
    parser.add_argument("--backtest-json", help="Backtest validation payload JSON")
    parser.add_argument("--latest-json", help="Latest metrics JSON")
    parser.add_argument("--previous-json", help="Previous metrics JSON")
    parser.add_argument("--stage", default="demo", help="Current lifecycle stage")
    parser.add_argument("--outdir", default="reports/current_strategy_validation", help="Validation report output directory")
    parser.add_argument("--config", default="config/validation.yaml", help="Validation config YAML")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""), help="PostgreSQL research DB URL")
    parser.add_argument("--sync-db", action="store_true", help="Mirror catalog metadata into PostgreSQL")
    args = parser.parse_args()

    catalog_path = Path(args.catalog)
    if not catalog_path.is_absolute():
        catalog_path = _ROOT / catalog_path

    strategy = args.strategy or get_current_strategy_name(catalog_path)
    if not strategy:
        raise SystemExit("No current strategy set in the catalog and no --strategy provided.")

    if get_strategy_manifest(strategy, catalog_path) is None:
        raise SystemExit(f"Strategy not found in catalog: {strategy}")

    if not _has_validation_input(args):
        raise SystemExit(
            "No validation payload supplied. Provide --payload or one of "
            "--replay-json/--backtest-json/--latest-json/--previous-json."
        )

    payload = _load_payload(args)
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = _ROOT / config_path
    config = load_validation_config(config_path)

    runner = ValidationRunner(strategy, config=config, registry_path=catalog_path, output_dir=_ROOT / args.outdir)
    bundle = runner.run(
        payload.get("replay") or None,
        payload.get("backtest") or None,
        payload.get("latest_metrics") or None,
        previous_metrics=payload.get("previous_metrics") or None,
        current_stage=args.stage,
        promote=False,
    )

    report_dir = _latest_validation_report(_ROOT / args.outdir, strategy)
    sync_summary: dict[str, Any] = {"synced": False, "reason": "not requested"}
    if args.sync_db and args.database_url:
        sync_summary = _sync_catalog_to_postgres(catalog_path, args.database_url)

    output = {
        "strategy": strategy,
        "current_strategy": get_current_strategy_name(catalog_path),
        "overall_status": bundle.overall_status,
        "lifecycle_recommendation": bundle.lifecycle_recommendation,
        "next_stage": bundle.next_stage,
        "promoted": bundle.promoted,
        "report_dir": str(report_dir) if report_dir else None,
        "catalog_path": str(catalog_path),
        "sync": sync_summary,
    }
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0 if bundle.overall_status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

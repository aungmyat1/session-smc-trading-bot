#!/usr/bin/env python3
"""Run the full SVOS pipeline for the catalog's current strategy.

This is the highest-level orchestration entrypoint in the repo:
- load the current strategy from the catalog
- load the audited strategy spec text from the catalog-linked document
- run audit, replay, backtest, robustness, demo, and production approval
- record the result back into the catalog without requiring manual text entry
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from core.strategy_registry import (
    get_current_strategy_name,
    get_strategy_manifest,
    get_strategy_spec_text,
    set_current_strategy,
    update_strategy_manifest,
)
from research.svos.payload_builder import build_svos_payload_bundle
from research.svos.engine import SVOSRunner
from research.validation.engine import load_validation_config


def _load_json(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    file_path = Path(path)
    if not file_path.exists():
        return {}
    return json.loads(file_path.read_text(encoding="utf-8"))


def _resolve_strategy_text(strategy: str, catalog_path: Path, explicit_text: str | None, explicit_file: str | None) -> str:
    if explicit_text:
        return explicit_text
    if explicit_file:
        file_path = Path(explicit_file)
        if not file_path.is_absolute():
            file_path = _ROOT / file_path
        if file_path.exists():
            return file_path.read_text(encoding="utf-8")
    text = get_strategy_spec_text(strategy, catalog_path)
    return text or ""


def _load_catalog_path(raw: str | None) -> Path:
    catalog_path = Path(raw or "config/strategy_catalog.yaml")
    if not catalog_path.is_absolute():
        catalog_path = _ROOT / catalog_path
    return catalog_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SVOS for the current strategy")
    parser.add_argument("--strategy", help="Strategy to validate; defaults to current catalog strategy")
    parser.add_argument("--catalog", default="config/strategy_catalog.yaml", help="Strategy catalog YAML")
    parser.add_argument("--strategy-text", help="Inline strategy description")
    parser.add_argument("--strategy-file", help="Path to strategy description text")
    parser.add_argument("--replay-json", help="Replay validation JSON")
    parser.add_argument("--backtest-json", help="Backtest validation JSON")
    parser.add_argument("--robustness-json", help="Robustness validation JSON")
    parser.add_argument("--demo-json", help="Demo validation JSON")
    parser.add_argument("--symbol", action="append", help="Symbol(s) to auto-load when building payloads")
    parser.add_argument("--start", help="Start date for auto payload generation")
    parser.add_argument("--end", help="End date for auto payload generation")
    parser.add_argument("--costs-json", help="Optional costs.json for auto-generated backtest payload")
    parser.add_argument(
        "--no-synthetic-demo",
        dest="allow_synthetic_demo",
        action="store_false",
        help="Disable the auto-generated demo payload",
    )
    parser.set_defaults(allow_synthetic_demo=True)
    parser.add_argument("--outdir", default="reports/current_strategy_svos", help="Output directory")
    parser.add_argument("--config", default="config/validation.yaml", help="Validation config YAML")
    args = parser.parse_args()

    catalog_path = _load_catalog_path(args.catalog)
    strategy = args.strategy or get_current_strategy_name(catalog_path)
    if not strategy:
        raise SystemExit("No current strategy is set in the catalog and no --strategy was provided.")
    if get_strategy_manifest(strategy, catalog_path) is None:
        raise SystemExit(f"Strategy not found in catalog: {strategy}")

    set_current_strategy(strategy, catalog_path)
    strategy_text = _resolve_strategy_text(strategy, catalog_path, args.strategy_text, args.strategy_file)
    if not strategy_text.strip():
        raise SystemExit(
            f"No strategy spec text available for {strategy}. Set strategy_spec_path in the catalog "
            "or pass --strategy-text/--strategy-file."
        )

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = _ROOT / config_path
    validation_config = load_validation_config(config_path)

    payload = None
    if not any([args.replay_json, args.backtest_json, args.robustness_json, args.demo_json]):
        payload_bundle = build_svos_payload_bundle(
            strategy=strategy,
            catalog_path=catalog_path,
            symbols=args.symbol,
            start=args.start,
            end=args.end,
            costs_json=args.costs_json,
            allow_synthetic_demo=args.allow_synthetic_demo,
            output_dir=_ROOT / args.outdir / strategy / "auto_payload",
        )
        payload = payload_bundle.to_dict()

    runner = SVOSRunner(
        strategy,
        registry_path=catalog_path,
        output_dir=_ROOT / args.outdir,
        validation_config=validation_config,
    )
    result = runner.run_pipeline(
        strategy_text,
        replay=(_load_json(args.replay_json) or payload.get("replay")) if payload else (_load_json(args.replay_json) or None),
        backtest=(_load_json(args.backtest_json) or payload.get("backtest")) if payload else (_load_json(args.backtest_json) or None),
        robustness=(_load_json(args.robustness_json) or payload.get("robustness")) if payload else (_load_json(args.robustness_json) or None),
        demo=(_load_json(args.demo_json) or payload.get("demo")) if payload else (_load_json(args.demo_json) or None),
        promote=False,
    )

    report_root = _ROOT / args.outdir / strategy
    update_strategy_manifest(
        strategy,
        {
            "last_svos_at": datetime.now(timezone.utc).isoformat(),
            "last_svos_status": result.overall_status,
            "last_svos_promoted_stage": result.promoted_stage or "",
            "last_svos_report": str(report_root),
            "validation_mode": "svos",
            "last_svos_payload_auto": bool(payload),
        },
        catalog_path,
    )

    output = {
        "strategy": strategy,
        "current_strategy": get_current_strategy_name(catalog_path),
        "overall_status": result.overall_status,
        "promoted_stage": result.promoted_stage,
        "report_dir": str(report_root),
        "catalog_path": str(catalog_path),
        "payload": payload,
    }
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0 if result.overall_status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

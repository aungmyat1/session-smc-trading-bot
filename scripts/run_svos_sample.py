#!/usr/bin/env python3
"""Run and verify a safe, isolated six-stage SVOS sample."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_ROOT = ROOT / "examples" / "svos_sample"
STRATEGY = "SVOS-SAMPLE"

sys.path.insert(0, str(ROOT))

from core.strategy_registry import get_strategy_manifest  # noqa: E402
from research.svos.engine import SVOSRunner  # noqa: E402

REPORTS = (
    ("strategy_audit", "01_strategy_audit"),
    ("historical_replay", "02_historical_replay"),
    ("backtest", "03_backtest"),
    ("robustness", "04_robustness"),
    ("virtual_demo", "05_virtual_demo"),
    ("production_approval", "06_production_approval"),
)

REQUIRED_REPORT_FIELDS = {
    "schema_version",
    "report_id",
    "run_id",
    "strategy_id",
    "strategy_version",
    "stage",
    "status",
    "score",
    "promotion_allowed",
    "thresholds",
    "hard_gate_results",
    "metrics",
    "findings",
    "evidence_hashes",
    "remediation",
    "version_comparison",
    "generated_at",
}


def _load_json(name: str) -> dict[str, Any]:
    return json.loads((SAMPLE_ROOT / name).read_text(encoding="utf-8"))


def _write_isolated_catalog(path: Path) -> None:
    payload = {
        "current_strategy": STRATEGY,
        "strategies": {
            STRATEGY: {
                "status": "walk_forward",
                "approved": True,
                "current": True,
                "version": "1.0.0",
                "owner": "svos-sample-harness",
                "symbols": ["EURUSD"],
                "timeframes": ["M15", "H1"],
                "deployment_target": "isolated-validation",
                "description": "Deterministic SVOS report-system fixture",
            }
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def verify_report_package(report_dir: Path) -> dict[str, Any]:
    summary_json = report_dir / "run_summary.json"
    summary_markdown = report_dir / "run_summary.md"
    if not summary_json.is_file() or not summary_markdown.is_file():
        raise AssertionError("SVOS sample did not generate both run summary formats")

    summary = json.loads(summary_json.read_text(encoding="utf-8"))
    if summary.get("overall_status") != "IN_PROGRESS":
        raise AssertionError(
            f"SVOS sample summary has unexpected status: {summary.get('overall_status')}"
        )
    if summary.get("latest_passed_stage") != "virtual_demo":
        raise AssertionError("SVOS sample did not reach Virtual Demo")
    if summary.get("active_blocker"):
        raise AssertionError(
            f"SVOS sample unexpectedly has a blocker: {summary['active_blocker']}"
        )

    verified: list[dict[str, Any]] = []
    for expected_stage, stem in REPORTS:
        json_path = report_dir / f"{stem}.json"
        markdown_path = report_dir / f"{stem}.md"
        if not json_path.is_file() or not markdown_path.is_file():
            raise AssertionError(
                f"Missing JSON/Markdown report pair for {expected_stage}"
            )
        report = json.loads(json_path.read_text(encoding="utf-8"))
        missing = sorted(REQUIRED_REPORT_FIELDS.difference(report))
        if missing:
            raise AssertionError(
                f"{expected_stage} report is missing fields: {', '.join(missing)}"
            )
        if report.get("stage") != expected_stage:
            raise AssertionError(
                f"Unexpected stage in {json_path}: {report.get('stage')}"
            )
        expected_status = (
            "NOT_RUN" if expected_stage == "production_approval" else "PASS"
        )
        if report.get("status") != expected_status:
            raise AssertionError(
                f"{expected_stage} has unexpected status: {report.get('status')}"
            )
        if expected_status == "PASS" and report.get("score") is None:
            raise AssertionError(f"{expected_stage} did not produce a diagnostic score")
        if not report.get("evidence_hashes", {}).get("strategy_spec"):
            raise AssertionError(
                f"{expected_stage} did not preserve the strategy specification hash"
            )
        markdown = markdown_path.read_text(encoding="utf-8")
        if f"Status: **{expected_status}**" not in markdown:
            raise AssertionError(
                f"Markdown decision does not match JSON for {expected_stage}"
            )
        verified.append(
            {
                "stage": expected_stage,
                "status": report["status"],
                "score": report["score"],
                "promotion_allowed": report["promotion_allowed"],
                "json": str(json_path),
                "markdown": str(markdown_path),
            }
        )

    return {
        "run_id": summary["run_id"],
        "strategy_id": summary["strategy_id"],
        "strategy_version": summary["strategy_version"],
        "overall_status": summary["overall_status"],
        "report_dir": str(report_dir),
        "reports_verified": len(verified),
        "stages": verified,
    }


def run_sample(output_root: Path | str) -> dict[str, Any]:
    output_root = Path(output_root).resolve()
    strategy_text = (SAMPLE_ROOT / "strategy.md").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="svos-sample-") as temp:
        state_root = Path(temp)
        catalog_path = state_root / "config" / "strategy_catalog.yaml"
        _write_isolated_catalog(catalog_path)
        runner = SVOSRunner(
            STRATEGY,
            registry_path=catalog_path,
            output_dir=state_root / "legacy_reports",
            canonical_output_dir=output_root,
        )
        result = runner.run_pipeline(
            strategy_text,
            replay=_load_json("replay.json"),
            backtest=_load_json("backtest.json"),
            robustness=_load_json("robustness.json"),
            virtual_demo=_load_json("virtual_demo.json"),
            promote=False,
            allow_live_promotion=False,
        )
        if result.overall_status != "PASS":
            failed = [
                (stage.stage, stage.status)
                for stage in result.stages
                if stage.status != "PASS"
            ]
            raise AssertionError(f"SVOS sample pipeline failed: {failed}")
        manifest = get_strategy_manifest(STRATEGY, catalog_path) or {}
        if manifest.get("status") == "live":
            raise AssertionError("Isolated sample must never promote to live")
        report_dir = Path(result.canonical_report["report_dir"])
        verification = verify_report_package(report_dir)
        verification["isolated_catalog_final_status"] = manifest.get("status")
        verification["live_promotion_requested"] = False
        return verification


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "reports" / "svos"),
        help="Canonical report root (default: reports/svos)",
    )
    args = parser.parse_args()
    try:
        result = run_sample(args.output_dir)
    except (AssertionError, OSError, ValueError) as exc:
        print(
            json.dumps({"status": "FAIL", "error": str(exc)}, indent=2), file=sys.stderr
        )
        return 1
    print(json.dumps({"status": "PASS", **result}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

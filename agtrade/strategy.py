from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import yaml

from core.strategy_registry import get_strategy_manifest
from research.svos.engine import SVOSRunner
from strategy_audit.cli import main as strategy_audit_main
from strategy_validation.cli import main as strategy_validation_main
from svos.application.pipeline import StrategyPipeline
from svos.orchestration import SVOSPlatform

_ROOT = Path(__file__).resolve().parents[1]
_SAMPLE_ROOT = _ROOT / "examples" / "svos_sample"
_SAMPLE_STRATEGY = "SVOS-SAMPLE"

_PHASE_LABELS = {
    "INTAKE": "INTAKE",
    "AUDIT": "AUDIT",
    "REPLAY": "REPLAY",
    "BACKTEST": "BACKTEST",
    "ROBUSTNESS": "ROBUSTNESS",
    "VIRTUAL_DEMO": "VIRTUAL DEMO",
}

_REPORTS = (
    ("strategy_audit", "01_strategy_audit"),
    ("historical_replay", "02_historical_replay"),
    ("backtest", "03_backtest"),
    ("robustness", "04_robustness"),
    ("virtual_demo", "05_virtual_demo"),
    ("production_approval", "06_production_approval"),
)

_REQUIRED_REPORT_FIELDS = {
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


def _synthetic_trades(n: int = 60) -> list[dict[str, Any]]:
    trades = []
    for i in range(n):
        day = min(i + 1, 28)
        month = min((i // 28) + 1, 12)
        ts = f"2024-{month:02d}-{day:02d}T08:00:00Z"
        is_win = i % 10 < 7
        result_r = 2.0 if is_win else -1.0
        entry = round(1.10 + i * 0.001, 5)
        sl = round(entry - 0.0020, 5)
        tp = round(entry + 0.0040, 5)
        trades.append(
            {
                "timestamp": ts,
                "symbol": "EURUSD",
                "direction": "long",
                "entry_price": entry,
                "stop_loss": sl,
                "take_profit": tp,
                "result": "win" if is_win else "loss",
                "result_r": result_r,
                "std_net_r": result_r,
            }
        )
    return trades


def _metrics_from_trades(trades: list[dict[str, Any]]) -> dict[str, Any]:
    wins = [t for t in trades if float(t.get("result_r", 0) or 0) > 0]
    losses = [t for t in trades if float(t.get("result_r", 0) or 0) < 0]
    gross_wins = sum(float(t["result_r"]) for t in wins)
    gross_losses = abs(sum(float(t["result_r"]) for t in losses)) or 1.0
    pf = round(gross_wins / gross_losses, 4)
    wr = round(len(wins) / len(trades), 4) if trades else 0.0
    exp = round(sum(float(t["result_r"]) for t in trades) / len(trades), 4) if trades else 0.0
    return {
        "trade_count": len(trades),
        "win_rate": wr,
        "profit_factor": pf,
        "profit_factor_2x": round(pf * 0.85, 4),
        "expectancy": exp,
        "max_drawdown": 6.0,
        "spread_included": True,
        "commission_included": True,
    }


def _load_json_file(path: str | None) -> list[Any] | dict[str, Any] | None:
    if not path:
        return None
    file_path = Path(path)
    if not file_path.exists():
        print(f"[agtrade] WARNING: file not found: {path}", file=sys.stderr)
        return None
    return json.loads(file_path.read_text(encoding="utf-8"))


def _print_table(strategy: str, phases: list[Any], approval_path: str) -> None:
    col_phase = 13
    col_status = 8
    col_time = 10
    top = f"┌{'─' * col_phase}┬{'─' * col_status}┬{'─' * col_time}┐"
    header = f"│{'Phase':^{col_phase}}│{'Status':^{col_status}}│{'Time (s)':^{col_time}}│"
    sep = f"├{'─' * col_phase}┼{'─' * col_status}┼{'─' * col_time}┤"
    bottom = f"└{'─' * col_phase}┴{'─' * col_status}┴{'─' * col_time}┘"

    print(f"\nSVOS Pipeline — {strategy}")
    print(top)
    print(header)
    print(sep)
    for phase in phases:
        label = _PHASE_LABELS.get(phase.phase, phase.phase)
        elapsed = f"{phase.elapsed_s:.2f}" if phase.status != "SKIPPED" else "—"
        print(f"│{label:<{col_phase}}│{phase.status:^{col_status}}│{elapsed:>{col_time - 1}} │")
    print(bottom)
    overall_status = "PASS" if all(phase.status == "PASS" for phase in phases) else "FAIL"
    print(f"Result: {overall_status}  |  Approval package: {approval_path or 'n/a'}")


def svos_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="agtrade strategy svos",
        description="Run a strategy through the full SVOS 6-phase pipeline.",
    )
    parser.add_argument("strategy", help="Strategy name (must match catalog key)")
    parser.add_argument("--spec", required=True, metavar="FILE", help="Path to strategy spec text file")
    parser.add_argument("--trades", metavar="FILE", help="JSON file of trade dicts for replay")
    parser.add_argument("--metrics", metavar="FILE", help="JSON file with backtest metrics dict")
    parser.add_argument("--signals", metavar="FILE", help="JSON file of signal dicts for virtual demo")
    parser.add_argument("--dataset-id", default="", metavar="TEXT", help="Dataset snapshot ID")
    parser.add_argument("--actor", default="cli", metavar="TEXT", help="Actor identity")
    parser.add_argument("--symbol", default="EURUSD", metavar="TEXT", help="Trading symbol")
    parser.add_argument(
        "--catalog",
        default="config/strategy_catalog.yaml",
        metavar="PATH",
        help="Path to strategy_catalog.yaml",
    )
    parser.add_argument("--root", default=".", metavar="PATH", help="Project root directory")
    parser.add_argument("--expected-pf", type=float, default=None, metavar="FLOAT", help="Expected profit factor for drift check")
    args = parser.parse_args(argv)

    spec_path = Path(args.spec)
    if not spec_path.exists():
        print(f"[agtrade] ERROR: spec file not found: {args.spec}", file=sys.stderr)
        return 1
    specification = spec_path.read_text(encoding="utf-8")

    root_path = Path(args.root).resolve()
    catalog_path = Path(args.catalog) if Path(args.catalog).is_absolute() else root_path / args.catalog

    platform = SVOSPlatform(root=root_path, catalog_path=catalog_path)
    platform.bootstrap()

    trades_raw = _load_json_file(args.trades)
    trades = trades_raw if isinstance(trades_raw, list) else _synthetic_trades(60)

    metrics_raw = _load_json_file(args.metrics)
    metrics = metrics_raw if isinstance(metrics_raw, dict) else _metrics_from_trades(trades)

    signals_raw = _load_json_file(args.signals)
    signals = signals_raw if isinstance(signals_raw, list) else trades

    pipeline = StrategyPipeline(platform)
    phase_names = ["INTAKE", "AUDIT", "REPLAY", "BACKTEST", "ROBUSTNESS", "VIRTUAL_DEMO"]
    for index, phase_name in enumerate(phase_names, start=1):
        print(f"[{index}/{len(phase_names)}] Running {_PHASE_LABELS[phase_name]}...", flush=True)

    started = time.monotonic()
    result = pipeline.run(
        args.strategy,
        specification,
        trades=trades,
        metrics=metrics,
        signals=signals,
        actor=args.actor,
        dataset_id=args.dataset_id,
        expected_pf=args.expected_pf,
        symbol=args.symbol,
    )
    _ = time.monotonic() - started

    _print_table(args.strategy, result.phases, result.approval_package_path)
    return 0 if result.passed else 1


def sample_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run and verify a safe, isolated six-stage SVOS sample.")
    parser.add_argument(
        "--output-dir",
        default=str(_ROOT / "reports" / "svos"),
        help="Canonical report root (default: reports/svos)",
    )
    args = parser.parse_args(argv)
    try:
        result = run_sample(args.output_dir)
    except (AssertionError, OSError, ValueError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1
    print(json.dumps({"status": "PASS", **result}, indent=2, sort_keys=True))
    return 0


def validate_main(argv: list[str] | None = None) -> int:
    return strategy_validation_main(argv)


def audit_main(argv: list[str] | None = None) -> int:
    return strategy_audit_main(argv)


def _load_sample_json(name: str) -> dict[str, Any]:
    return json.loads((_SAMPLE_ROOT / name).read_text(encoding="utf-8"))


def _write_isolated_catalog(path: Path) -> None:
    payload = {
        "current_strategy": _SAMPLE_STRATEGY,
        "strategies": {
            _SAMPLE_STRATEGY: {
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
        raise AssertionError(f"SVOS sample summary has unexpected status: {summary.get('overall_status')}")
    if summary.get("latest_passed_stage") != "virtual_demo":
        raise AssertionError("SVOS sample did not reach Virtual Demo")
    if summary.get("active_blocker"):
        raise AssertionError(f"SVOS sample unexpectedly has a blocker: {summary['active_blocker']}")

    verified: list[dict[str, Any]] = []
    for expected_stage, stem in _REPORTS:
        json_path = report_dir / f"{stem}.json"
        markdown_path = report_dir / f"{stem}.md"
        if not json_path.is_file() or not markdown_path.is_file():
            raise AssertionError(f"Missing JSON/Markdown report pair for {expected_stage}")
        report = json.loads(json_path.read_text(encoding="utf-8"))
        missing = sorted(_REQUIRED_REPORT_FIELDS.difference(report))
        if missing:
            raise AssertionError(f"{expected_stage} report is missing fields: {', '.join(missing)}")
        if report.get("stage") != expected_stage:
            raise AssertionError(f"Unexpected stage in {json_path}: {report.get('stage')}")
        expected_status = "NOT_RUN" if expected_stage == "production_approval" else "PASS"
        if report.get("status") != expected_status:
            raise AssertionError(f"{expected_stage} has unexpected status: {report.get('status')}")
        if expected_status == "PASS" and report.get("score") is None:
            raise AssertionError(f"{expected_stage} did not produce a diagnostic score")
        if not report.get("evidence_hashes", {}).get("strategy_spec"):
            raise AssertionError(f"{expected_stage} did not preserve the strategy specification hash")
        markdown = markdown_path.read_text(encoding="utf-8")
        if f"Status: **{expected_status}**" not in markdown:
            raise AssertionError(f"Markdown decision does not match JSON for {expected_stage}")
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
    strategy_text = (_SAMPLE_ROOT / "strategy.md").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="svos-sample-") as temporary_dir:
        state_root = Path(temporary_dir)
        catalog_path = state_root / "config" / "strategy_catalog.yaml"
        _write_isolated_catalog(catalog_path)
        runner = SVOSRunner(
            _SAMPLE_STRATEGY,
            registry_path=catalog_path,
            output_dir=state_root / "legacy_reports",
            canonical_output_dir=output_root,
        )
        result = runner.run_pipeline(
            strategy_text,
            replay=_load_sample_json("replay.json"),
            backtest=_load_sample_json("backtest.json"),
            robustness=_load_sample_json("robustness.json"),
            virtual_demo=_load_sample_json("virtual_demo.json"),
            promote=False,
            allow_live_promotion=False,
        )
        if result.overall_status != "PASS":
            failed = [(stage.stage, stage.status) for stage in result.stages if stage.status != "PASS"]
            raise AssertionError(f"SVOS sample pipeline failed: {failed}")
        manifest = get_strategy_manifest(_SAMPLE_STRATEGY, catalog_path) or {}
        if manifest.get("status") == "live":
            raise AssertionError("Isolated sample must never promote to live")
        report_dir = Path(result.canonical_report["report_dir"])
        verification = verify_report_package(report_dir)
        verification["isolated_catalog_final_status"] = manifest.get("status")
        verification["live_promotion_requested"] = False
        return verification

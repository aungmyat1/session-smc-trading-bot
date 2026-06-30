#!/usr/bin/env python3
"""Entry point for the Production Approval Agent."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import argparse
import logging

from agents.approval.agent import ApprovalAgent, ReleaseStatus, load_config
from agents.approval.report import ApprovalReport
from agents.quality.runner import run as run_quality
from agents.testing.runner import run as run_testing


def _refresh_upstream_reports(root: Path, output_dir: Path, log_level: str) -> None:
    run_testing(["--root", str(root), "--output-dir", str(output_dir), "--log-level", log_level])
    run_quality(["--root", str(root), "--output-dir", str(output_dir), "--log-level", log_level])


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Production Approval Agent")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, default=Path("reports"))
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--skip-refresh", action="store_true", help="Use existing upstream reports instead of regenerating them first")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
    )

    root = args.root.resolve()
    output_dir = args.output_dir.resolve()
    if not args.skip_refresh:
        _refresh_upstream_reports(root, output_dir, args.log_level)

    config = load_config(root)
    agent = ApprovalAgent(root, config)
    result = agent.run()

    reporter = ApprovalReport(result)
    reporter.write_json(output_dir / "approval_report.json")
    reporter.write_json(output_dir / "production_readiness_report.json")
    reporter.write_markdown(output_dir / "production_readiness_report.md")

    return 0 if result.release_status == ReleaseStatus.APPROVED else 1


if __name__ == "__main__":
    sys.exit(run())

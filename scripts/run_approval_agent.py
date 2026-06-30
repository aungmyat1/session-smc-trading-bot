#!/usr/bin/env python3
"""Entry point for the Production Approval Agent."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import argparse  # noqa: E402
import logging  # noqa: E402

from agents.approval.agent import (
    ApprovalAgent,
    ReleaseStatus,
    load_config,
)  # noqa: E402
from agents.approval.report import ApprovalReport  # noqa: E402


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Production Approval Agent")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, default=Path("reports"))
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
    )

    root = args.root.resolve()
    config = load_config(root)
    agent = ApprovalAgent(root, config)
    result = agent.run()

    reporter = ApprovalReport(result)
    reporter.write_json(args.output_dir / "approval_report.json")
    reporter.write_json(args.output_dir / "production_readiness_report.json")
    reporter.write_markdown(args.output_dir / "production_readiness_report.md")

    return 0 if result.release_status == ReleaseStatus.APPROVED else 1


if __name__ == "__main__":
    sys.exit(run())

"""Testing Agent runner — CLI wrapper and config loader."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

import yaml

from agents.testing.agent import Status, TestingAgent
from agents.testing.report import TestingReport


def _load_config(path: Path) -> dict[str, Any]:
    if path.exists():
        with open(path) as fh:
            return yaml.safe_load(fh) or {}
    return {}


def run(argv: list[str] | None = None) -> int:
    """Parse CLI args, execute all stages, write reports, return exit code."""
    parser = argparse.ArgumentParser(description="Testing Agent")
    parser.add_argument("--root", type=Path, default=Path("."), help="Project root")
    parser.add_argument("--config", type=Path, default=Path("config/testing.yaml"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports"))
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
    )

    config = _load_config(args.config)
    agent = TestingAgent(args.root.resolve(), config)
    result = agent.run()

    reporter = TestingReport(result)
    reporter.write_json(args.output_dir / "testing_report.json")
    reporter.write_markdown(args.output_dir / "testing_report.md")

    if result.status == Status.PASS:
        logging.getLogger(__name__).info("Testing Agent PASS — score=%.1f coverage=%.1f%%", result.score, result.coverage)
        return 0
    logging.getLogger(__name__).error("Testing Agent FAIL — score=%.1f coverage=%.1f%%", result.score, result.coverage)
    return 1

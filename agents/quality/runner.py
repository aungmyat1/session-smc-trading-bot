"""Quality Agent runner — CLI wrapper and config loader."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

import yaml

from agents.quality.agent import QualityAgent, Status
from agents.quality.report import QualityReport


def _load_config(path: Path) -> dict[str, Any]:
    if path.exists():
        with open(path) as fh:
            return yaml.safe_load(fh) or {}
    return {}


def run(argv: list[str] | None = None) -> int:
    """Parse CLI args, execute all quality stages, write reports, return exit code."""
    parser = argparse.ArgumentParser(description="Quality Agent")
    parser.add_argument("--root", type=Path, default=Path("."), help="Project root")
    parser.add_argument("--config", type=Path, default=Path("quality/config.yaml"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports"))
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
    )

    config = _load_config(args.config)
    agent = QualityAgent(args.root.resolve(), config)
    result = agent.run()

    reporter = QualityReport(result)
    reporter.write_json(args.output_dir / "quality_report.json")
    reporter.write_markdown(args.output_dir / "quality_report.md")

    log = logging.getLogger(__name__)
    if result.status == Status.PASS:
        log.info(
            "Quality Agent PASS — quality=%.1f security=%.1f arch=%.1f docs=%.1f",
            result.quality_score, result.security_score, result.architecture_score, result.documentation_score,
        )
        return 0
    log.error(
        "Quality Agent FAIL — quality=%.1f security=%.1f arch=%.1f docs=%.1f",
        result.quality_score, result.security_score, result.architecture_score, result.documentation_score,
    )
    return 1

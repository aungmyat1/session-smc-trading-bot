#!/usr/bin/env python3
"""Run the manifest-driven research queue."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from research.research_queue import run_research_queue  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the research queue")
    parser.add_argument(
        "--queue", default="config/research_queue.yaml", help="Queue YAML file"
    )
    parser.add_argument(
        "--output-dir",
        default="reports/research_queue",
        help="Directory for job results and reports",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Validate jobs without running commands"
    )
    args = parser.parse_args()

    results = run_research_queue(
        path=_ROOT / args.queue,
        output_dir=_ROOT / args.output_dir,
        dry_run=args.dry_run,
    )
    print(json.dumps([asdict(result) for result in results], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

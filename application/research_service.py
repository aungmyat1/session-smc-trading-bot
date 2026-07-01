from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from research.research_queue import load_research_queue, run_research_queue

_ROOT = Path(__file__).resolve().parents[1]


def research_queue_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the manifest-driven research queue")
    parser.add_argument("--queue", default="config/research_queue.yaml", help="Queue YAML file")
    parser.add_argument(
        "--output-dir",
        default="reports/research_queue",
        help="Directory for job results and reports",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate jobs without running commands")
    args = parser.parse_args(argv)

    results = run_research_queue(
        path=_ROOT / args.queue,
        output_dir=_ROOT / args.output_dir,
        dry_run=args.dry_run,
    )
    print(json.dumps([asdict(result) for result in results], indent=2, sort_keys=True))
    return 0


def research_status_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize the configured research queue")
    parser.add_argument("--queue", default="config/research_queue.yaml", help="Queue YAML file")
    args = parser.parse_args(argv)

    queue_path = Path(args.queue)
    if not queue_path.is_absolute():
        queue_path = _ROOT / queue_path

    jobs = load_research_queue(queue_path)
    raw_payload: dict[str, Any] = {}
    if queue_path.exists():
        raw_payload = yaml.safe_load(queue_path.read_text(encoding="utf-8")) or {}
    raw_jobs = raw_payload.get("jobs", []) if isinstance(raw_payload, dict) else []
    blocked_steps = sum(1 for job in jobs for step in job.steps if step.blocked)
    enabled_jobs = sum(1 for job in raw_jobs if isinstance(job, dict) and job.get("enabled", True))
    summary = {
        "queue_path": str(queue_path),
        "job_count": len(jobs),
        "enabled_job_count": enabled_jobs,
        "blocked_step_count": blocked_steps,
        "jobs": [
            {
                "job_id": job.job_id,
                "strategy": job.strategy,
                "step_count": len(job.steps),
                "blocked_steps": [step.name for step in job.steps if step.blocked],
            }
            for job in jobs
        ],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0

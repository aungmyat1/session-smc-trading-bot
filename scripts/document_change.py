#!/usr/bin/env python3
"""Record a durable repo/runtime change-control entry.

This command documents both repository changes and the current runtime state,
including the "nothing is running" case.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from svos.shared.change_control import build_change_record, write_change_record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", required=True, help="One-line description of the change or observation")
    parser.add_argument(
        "--change-type",
        default="repo_change",
        choices=["repo_change", "runtime_snapshot", "config_change", "doc_update", "verification"],
    )
    parser.add_argument(
        "--status",
        default="implemented",
        choices=["planned", "implemented", "verified", "observed"],
    )
    parser.add_argument("--actor", default="codex")
    parser.add_argument("--strategy", default="")
    parser.add_argument("--lifecycle-stage", default="")
    parser.add_argument("--affected-file", action="append", default=[])
    parser.add_argument("--verify", action="append", default=[], help="Verification step or command")
    parser.add_argument("--note", action="append", default=[], help="Additional note")
    parser.add_argument("--output-root", default="reports/change_control")
    args = parser.parse_args()

    record = build_change_record(
        root=ROOT,
        actor=args.actor,
        change_type=args.change_type,
        status=args.status,
        summary=args.summary,
        strategy=args.strategy,
        lifecycle_stage=args.lifecycle_stage,
        affected_files=list(args.affected_file),
        verification_steps=list(args.verify),
        notes=list(args.note),
    )
    json_path, md_path = write_change_record(ROOT, record, ROOT / args.output_root)
    print(
        json.dumps(
            {
                "status": "PASS",
                "event_id": record.event_id,
                "strategy": record.strategy,
                "lifecycle_stage": record.lifecycle_stage,
                "json": str(json_path),
                "markdown": str(md_path),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Export a read-only governance/registry snapshot for execution-side audit use.

This script is System-1 (SVOS) tooling: it imports SVOS services freely.
It writes `artifacts/svos/strategy_snapshots.json`, which
`execution/governance_snapshot_provider.py` reads at runtime. Execution never
imports `svos.*` directly — this script is the only bridge, and it is run
manually/out-of-band (no event-driven writer in this task).

Run:
    python scripts/export_governance_snapshot.py [--root ROOT] [--output PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from svos.governance.snapshot import compute_all_governance_snapshots

DEFAULT_OUTPUT = ROOT / "artifacts" / "svos" / "strategy_snapshots.json"


def build_snapshot(root: Path) -> dict:
    """Compute the governance snapshot for every catalog strategy.

    Thin wrapper over the shared `svos.governance.snapshot` computation, kept
    here (rather than inlined) so this script's CLI/file-writing behavior is
    unaffected while the actual computation is reused by
    `svos/deployment/service.py`'s packaged `governance_snapshot.json` builder.
    """

    return compute_all_governance_snapshots(root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Project root (default: repo root)")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output snapshot path (default: artifacts/svos/strategy_snapshots.json)",
    )
    args = parser.parse_args()

    payload = build_snapshot(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote governance snapshot for {len(payload['strategies'])} strategies to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

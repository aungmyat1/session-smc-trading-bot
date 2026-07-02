#!/usr/bin/env python3
"""Compatibility wrapper for the canonical agtrade research queue command."""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from agtrade.research import research_queue_main


def main() -> int:
    warnings.warn(
        "scripts/run_research_queue.py is deprecated; use `agtrade research queue` instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return research_queue_main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())

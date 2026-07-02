#!/usr/bin/env python3
"""Compatibility wrapper for the canonical agtrade strategy SVOS command."""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agtrade.strategy import svos_main


def main() -> int:
    warnings.warn(
        "scripts/svos_run.py is deprecated; use `agtrade strategy svos` instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return svos_main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())

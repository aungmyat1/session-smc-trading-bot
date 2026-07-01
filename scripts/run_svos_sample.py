#!/usr/bin/env python3
"""Compatibility wrapper for the canonical agtrade SVOS sample command."""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agtrade.strategy import sample_main


def main() -> int:
    warnings.warn(
        "scripts/run_svos_sample.py is deprecated; use `agtrade strategy sample` instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return sample_main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())

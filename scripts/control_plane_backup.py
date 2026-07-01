#!/usr/bin/env python3
"""Compatibility wrapper for the canonical agtrade admin backup command."""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agtrade.admin import backup_main, restore_main


def main() -> int:
    warnings.warn(
        "scripts/control_plane_backup.py is deprecated; use `agtrade admin backup|restore` instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    argv = sys.argv[1:]
    if not argv:
        raise SystemExit("usage: control_plane_backup.py {backup|restore} ...")
    command, remaining = argv[0], argv[1:]
    if command == "backup":
        return backup_main(remaining)
    if command == "restore":
        return restore_main(remaining)
    raise SystemExit(f"unknown command: {command}")


if __name__ == "__main__":
    raise SystemExit(main())

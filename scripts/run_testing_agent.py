#!/usr/bin/env python3
"""Entry point for the Testing Agent — executed by CI and local developers."""

import sys
from pathlib import Path

# Ensure project root is on sys.path when running as a script.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from agents.testing.runner import run  # noqa: E402

if __name__ == "__main__":
    sys.exit(run())

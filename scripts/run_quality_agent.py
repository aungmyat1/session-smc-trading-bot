#!/usr/bin/env python3
"""Entry point for the Quality Agent — executed by CI and local developers."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from agents.quality.runner import run

if __name__ == "__main__":
    sys.exit(run())

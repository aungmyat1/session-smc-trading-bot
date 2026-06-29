#!/usr/bin/env python3
"""Neutral entrypoint for the strategy demo runner."""

from __future__ import annotations

import runpy
from pathlib import Path


if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).with_name("run_st_a2_demo.py")), run_name="__main__")

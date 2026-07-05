#!/usr/bin/env python3
"""Run verification commands and save results to a file."""
import subprocess
import sys
import json
from pathlib import Path

ROOT = Path("/home/aungp/session-smc-trading-bot")

results = {}

# 1. db_preflight
r = subprocess.run(
    [sys.executable, str(ROOT / "scripts/db_preflight.py"), "--json"],
    capture_output=True, text=True, timeout=60, cwd=ROOT
)
results["db_preflight"] = {
    "stdout": r.stdout[:3000],
    "stderr": r.stderr[:1000],
    "exit_code": r.returncode,
    "truncated": len(r.stdout) > 3000,
}

# 2. alembic current
r2 = subprocess.run(
    [sys.executable, "-m", "alembic", "current"],
    capture_output=True, text=True, timeout=60, cwd=ROOT,
    env={**{k: v for k, v in subprocess.sys.__dict__.items() if k != "__loader__"}}
)
results["alembic_current"] = {
    "stdout": r2.stdout[:1000],
    "stderr": r2.stderr[:1000],
    "exit_code": r2.returncode,
}

# 3. alembic heads
r3 = subprocess.run(
    [sys.executable, "-m", "alembic", "heads"],
    capture_output=True, text=True, timeout=60, cwd=ROOT,
)
results["alembic_heads"] = {
    "stdout": r3.stdout[:1000],
    "stderr": r3.stderr[:1000],
    "exit_code": r3.returncode,
}

# Write results
output_path = Path("/home/aungp/session-smc-trading-bot/tmp_verify_results.json")
output_path.write_text(json.dumps(results, indent=2))
print(f"Results written to {output_path}")
print(f"File size: {output_path.stat().st_size} bytes")

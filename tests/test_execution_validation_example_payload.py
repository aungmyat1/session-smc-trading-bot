from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_example_execution_payload_runs_ready_for_demo():
    payload = Path("execution_validation/examples/example_execution_payload.json")
    result = subprocess.run(
        [
            "python3",
            "scripts/run_evf.py",
            "--payload",
            str(payload),
            "--strategy",
            "ST-A2",
            "--period",
            "2023-2026",
            "--rules",
            "execution_validation/config/validation_rules.yaml",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "READY FOR DEMO"
    assert report["signal_accuracy"] == 1.0
    assert report["order_accuracy"] == 1.0
    assert report["risk_accuracy"] == 1.0

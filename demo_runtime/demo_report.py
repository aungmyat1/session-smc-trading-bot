from __future__ import annotations

import json
from pathlib import Path

from demo_runtime.demo_health_check import DemoReadinessResult


def write_demo_report(result: DemoReadinessResult, output: Path | str) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path

from __future__ import annotations

from pathlib import Path
from typing import Any

from replay.replay_config import ReplayConfig


class ReplayReport:
    def __init__(self, config: ReplayConfig) -> None:
        self.config = config

    def write(self, summary: dict[str, Any]) -> Path:
        warnings = summary.get("warnings", [])
        warning_text = "\n".join(f"- {warning}" for warning in warnings) or "- None"
        content = f"""# Historical Replay Report

- run_id: `{self.config.run_id}`
- symbol: `{self.config.symbol}`
- timeframe: `{self.config.timeframe}`
- start_time: `{self.config.start_time.isoformat()}`
- end_time: `{self.config.end_time.isoformat()}`
- data_path: `{self.config.data_path}`
- strategy_package_path: `{self.config.strategy_package_path}`
- candles_replayed: `{summary['candles_replayed']}`
- events_emitted: `{summary['events_emitted']}`
- deterministic_replay_hash: `{summary['deterministic_replay_hash']}`
- status: `{summary['status']}`

## Warnings

{warning_text}
"""
        path = self.config.run_dir / "replay_report.md"
        path.write_text(content, encoding="utf-8")
        return path

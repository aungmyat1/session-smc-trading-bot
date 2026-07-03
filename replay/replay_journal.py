from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from replay.replay_events import ReplayEvent


class ReplayJournal:
    def __init__(self, output_dir: Path, run_id: str) -> None:
        self.run_dir = Path(output_dir) / run_id
        self.events_path = self.run_dir / "events.jsonl"
        self.summary_path = self.run_dir / "summary.json"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        if self.events_path.exists() and self.events_path.stat().st_size:
            raise FileExistsError(f"replay journal already exists: {self.events_path}")
        self.events_path.write_text("", encoding="utf-8")
        self.event_count = 0

    def append(self, event: ReplayEvent) -> None:
        with self.events_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event.to_dict(), sort_keys=True, separators=(",", ":")) + "\n")
        self.event_count += 1

    def write_summary(self, summary: dict[str, Any]) -> Path:
        self.summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return self.summary_path

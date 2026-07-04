from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from replay.historical_feed import HistoricalFeed
from replay.replay_clock import ReplayClock
from replay.replay_config import ReplayConfig
from replay.replay_events import ReplayEvent, ReplayEventType
from replay.replay_journal import ReplayJournal
from replay.replay_report import ReplayReport


@dataclass(frozen=True, slots=True)
class ReplayResult:
    status: str
    candles_replayed: int
    events_emitted: int
    deterministic_replay_hash: str


class ReplaySession:
    """System 1 replay coordinator. It deliberately has no execution or broker ports."""

    def __init__(self, config: ReplayConfig) -> None:
        self.config = config
        self.feed = HistoricalFeed(config.data_path)
        bars = list(self.feed.stream_between(config.start_time, config.end_time))
        self._bars = [bar for bar in bars if bar.symbol == config.symbol and bar.timeframe == config.timeframe]
        self.clock = ReplayClock(config.start_time, config.end_time, [bar.timestamp for bar in self._bars])
        self.journal = ReplayJournal(config.output_dir, config.run_id)
        self.report = ReplayReport(config)
        self._sequence = 0
        self._hash_records: list[dict[str, Any]] = []

    @staticmethod
    def _file_digest(path: Path) -> str:
        source = path.read_bytes()
        return hashlib.sha256(source).hexdigest()

    def _emit(self, event_type: ReplayEventType, timestamp: datetime, payload: dict[str, Any]) -> None:
        event = ReplayEvent(self.config.run_id, event_type, timestamp, payload, self._sequence)
        self.journal.append(event)
        stable = event.to_dict()
        stable.pop("run_id")
        self._hash_records.append(stable)
        self._sequence += 1

    def _replay_hash(self) -> str:
        identity = {
            "symbol": self.config.symbol,
            "timeframe": self.config.timeframe,
            "start_time": self.config.start_time.isoformat(),
            "end_time": self.config.end_time.isoformat(),
            "data_sha256": self._file_digest(self.config.data_path),
            "strategy_package_sha256": self._file_digest(self.config.strategy_package_path),
            "events": self._hash_records,
        }
        encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    def run(self) -> ReplayResult:
        warnings = ["Strategy execution is not connected in ADR-0010; only market bars are emitted."]
        try:
            self._emit(ReplayEventType.REPLAY_STARTED, self.config.start_time, {"strategy_execution": "not_connected"})
            if not self._bars:
                raise ValueError("No candles matched the requested symbol, timeframe, and replay window.")
            for bar in self._bars:
                current = self.clock.step()
                if current != bar.timestamp:
                    raise RuntimeError("replay clock and feed are not aligned")
                self._emit(ReplayEventType.MARKET_BAR_EMITTED, current, bar.to_dict())
            self._emit(
                ReplayEventType.REPLAY_FINISHED,
                self.clock.current_time if self._bars else self.config.end_time,
                {"candles_replayed": len(self._bars), "status": "pass"},
            )
            status = "pass"
        except Exception as exc:
            self._emit(ReplayEventType.REPLAY_FAILED, self.clock.current_time, {"error": str(exc)})
            status = "fail"
            warnings.append(str(exc))
        digest = self._replay_hash()
        summary = {
            "run_id": self.config.run_id,
            "status": status,
            "candles_replayed": len(self._bars),
            "events_emitted": self.journal.event_count,
            "deterministic_replay_hash": digest,
            "data_path": str(self.config.data_path),
            "data_sha256": self._file_digest(self.config.data_path),
            "strategy_package_path": str(self.config.strategy_package_path),
            "strategy_package_sha256": self._file_digest(self.config.strategy_package_path),
            "warnings": warnings,
        }
        self.journal.write_summary(summary)
        self.report.write(summary)
        return ReplayResult(status, len(self._bars), self.journal.event_count, digest)

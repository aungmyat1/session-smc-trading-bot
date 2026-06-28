"""
Structured JSON logger for the trading bot.

Writes JSON lines to logs/bot.jsonl (and optionally to stderr).
Each log line is a self-contained JSON object with timestamp, level,
strategy_id, message, and optional context fields.

Usage::
    log = get_structured_logger("ST-A2")
    log.info("signal_fired", symbol="EURUSD", direction="LONG", entry=1.085)
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_UTC = timezone.utc
_DEFAULT_LOG_DIR = Path("logs")
_DEFAULT_LOG_FILE = _DEFAULT_LOG_DIR / "bot.jsonl"


class StructuredLogger:
    """JSON-line logger scoped to a strategy."""

    def __init__(
        self,
        strategy_id: str,
        log_file: Path = _DEFAULT_LOG_FILE,
        also_stderr: bool = True,
        stderr_level: int = logging.INFO,
    ) -> None:
        self.strategy_id = strategy_id
        self._log_file = log_file
        self._also_stderr = also_stderr
        self._stderr_level_int = stderr_level
        log_file.parent.mkdir(parents=True, exist_ok=True)

    def _write(self, level: str, event: str, **ctx: Any) -> None:
        record = {
            "ts": datetime.now(_UTC).isoformat(),
            "level": level,
            "strategy_id": self.strategy_id,
            "event": event,
            **ctx,
        }
        line = json.dumps(record, default=str)
        try:
            with self._log_file.open("a") as fh:
                fh.write(line + "\n")
        except OSError:
            pass  # Never let logging crash the bot

        if self._also_stderr:
            lvl_map = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
            if lvl_map.get(level, 0) >= self._stderr_level_int:
                print(f"[{record['ts']}] {level} [{self.strategy_id}] {event}", file=sys.stderr)

    def debug(self, event: str, **ctx: Any) -> None:
        self._write("DEBUG", event, **ctx)

    def info(self, event: str, **ctx: Any) -> None:
        self._write("INFO", event, **ctx)

    def warning(self, event: str, **ctx: Any) -> None:
        self._write("WARNING", event, **ctx)

    def error(self, event: str, **ctx: Any) -> None:
        self._write("ERROR", event, **ctx)

    def critical(self, event: str, **ctx: Any) -> None:
        self._write("CRITICAL", event, **ctx)


def get_structured_logger(strategy_id: str, **kwargs: Any) -> StructuredLogger:
    """Factory function — returns a StructuredLogger for the given strategy."""
    return StructuredLogger(strategy_id=strategy_id, **kwargs)

"""
Shadow Tracker — record signals from unvalidated strategies without execution.

New strategies run in SIGNAL_ONLY mode:
  - Signal is generated and recorded
  - No order is placed
  - Hypothetical P/L is tracked for validation purposes

Journal path: logs/shadow_trades.jsonl
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from core.signal import Signal

_log = logging.getLogger("portfolio.shadow")
_DEFAULT_PATH = Path("logs") / "shadow_trades.jsonl"


class ShadowTracker:
    def __init__(self, path: Path | str | None = None) -> None:
        self._path = Path(path) if path else _DEFAULT_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def track(self, signal: Signal, reason: str = "shadow_mode") -> None:
        """
        Record signal without executing. Always returns None to execution layer.
        """
        record = {
            "type":          "SHADOW_SIGNAL",
            "timestamp":     datetime.now(timezone.utc).isoformat(),
            "strategy_name": signal.strategy_name,
            "symbol":        signal.symbol,
            "action":        signal.action,
            "entry_price":   signal.entry_price,
            "stop_loss":     signal.stop_loss,
            "take_profit":   signal.take_profit,
            "confidence":    signal.confidence,
            "risk_percent":  signal.risk_percent,
            "session":       signal.session,
            "reason":        reason,
            "metadata":      signal.metadata,
            "executed":      False,
        }
        try:
            with self._path.open("a") as fh:
                fh.write(json.dumps(record) + "\n")
        except OSError as exc:
            _log.error("Shadow journal write failed: %s", exc)

    def read_all(self) -> list[dict]:
        if not self._path.exists():
            return []
        records = []
        with self._path.open() as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return records

    def summary(self) -> dict:
        records = self.read_all()
        by_strategy: dict[str, int] = {}
        for r in records:
            name = r.get("strategy_name", "unknown")
            by_strategy[name] = by_strategy.get(name, 0) + 1
        return {
            "total_shadow_signals": len(records),
            "by_strategy":          by_strategy,
        }

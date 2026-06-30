"""
S5 — Trade Journal.

Appends closed trade records to logs/adaptive_trades.jsonl (one JSON per line).
Also appends signal records when a signal is routed.

Public API:
    TradeJournal(path)
        .log_signal(signal, router_result)
        .log_trade(closed_trade_dict)
        .read_all() -> list[dict]
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from adaptive.strategies import AdaptiveSignal

_DEFAULT_PATH = Path("logs/adaptive_trades.jsonl")
_logger = logging.getLogger("adaptive.journal")


class TradeJournal:
    def __init__(self, path: Path | str = _DEFAULT_PATH) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _append(self, record: dict) -> None:
        try:
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, default=str) + "\n")
        except OSError as exc:
            _logger.error("Journal write failed: %s", exc)

    def log_signal(self, signal: AdaptiveSignal, router_result: dict) -> None:
        """Record a routing decision (APPROVED or REJECTED)."""
        record = {
            "record_type": "signal",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": signal.pair,
            "strategy": signal.strategy,
            "direction": signal.direction,
            "entry": signal.entry_price,
            "sl": signal.sl_price,
            "tp": signal.tp_price,
            "session": signal.session,
            "score": router_result.get("score_result", {}).get("score", -1),
            "regime": router_result.get("regime", {}).get("regime", ""),
            "decision": router_result.get("decision", ""),
            "reason": router_result.get("rejection_reason", ""),
        }
        self._append(record)

    def log_trade(self, trade: dict) -> None:
        """Record a closed paper trade."""
        record = {
            "record_type": "trade",
            "timestamp": trade.get("closed_at", datetime.now(timezone.utc).isoformat()),
            "symbol": trade.get("pair", ""),
            "strategy": trade.get("strategy", ""),
            "direction": trade.get("direction", ""),
            "entry": trade.get("entry", 0.0),
            "sl": trade.get("sl", 0.0),
            "tp": trade.get("tp", 0.0),
            "result": trade.get("status", ""),
            "r_multiple": trade.get("pnl_r", 0.0),
        }
        self._append(record)

    def read_all(self) -> list[dict]:
        """Return all journal records (for reporting / restart recovery)."""
        if not self._path.exists():
            return []
        records = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return records

"""
Strategy Demo Trade Journal.

Appends records to logs/strategy_demo_trades.jsonl by default.
Isolated from execution/trade_logger.py (live bot logger).

Public API:
    DemoTradeJournal(path)
        .log_open(signal, order_result, lots, spread)
        .log_close(position_id, exit_price, result_r)
        .read_all() -> list[dict]
        .summary() -> dict
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT = Path("logs/strategy_demo_trades.jsonl")
_log = logging.getLogger("strategy_demo.journal")


class DemoTradeJournal:
    def __init__(self, path: Path | str = _DEFAULT) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _append(self, record: dict) -> None:
        try:
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, default=str) + "\n")
        except OSError as exc:
            _log.error("Journal write failed: %s", exc)

    def log_open(
        self,
        signal,
        order_result: dict,
        lots: float,
        spread: float,
        session: str = "",
    ) -> None:
        """Record a new trade open."""
        symbol = getattr(signal, "pair", None) or signal.get("symbol", "")
        direction = getattr(signal, "side", None) or signal.get("direction", "")
        entry = getattr(signal, "entry", None) or signal.get("entry", 0.0)
        sl = getattr(signal, "stop_loss", None) or signal.get("stop_loss", 0.0)
        tp = getattr(signal, "take_profit", None) or signal.get("take_profit", 0.0)
        sess = getattr(signal, "session", None) or session

        record = {
            "record_type": "open",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "direction": direction,
            "entry": entry,
            "stop_loss": sl,
            "take_profit": tp,
            "lot_size": lots,
            "spread": spread,
            "session": sess,
            "strategy": getattr(signal, "strategy_name", None) or "",
            "order_id": order_result.get("order_id", ""),
            "simulated": order_result.get("simulated", True),
            "exit": None,
            "result_R": None,
        }
        self._append(record)

    def log_close(
        self,
        position_id: str,
        exit_price: float,
        result_r: float,
        status: str = "closed",
    ) -> None:
        """Record a trade close."""
        record = {
            "record_type": "close",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "position_id": position_id,
            "exit": exit_price,
            "result_R": round(result_r, 3),
            "status": status,
        }
        self._append(record)

    def read_all(self) -> list[dict]:
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

    def summary(self) -> dict:
        """Quick stats over all closed trades."""
        records = self.read_all()
        opens = [r for r in records if r.get("record_type") == "open"]
        closes = [
            r
            for r in records
            if r.get("record_type") == "close" and r.get("result_R") is not None
        ]
        wins = [r for r in closes if r["result_R"] > 0]
        losses = [r for r in closes if r["result_R"] < 0]
        return {
            "total_opened": len(opens),
            "total_closed": len(closes),
            "wins": len(wins),
            "losses": len(losses),
            "avg_r": (
                round(sum(r["result_R"] for r in closes) / len(closes), 3)
                if closes
                else 0.0
            ),
        }

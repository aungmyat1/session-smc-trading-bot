"""
Trade journal — append-only JSON-lines log at logs/trades.jsonl.

Each line is one closed trade. Stats are computed on-demand from the log.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

JOURNAL_FILE = Path("logs/trades.jsonl")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TradeJournal:
    def __init__(self, path: Path = JOURNAL_FILE):
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def log_trade(
        self,
        symbol: str,
        direction: str,
        entry: float,
        sl: float,
        tp: float,
        risk_pct: float,
        lot: float,
        result_r: Optional[float] = None,
        exit_price: Optional[float] = None,
        reason: str = "",
        session: str = "",
        dry_run: bool = False,
    ) -> None:
        record = {
            "timestamp": _now_iso(),
            "symbol": symbol,
            "direction": direction,
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "risk_pct": risk_pct,
            "lot": lot,
            "result_r": result_r,
            "exit_price": exit_price,
            "reason": reason,
            "session": session,
            "dry_run": dry_run,
        }
        with self._path.open("a") as f:
            f.write(json.dumps(record) + "\n")
        logger.info(
            "Trade logged: %s %s r=%.2f dry=%s",
            direction.upper(),
            symbol,
            result_r or 0.0,
            dry_run,
        )

    def get_all_trades(self) -> list[dict]:
        if not self._path.exists():
            return []
        trades = []
        with self._path.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        trades.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return trades

    def get_daily_stats(self, date_str: Optional[str] = None) -> dict:
        """Compute stats for a given date (YYYY-MM-DD). Defaults to today UTC."""
        date_str = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        trades = [
            t
            for t in self.get_all_trades()
            if t.get("timestamp", "").startswith(date_str)
        ]
        return self._compute_stats(trades)

    def get_all_stats(self) -> dict:
        return self._compute_stats(self.get_all_trades())

    def _compute_stats(self, trades: list[dict]) -> dict:
        closed = [t for t in trades if t.get("result_r") is not None]
        if not closed:
            return {
                "trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "total_r": 0.0,
                "avg_r": 0.0,
            }

        wins = [t for t in closed if t["result_r"] >= 0]
        losses = [t for t in closed if t["result_r"] < 0]
        total_r = sum(t["result_r"] for t in closed)
        return {
            "trades": len(closed),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / len(closed) * 100, 1),
            "total_r": round(total_r, 2),
            "avg_r": round(total_r / len(closed), 2),
        }

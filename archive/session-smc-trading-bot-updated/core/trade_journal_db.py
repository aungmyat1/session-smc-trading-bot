"""
Persistent SQLite trade journal — all pipeline stages recorded per trade.

Database: data/trade_journal.db
Table:    trades

Schema captures every field from signal generation through execution result,
allowing post-hoc analysis of router/breaker/portfolio decisions alongside
execution quality and trade outcome.

Public API:
    TradeJournalDB(path)
        .record_signal(signal, router_result, breaker_result,
                       portfolio_result, execution_result, ...) -> int (trade_id)
        .update_close(trade_id, close_price, profit_loss, r_multiple,
                      reason_for_exit) -> None
        .get_trade(trade_id) -> dict | None
        .get_open_trades() -> list[dict]
        .get_all_trades() -> list[dict]
        .summary() -> dict
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from core.signal import Signal

_log = logging.getLogger("journal.db")

_DEFAULT_PATH = Path("data") / "trade_journal.db"

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS trades (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp         TEXT    NOT NULL,
    strategy_name     TEXT,
    symbol            TEXT,
    direction         TEXT,
    signal_price      REAL,
    entry_price       REAL,
    stop_loss         REAL,
    take_profit       REAL,
    position_size     REAL,
    risk_percentage   REAL,
    router_result     TEXT,
    breaker_result    TEXT,
    portfolio_result  TEXT,
    execution_result  TEXT,
    broker_order_id   TEXT,
    close_price       REAL,
    profit_loss       REAL,
    r_multiple        REAL,
    reason_for_exit   TEXT,
    status            TEXT    DEFAULT 'OPEN',
    session           TEXT,
    confidence        REAL,
    ttl_seconds       INTEGER,
    metadata          TEXT
);

CREATE INDEX IF NOT EXISTS idx_trades_symbol  ON trades (symbol);
CREATE INDEX IF NOT EXISTS idx_trades_status  ON trades (status);
CREATE INDEX IF NOT EXISTS idx_trades_ts      ON trades (timestamp);
"""


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


class TradeJournalDB:
    def __init__(self, path: Path | str | None = None) -> None:
        self._path = Path(path) if path else _DEFAULT_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_CREATE_SQL)

    # ── Write ──────────────────────────────────────────────────────────────

    def record_signal(
        self,
        signal: Signal,
        router_result:    str = "",
        breaker_result:   str = "",
        portfolio_result: str = "",
        execution_result: str = "",
        broker_order_id:  str = "",
        position_size:    float = 0.0,
    ) -> int:
        """
        Insert a trade record at signal time. Returns the new row id.
        Call update_close() when the trade closes.
        """
        import json

        direction = "long" if signal.action == "BUY" else \
                    "short" if signal.action == "SELL" else signal.action.lower()

        row = (
            datetime.now(timezone.utc).isoformat(),
            signal.strategy_name,
            signal.symbol,
            direction,
            signal.entry_price,    # signal_price (at generation time)
            signal.entry_price,    # entry_price (filled price updated on close)
            signal.stop_loss,
            signal.take_profit,
            position_size,
            signal.risk_percent,
            router_result,
            breaker_result,
            portfolio_result,
            execution_result,
            broker_order_id,
            None,  # close_price
            None,  # profit_loss
            None,  # r_multiple
            None,  # reason_for_exit
            "OPEN" if execution_result in ("OPEN", "SHADOW") else "BLOCKED",
            signal.session,
            signal.confidence,
            signal.ttl_seconds,
            json.dumps(signal.metadata),
        )

        sql = """
        INSERT INTO trades (
            timestamp, strategy_name, symbol, direction,
            signal_price, entry_price, stop_loss, take_profit,
            position_size, risk_percentage,
            router_result, breaker_result, portfolio_result, execution_result,
            broker_order_id, close_price, profit_loss, r_multiple, reason_for_exit,
            status, session, confidence, ttl_seconds, metadata
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """
        try:
            with self._connect() as conn:
                cur = conn.execute(sql, row)
                return cur.lastrowid or 0
        except sqlite3.Error as exc:
            _log.error("Journal DB write failed: %s", exc)
            return 0

    def update_close(
        self,
        trade_id:       int,
        close_price:    float,
        profit_loss:    float,
        r_multiple:     float,
        reason_for_exit: str = "tp_hit",
        entry_price:    Optional[float] = None,
    ) -> None:
        """Mark a trade closed with its outcome."""
        fields = {
            "close_price":     close_price,
            "profit_loss":     profit_loss,
            "r_multiple":      round(r_multiple, 3),
            "reason_for_exit": reason_for_exit,
            "status":          "CLOSED",
        }
        if entry_price is not None:
            fields["entry_price"] = entry_price

        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [trade_id]

        try:
            with self._connect() as conn:
                conn.execute(f"UPDATE trades SET {set_clause} WHERE id = ?", values)
        except sqlite3.Error as exc:
            _log.error("Journal DB update failed id=%s: %s", trade_id, exc)

    # ── Read ───────────────────────────────────────────────────────────────

    def get_trade(self, trade_id: int) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM trades WHERE id = ?", (trade_id,)
            ).fetchone()
        return _row_to_dict(row) if row else None

    def get_open_trades(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM trades WHERE status = 'OPEN' ORDER BY timestamp"
            ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def get_all_trades(self, limit: int = 500) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def get_trades_by_symbol(self, symbol: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM trades WHERE symbol = ? ORDER BY timestamp",
                (symbol,),
            ).fetchall()
        return [_row_to_dict(r) for r in rows]

    # ── Analytics ──────────────────────────────────────────────────────────

    def summary(self) -> dict:
        with self._connect() as conn:
            total  = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
            open_  = conn.execute(
                "SELECT COUNT(*) FROM trades WHERE status='OPEN'"
            ).fetchone()[0]
            closed = conn.execute(
                "SELECT COUNT(*) FROM trades WHERE status='CLOSED'"
            ).fetchone()[0]
            blocked = conn.execute(
                "SELECT COUNT(*) FROM trades WHERE status='BLOCKED'"
            ).fetchone()[0]

            row = conn.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE r_multiple > 0) AS wins,
                    COUNT(*) FILTER (WHERE r_multiple < 0) AS losses,
                    AVG(r_multiple)                         AS avg_r,
                    SUM(profit_loss)                        AS total_pnl
                FROM trades WHERE status='CLOSED'
            """).fetchone()

            wins       = row["wins"]   or 0
            losses     = row["losses"] or 0
            avg_r      = round(row["avg_r"] or 0.0, 3)
            total_pnl  = round(row["total_pnl"] or 0.0, 2)

        win_rate    = round(wins / (wins + losses) * 100, 1) if (wins + losses) else 0.0
        gross_wins  = self._sum_r(closed=True, side="win")
        gross_losses = abs(self._sum_r(closed=True, side="loss"))
        pf = round(gross_wins / gross_losses, 3) if gross_losses > 0 else 0.0

        return {
            "total":       total,
            "open":        open_,
            "closed":      closed,
            "blocked":     blocked,
            "wins":        wins,
            "losses":      losses,
            "win_rate_pct":win_rate,
            "avg_r":       avg_r,
            "profit_factor": pf,
            "total_pnl":   total_pnl,
        }

    def _sum_r(self, closed: bool, side: str) -> float:
        cond = "r_multiple > 0" if side == "win" else "r_multiple < 0"
        with self._connect() as conn:
            val = conn.execute(
                f"SELECT SUM(r_multiple) FROM trades WHERE status='CLOSED' AND {cond}"
            ).fetchone()[0]
        return val or 0.0

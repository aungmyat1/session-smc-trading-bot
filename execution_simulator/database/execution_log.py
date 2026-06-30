from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ExecutionLog:
    """SQLite-backed execution audit for replay runs."""

    def __init__(
        self, path: str | Path = "execution_validation/execution_validation.sqlite3"
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    requested_price REAL,
                    filled_price REAL,
                    slippage REAL,
                    latency_ms INTEGER,
                    status TEXT NOT NULL,
                    reason TEXT
                );

                CREATE TABLE IF NOT EXISTS positions (
                    position_id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    profit REAL,
                    duration_seconds REAL,
                    exit_reason TEXT
                );

                CREATE TABLE IF NOT EXISTS fills (
                    fill_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT NOT NULL,
                    execution_time TEXT NOT NULL,
                    slippage REAL,
                    latency_ms INTEGER,
                    requested_price REAL,
                    filled_price REAL,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS signal_comparison (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    expected_direction TEXT,
                    actual_direction TEXT,
                    expected_entry REAL,
                    actual_entry REAL,
                    slippage REAL,
                    latency_ms INTEGER,
                    verdict TEXT
                );
                """)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def log_order(
        self,
        *,
        order_id: str,
        symbol: str,
        direction: str,
        requested_price: float | None,
        filled_price: float | None,
        slippage: float,
        latency_ms: int,
        status: str,
        reason: str = "",
        timestamp: str | None = None,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO orders
                (order_id, timestamp, symbol, direction, requested_price, filled_price, slippage, latency_ms, status, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    timestamp or self._now(),
                    symbol,
                    direction,
                    requested_price,
                    filled_price,
                    slippage,
                    latency_ms,
                    status,
                    reason,
                ),
            )

    def log_position(
        self,
        *,
        position_id: str,
        order_id: str,
        symbol: str,
        direction: str,
        entry_price: float,
        exit_price: float | None,
        profit: float | None,
        duration_seconds: float | None,
        exit_reason: str,
        timestamp: str | None = None,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO positions
                (position_id, order_id, timestamp, symbol, direction, entry_price, exit_price, profit, duration_seconds, exit_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    position_id,
                    order_id,
                    timestamp or self._now(),
                    symbol,
                    direction,
                    entry_price,
                    exit_price,
                    profit,
                    duration_seconds,
                    exit_reason,
                ),
            )

    def log_fill(
        self,
        *,
        order_id: str,
        symbol: str,
        direction: str,
        execution_time: str | None = None,
        slippage: float | None,
        latency_ms: int | None,
        requested_price: float | None,
        filled_price: float | None,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO fills
                (order_id, execution_time, slippage, latency_ms, requested_price, filled_price, symbol, direction)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    execution_time or self._now(),
                    slippage,
                    latency_ms,
                    requested_price,
                    filled_price,
                    symbol,
                    direction,
                ),
            )

    def log_signal_comparison(
        self,
        *,
        symbol: str,
        expected_direction: str | None,
        actual_direction: str | None,
        expected_entry: float | None,
        actual_entry: float | None,
        slippage: float | None,
        latency_ms: int | None,
        verdict: str,
        timestamp: str | None = None,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO signal_comparison
                (timestamp, symbol, expected_direction, actual_direction, expected_entry, actual_entry, slippage, latency_ms, verdict)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timestamp or self._now(),
                    symbol,
                    expected_direction,
                    actual_direction,
                    expected_entry,
                    actual_entry,
                    slippage,
                    latency_ms,
                    verdict,
                ),
            )

    def fetch(self, table: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
        return [dict(row) for row in rows]

    def summary(self) -> dict[str, int]:
        with self._conn() as conn:
            orders = conn.execute("SELECT COUNT(*) AS n FROM orders").fetchone()["n"]
            positions = conn.execute("SELECT COUNT(*) AS n FROM positions").fetchone()[
                "n"
            ]
            fills = conn.execute("SELECT COUNT(*) AS n FROM fills").fetchone()["n"]
            comparisons = conn.execute(
                "SELECT COUNT(*) AS n FROM signal_comparison"
            ).fetchone()["n"]
        return {
            "orders": orders,
            "positions": positions,
            "fills": fills,
            "signal_comparison": comparisons,
        }

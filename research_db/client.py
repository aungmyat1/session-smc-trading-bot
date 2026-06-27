"""
Research database client.

Synchronous psycopg2 wrapper for replay/backtest integration.
Reads DATABASE_URL from environment or falls back to direct params.

Public API:
    ResearchDB(dsn=None)
        .save_run(run) -> run_id str
        .save_trade(trade) -> int (trade_id)
        .save_smc_event(event) -> int
        .save_daily_equity(row) -> None
        .save_strategy_metrics(metrics) -> None
        .update_run_summary(run_id, metrics) -> None
        .close() -> None

All methods are safe to call when DB is unavailable — they log and return
a null value so the replay continues without crashing.
"""

from __future__ import annotations

import logging
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
import re
from typing import Optional

import psycopg2
import psycopg2.extras

from research.lineage import build_lineage_metadata

log = logging.getLogger("research_db")


def _dsn_from_env() -> str | None:
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if url.startswith("postgresql://"):
        return url
    return None


class ResearchDB:
    def __init__(self, dsn: Optional[str] = None) -> None:
        self._dsn = dsn or _dsn_from_env()
        self._conn: Optional[psycopg2.extensions.connection] = None
        self._available = False
        self._connect()

    def _connect(self) -> None:
        if not self._dsn:
            log.warning("ResearchDB unavailable: DATABASE_URL not configured")
            self._available = False
            return
        try:
            self._conn = psycopg2.connect(self._dsn)
            self._conn.autocommit = False
            self._available = True
            log.info("ResearchDB connected to %s", self._dsn.split("@")[-1])
        except psycopg2.Error as e:
            log.warning("ResearchDB unavailable: %s — replay will continue without DB", e)
            self._available = False

    def _strategy_name_version(self, run: dict) -> tuple[str, str]:
        raw_name = str(run.get("strategy_name") or run.get("strategy") or "ST-A2").strip()
        raw_version = str(run.get("strategy_version") or run.get("version") or "").strip()
        if raw_version:
            return raw_name, raw_version
        match = re.search(r"v?(\d+(?:\.\d+)*)$", raw_name, flags=re.IGNORECASE)
        if match:
            version = match.group(1)
            name = raw_name[: match.start()].strip(" -_") or raw_name
            return name, version
        return raw_name, "1.0"

    def _ensure_strategy(self, cur, *, name: str, version: str, description: str = "", status: str = "active") -> int | None:
        cur.execute(
            """
            INSERT INTO research.strategies (strategy_name, version, description, rules_json, status)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (strategy_name, version) DO UPDATE SET
                description = EXCLUDED.description,
                status = EXCLUDED.status
            RETURNING id
            """,
            (
                name,
                version,
                description,
                psycopg2.extras.Json(
                    build_lineage_metadata(
                        source="research_db.client",
                        strategy=name,
                        strategy_version=version,
                        artifact="strategy",
                        extra={"status": status},
                    )
                ),
                status,
            ),
        )
        row = cur.fetchone()
        if row:
            return row["id"]
        cur.execute(
            "SELECT id FROM research.strategies WHERE strategy_name = %s AND version = %s",
            (name, version),
        )
        fetched = cur.fetchone()
        return fetched["id"] if fetched else None

    @contextmanager
    def _cursor(self):
        if not self._available or self._conn is None:
            yield None
            return
        try:
            with self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                yield cur
            self._conn.commit()
        except psycopg2.Error as e:
            log.error("DB error: %s", e)
            try:
                self._conn.rollback()
            except Exception:
                pass
            yield None

    def close(self) -> None:
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass

    # ── replay_runs ───────────────────────────────────────────────────────

    def save_run(self, run: dict) -> str:
        run_id = run.get("run_id") or f"run_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:6]}"
        with self._cursor() as cur:
            if cur is None:
                return run_id
            strategy_name, strategy_version = self._strategy_name_version(run)
            strategy_id = self._ensure_strategy(
                cur,
                name=strategy_name,
                version=strategy_version,
                description=str(run.get("notes", ""))[:2000],
                status=str(run.get("status", "active")),
            )
            cur.execute("""
                INSERT INTO research.replay_runs
                    (run_id, strategy_id, symbol, start_date, end_date, scenario, data_source)
                VALUES (%(run_id)s, %(strategy_id)s, %(symbol)s, %(start_date)s, %(end_date)s,
                        %(scenario)s, %(data_source)s)
                ON CONFLICT (run_id) DO UPDATE SET
                    strategy_id = EXCLUDED.strategy_id,
                    symbol = EXCLUDED.symbol,
                    start_date = EXCLUDED.start_date,
                    end_date = EXCLUDED.end_date,
                    scenario = EXCLUDED.scenario,
                    data_source = EXCLUDED.data_source
            """, {
                "run_id":        run_id,
                "strategy_id":   strategy_id,
                "symbol":        run.get("symbol", "EURUSD"),
                "start_date":    run.get("start_date"),
                "end_date":      run.get("end_date"),
                "data_source":   run.get("data_source", "csv"),
                "scenario":      run.get("scenario", "standard"),
            })
        return run_id

    def update_run_summary(self, run_id: str, metrics: dict) -> None:
        with self._cursor() as cur:
            if cur is None:
                return
            cur.execute("""
                UPDATE research.replay_runs SET
                    scenario = COALESCE(%(scenario)s, scenario),
                    data_source = COALESCE(%(data_source)s, data_source)
                WHERE run_id = %(run_id)s
            """, {
                "run_id": run_id,
                "scenario": metrics.get("scenario"),
                "data_source": metrics.get("data_source"),
            })

    # ── trades ────────────────────────────────────────────────────────────

    def save_trade(self, trade: dict) -> int:
        with self._cursor() as cur:
            if cur is None:
                return 0
            strategy_name, strategy_version = self._strategy_name_version(trade)
            strategy_id = trade.get("strategy_id")
            if strategy_id is None:
                strategy_id = self._ensure_strategy(
                    cur,
                    name=strategy_name,
                    version=strategy_version,
                    description=str(trade.get("notes", ""))[:2000],
                    status=str(trade.get("status", "active")),
                )
            trade_id = trade.get("trade_id") or f"{trade.get('run_id', 'run')}_{trade.get('symbol', 'SYM')}_{trade.get('entry_time', datetime.now(timezone.utc).isoformat())}_{uuid.uuid4().hex[:8]}"
            spread_cost = trade.get("spread_cost_pips", trade.get("spread_pip", 0.0))
            cost_in_r = trade.get("cost_in_r")
            if cost_in_r is None:
                sl_pips = float(trade.get("sl_pips", 0.0) or 0.0)
                cost_in_r = float(spread_cost or 0.0) / sl_pips if sl_pips > 0 else 0.0
            gross_r = trade.get("gross_result_r", trade.get("gross_r", trade.get("result_r", 0.0)))
            net_r = trade.get("net_result_r", trade.get("result_r", 0.0))
            tp1_hit = trade.get("tp1_hit")
            if tp1_hit is None:
                tp1_hit = bool(trade.get("result_r_2x") is not None and float(trade.get("result_r_2x", 0.0)) != float(net_r))
            cur.execute("""
                INSERT INTO research.trades
                    (trade_id, run_id, strategy_id, symbol, session, direction,
                     setup_type, entry_time, exit_time, entry_price, stop_price,
                     take_profit, tp2_price, sl_pips, risk_reward, spread_cost_pips,
                     cost_in_r, gross_result_r, net_result_r, exit_reason, tp1_hit,
                     session_high, session_low, session_range_pips)
                VALUES
                    (%(trade_id)s, %(run_id)s, %(strategy_id)s, %(symbol)s, %(session)s,
                     %(direction)s, %(setup_type)s, %(entry_time)s, %(exit_time)s,
                     %(entry_price)s, %(stop_price)s, %(take_profit)s, %(tp2_price)s,
                     %(sl_pips)s, %(risk_reward)s, %(spread_cost_pips)s, %(cost_in_r)s,
                     %(gross_result_r)s, %(net_result_r)s, %(exit_reason)s, %(tp1_hit)s,
                     %(session_high)s, %(session_low)s, %(session_range_pips)s)
                ON CONFLICT (trade_id) DO UPDATE SET
                    run_id = EXCLUDED.run_id,
                    strategy_id = EXCLUDED.strategy_id,
                    exit_time = EXCLUDED.exit_time,
                    exit_reason = EXCLUDED.exit_reason,
                    net_result_r = EXCLUDED.net_result_r,
                    gross_result_r = EXCLUDED.gross_result_r
                RETURNING id
            """, {
                "trade_id": trade_id,
                "run_id": trade.get("run_id"),
                "strategy_id": strategy_id,
                "symbol": trade.get("symbol"),
                "session": trade.get("session"),
                "direction": trade.get("direction"),
                "setup_type": trade.get("setup_type", "A"),
                "entry_time": trade.get("entry_time"),
                "exit_time": trade.get("exit_time"),
                "entry_price": trade.get("entry_price"),
                "stop_price": trade.get("stop_price", trade.get("stop_loss")),
                "take_profit": trade.get("take_profit"),
                "tp2_price": trade.get("tp2_price"),
                "sl_pips": trade.get("sl_pips"),
                "risk_reward": trade.get("risk_reward", trade.get("rr")),
                "spread_cost_pips": spread_cost,
                "cost_in_r": cost_in_r,
                "gross_result_r": gross_r,
                "net_result_r": net_r,
                "exit_reason": trade.get("exit_reason"),
                "tp1_hit": tp1_hit,
                "session_high": trade.get("session_high"),
                "session_low": trade.get("session_low"),
                "session_range_pips": trade.get("session_range_pips"),
            })
            row = cur.fetchone()
            return row["id"] if row else 0

    # ── smc_events ────────────────────────────────────────────────────────

    def save_smc_event(self, event: dict) -> int:
        with self._cursor() as cur:
            if cur is None:
                return 0
            metadata = {
                k: v
                for k, v in event.items()
                if k not in {"run_id", "symbol", "event_type", "timeframe", "event_time", "direction", "price_level", "price_high", "price_low", "htf_bias", "session", "detail", "lineage"}
            }
            event_price = event.get("event_price", event.get("price_level", event.get("price_high", event.get("price_low"))))
            strength = event.get("strength_score")
            cur.execute("""
                INSERT INTO market.smc_events
                    (symbol, timeframe, timestamp, event_type, event_price, strength_score, metadata_json)
                VALUES
                    (%(symbol)s, %(timeframe)s, %(timestamp)s, %(event_type)s, %(event_price)s,
                     %(strength_score)s, %(metadata_json)s)
                RETURNING id
            """, {
                "symbol": event.get("symbol"),
                "timeframe": event.get("timeframe"),
                "timestamp": event.get("timestamp") or event.get("event_time"),
                "event_type": event.get("event_type"),
                "event_price": event_price,
                "strength_score": strength,
                "metadata_json": psycopg2.extras.Json({
                    "run_id": event.get("run_id"),
                    "direction": event.get("direction"),
                    "price_high": event.get("price_high"),
                    "price_low": event.get("price_low"),
                    "htf_bias": event.get("htf_bias"),
                    "session": event.get("session"),
                    "detail": event.get("detail"),
                    **metadata,
                    "lineage": build_lineage_metadata(
                        source="research_db.client",
                        strategy=str(event.get("strategy", "unknown")),
                        strategy_version=str(event.get("strategy_version", "unknown")),
                        artifact="smc_event",
                    ),
                }),
            })
            row = cur.fetchone()
            return row["id"] if row else 0

    # ── daily_equity ──────────────────────────────────────────────────────

    def save_daily_equity(self, row: dict) -> None:
        with self._cursor() as cur:
            if cur is None:
                return
            date_value = row.get("date", row.get("trade_date"))
            daily_r = row.get("daily_r", row.get("daily_return_r"))
            equity_r = row.get("equity_r", row.get("cumulative_r"))
            drawdown = row.get("drawdown")
            cur.execute("""
                INSERT INTO analytics.daily_equity
                    (run_id, date, daily_r, equity_r, drawdown)
                VALUES (%(run_id)s, %(date)s, %(daily_r)s, %(equity_r)s, %(drawdown)s)
                ON CONFLICT (run_id, date) DO UPDATE SET
                    daily_r = EXCLUDED.daily_r,
                    equity_r = EXCLUDED.equity_r,
                    drawdown = EXCLUDED.drawdown
            """, {
                "run_id": row.get("run_id"),
                "date": date_value,
                "daily_r": daily_r,
                "equity_r": equity_r,
                "drawdown": drawdown,
            })

    # ── strategy_metrics ──────────────────────────────────────────────────

    def save_strategy_metrics(self, metrics: dict) -> None:
        with self._cursor() as cur:
            if cur is None:
                return
            total_trades = int(metrics.get("total_trades", metrics.get("trade_count", 0)) or 0)
            wins = int(metrics.get("wins", metrics.get("winning_trades", round(total_trades * float(metrics.get("win_rate", 0.0) or 0.0) / 100.0))) or 0)
            losses = int(metrics.get("losses", metrics.get("losing_trades", max(total_trades - wins, 0))) or 0)
            cur.execute("""
                INSERT INTO analytics.strategy_metrics
                    (run_id, strategy, total_trades, winning_trades, losing_trades,
                     win_rate, profit_factor, expectancy, average_win, average_loss,
                     max_drawdown, net_r)
                VALUES
                    (%(run_id)s, %(strategy)s, %(total_trades)s, %(winning_trades)s, %(losing_trades)s,
                     %(win_rate)s, %(profit_factor)s, %(expectancy)s, %(average_win)s,
                     %(average_loss)s, %(max_drawdown)s, %(net_r)s)
            """, {
                "run_id": metrics.get("run_id"),
                "strategy": metrics.get("strategy", "ST-A2"),
                "total_trades": total_trades,
                "winning_trades": wins,
                "losing_trades": losses,
                "win_rate": metrics.get("win_rate", 0.0),
                "profit_factor": metrics.get("profit_factor", 0.0),
                "expectancy": metrics.get("expectancy", metrics.get("avg_r", 0.0)),
                "average_win": metrics.get("average_win", 0.0),
                "average_loss": metrics.get("average_loss", 0.0),
                "max_drawdown": metrics.get("max_drawdown", 0.0),
                "net_r": metrics.get("net_r", metrics.get("total_r", 0.0)),
            })

    # ── Query helpers ─────────────────────────────────────────────────────

    def get_run(self, run_id: str) -> Optional[dict]:
        with self._cursor() as cur:
            if cur is None:
                return None
            cur.execute("SELECT * FROM research.replay_runs WHERE run_id = %s", (run_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_trades_for_run(self, run_id: str) -> list[dict]:
        with self._cursor() as cur:
            if cur is None:
                return []
            cur.execute(
                "SELECT * FROM research.trades WHERE run_id = %s ORDER BY entry_time",
                (run_id,)
            )
            return [dict(r) for r in cur.fetchall()]

    def is_available(self) -> bool:
        return self._available

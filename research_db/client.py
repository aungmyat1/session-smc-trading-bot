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
from typing import Optional

import psycopg2
import psycopg2.extras

log = logging.getLogger("research_db")


def _dsn_from_env() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if url.startswith("postgresql://"):
        return url
    return "postgresql://trading:TradingSecure2026!@127.0.0.1:5432/vmassit"


class ResearchDB:
    def __init__(self, dsn: Optional[str] = None) -> None:
        self._dsn = dsn or _dsn_from_env()
        self._conn: Optional[psycopg2.extensions.connection] = None
        self._available = False
        self._connect()

    def _connect(self) -> None:
        try:
            self._conn = psycopg2.connect(self._dsn)
            self._conn.autocommit = False
            self._available = True
            log.info("ResearchDB connected to %s", self._dsn.split("@")[-1])
        except psycopg2.Error as e:
            log.warning("ResearchDB unavailable: %s — replay will continue without DB", e)
            self._available = False

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
            cur.execute("""
                INSERT INTO research.replay_runs
                    (run_id, strategy, symbol, start_date, end_date, data_source,
                     rr, spread_std_pip, spread_2x_pip, notes)
                VALUES (%(run_id)s, %(strategy)s, %(symbol)s, %(start_date)s, %(end_date)s,
                        %(data_source)s, %(rr)s, %(spread_std_pip)s, %(spread_2x_pip)s, %(notes)s)
                ON CONFLICT (run_id) DO UPDATE SET
                    notes = EXCLUDED.notes
            """, {
                "run_id":        run_id,
                "strategy":      run.get("strategy", "ST-A2"),
                "symbol":        run.get("symbol", "EURUSD"),
                "start_date":    run.get("start_date"),
                "end_date":      run.get("end_date"),
                "data_source":   run.get("data_source", "csv"),
                "rr":            run.get("rr", 3.0),
                "spread_std_pip": run.get("spread_std_pip", 1.4),
                "spread_2x_pip":  run.get("spread_2x_pip", 2.8),
                "notes":         run.get("notes", ""),
            })
        return run_id

    def update_run_summary(self, run_id: str, metrics: dict) -> None:
        with self._cursor() as cur:
            if cur is None:
                return
            cur.execute("""
                UPDATE research.replay_runs SET
                    n_trades = %(n_trades)s,
                    win_rate = %(win_rate)s,
                    pf_std   = %(pf_std)s,
                    pf_2x    = %(pf_2x)s,
                    avg_r    = %(avg_r)s,
                    total_r  = %(total_r)s,
                    max_dd   = %(max_dd)s,
                    verdict  = %(verdict)s
                WHERE run_id = %(run_id)s
            """, {**metrics, "run_id": run_id})

    # ── trades ────────────────────────────────────────────────────────────

    def save_trade(self, trade: dict) -> int:
        with self._cursor() as cur:
            if cur is None:
                return 0
            cur.execute("""
                INSERT INTO research.trades
                    (run_id, strategy_id, symbol, timeframe, session, direction,
                     entry_time, exit_time, entry_price, stop_price, take_profit,
                     sl_pips, risk_reward, gross_r, result_r, result_r_2x,
                     profit_loss, exit_reason, spread_pip, bars_held)
                VALUES
                    (%(run_id)s, %(strategy_id)s, %(symbol)s, %(timeframe)s,
                     %(session)s, %(direction)s,
                     %(entry_time)s, %(exit_time)s, %(entry_price)s, %(stop_price)s,
                     %(take_profit)s, %(sl_pips)s, %(risk_reward)s, %(gross_r)s,
                     %(result_r)s, %(result_r_2x)s, %(profit_loss)s, %(exit_reason)s,
                     %(spread_pip)s, %(bars_held)s)
                RETURNING trade_id
            """, trade)
            row = cur.fetchone()
            return row["trade_id"] if row else 0

    # ── smc_events ────────────────────────────────────────────────────────

    def save_smc_event(self, event: dict) -> int:
        with self._cursor() as cur:
            if cur is None:
                return 0
            cur.execute("""
                INSERT INTO market.smc_events
                    (run_id, symbol, event_type, timeframe, event_time, direction,
                     price_level, price_high, price_low, htf_bias, session, detail)
                VALUES
                    (%(run_id)s, %(symbol)s, %(event_type)s, %(timeframe)s,
                     %(event_time)s, %(direction)s, %(price_level)s, %(price_high)s,
                     %(price_low)s, %(htf_bias)s, %(session)s, %(detail)s)
                RETURNING event_id
            """, event)
            row = cur.fetchone()
            return row["event_id"] if row else 0

    # ── daily_equity ──────────────────────────────────────────────────────

    def save_daily_equity(self, row: dict) -> None:
        with self._cursor() as cur:
            if cur is None:
                return
            cur.execute("""
                INSERT INTO analytics.daily_equity
                    (run_id, trade_date, symbol, trades_today, daily_r, cumulative_r, equity_curve)
                VALUES (%(run_id)s, %(trade_date)s, %(symbol)s, %(trades_today)s,
                        %(daily_r)s, %(cumulative_r)s, %(equity_curve)s)
                ON CONFLICT (run_id, trade_date, symbol) DO UPDATE SET
                    trades_today  = EXCLUDED.trades_today,
                    daily_r       = EXCLUDED.daily_r,
                    cumulative_r  = EXCLUDED.cumulative_r,
                    equity_curve  = EXCLUDED.equity_curve
            """, row)

    # ── strategy_metrics ──────────────────────────────────────────────────

    def save_strategy_metrics(self, metrics: dict) -> None:
        with self._cursor() as cur:
            if cur is None:
                return
            cur.execute("""
                INSERT INTO analytics.strategy_metrics
                    (run_id, strategy, symbol, period_start, period_end,
                     total_trades, wins, losses, win_rate, profit_factor, pf_2x,
                     expectancy, max_drawdown, total_r, avg_r, sharpe_r,
                     session_london_pf, session_ny_pf)
                VALUES
                    (%(run_id)s, %(strategy)s, %(symbol)s, %(period_start)s, %(period_end)s,
                     %(total_trades)s, %(wins)s, %(losses)s, %(win_rate)s,
                     %(profit_factor)s, %(pf_2x)s, %(expectancy)s, %(max_drawdown)s,
                     %(total_r)s, %(avg_r)s, %(sharpe_r)s,
                     %(session_london_pf)s, %(session_ny_pf)s)
            """, metrics)

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

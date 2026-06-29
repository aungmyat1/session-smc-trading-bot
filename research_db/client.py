"""
research_db/client.py
Research database write client — SQLAlchemy edition.

Replaces the former psycopg2 direct-connection client (D-05 fix).
Uses db.connection.SessionLocal so all writes share one session factory
and are governed by the same connection pool.

Public API (unchanged — callers require no modification)
────────────────────────────────────────────────────────
    ResearchDB(url=None)
        .save_run(run)             -> run_id str
        .save_trade(trade)         -> int (legacy row id)
        .save_smc_event(event)     -> int
        .save_daily_equity(row)    -> None
        .save_strategy_metrics(m)  -> None
        .update_run_summary(run_id, metrics) -> None
        .get_run(run_id)           -> dict | None
        .get_trades_for_run(run_id)-> list[dict]
        .is_available()            -> bool
        .close()                   -> None

All methods are safe to call when the DB is unavailable — they log and
return a null value so the replay/backtest continues without crashing.

Bug fix (D-05 assessment finding)
──────────────────────────────────
The prior client wrote daily equity to analytics.daily_equity.
The correct table is research.daily_equity (as declared in schema_v2.sql
and the ORM).  This is corrected here.
"""
from __future__ import annotations

import logging
import re
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Generator, Optional

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from db.runtime import resolve_database_url
from research.lineage import build_lineage_metadata

log = logging.getLogger("research_db")


def _make_session_factory(url: str | None) -> Any:
    """Return a SessionLocal factory, or None if URL is absent/invalid."""
    if not url:
        return None
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import QueuePool
        engine = create_engine(
            url,
            poolclass=QueuePool,
            pool_size=3,
            max_overflow=5,
            pool_pre_ping=True,
        )
        return sessionmaker(autocommit=False, autoflush=False, bind=engine)
    except Exception as exc:
        log.warning("ResearchDB could not build session factory: %s", exc)
        return None


def _strategy_name_version(run: dict) -> tuple[str, str]:
    raw_name = str(run.get("strategy_name") or run.get("strategy") or "ST-A2").strip()
    raw_version = str(run.get("strategy_version") or run.get("version") or "").strip()
    if raw_version:
        return raw_name, raw_version
    match = re.search(r"v?(\d+(?:\.\d+)*)$", raw_name, flags=re.IGNORECASE)
    if match:
        return raw_name[: match.start()].strip(" -_") or raw_name, match.group(1)
    return raw_name, "1.0"


class ResearchDB:
    def __init__(self, url: Optional[str] = None) -> None:
        resolved = url or resolve_database_url()
        self._SessionFactory = _make_session_factory(resolved)
        self._available = self._SessionFactory is not None
        if self._available:
            log.info("ResearchDB ready (SQLAlchemy)")
        else:
            log.warning("ResearchDB unavailable: DATABASE_URL not configured or unreachable")

    # ── internal session context ──────────────────────────────────────────

    @contextmanager
    def _session(self) -> Generator[Optional[Session], None, None]:
        """Yield an open Session, commit on success, rollback on error, always close."""
        if not self._available or self._SessionFactory is None:
            yield None
            return
        session: Session = self._SessionFactory()
        try:
            yield session
            session.commit()
        except SQLAlchemyError as exc:
            log.error("ResearchDB error: %s", exc)
            session.rollback()
            yield None
        except Exception as exc:
            log.error("ResearchDB unexpected error: %s", exc)
            session.rollback()
            yield None
        finally:
            session.close()

    def _ensure_strategy(self, session: Session, *, name: str, version: str,
                         description: str = "", status: str = "active") -> int | None:
        lineage = build_lineage_metadata(
            source="research_db.client",
            strategy=name,
            strategy_version=version,
            artifact="strategy",
            extra={"status": status},
        )
        row = session.execute(
            text("""
                INSERT INTO research.strategies (strategy_name, version, description, rules_json, status)
                VALUES (:name, :version, :description, CAST(:lineage AS jsonb), :status)
                ON CONFLICT (strategy_name, version) DO UPDATE SET
                    description = EXCLUDED.description,
                    status = EXCLUDED.status
                RETURNING id
            """),
            {"name": name, "version": version, "description": description,
             "lineage": __import__("json").dumps(lineage), "status": status},
        ).fetchone()
        if row:
            return row[0]
        row = session.execute(
            text("SELECT id FROM research.strategies WHERE strategy_name = :n AND version = :v"),
            {"n": name, "v": version},
        ).fetchone()
        return row[0] if row else None

    # ── replay_runs ───────────────────────────────────────────────────────

    def save_run(self, run: dict) -> str:
        run_id = (
            run.get("run_id")
            or f"run_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:6]}"
        )
        with self._session() as session:
            if session is None:
                return run_id
            strategy_name, strategy_version = _strategy_name_version(run)
            strategy_id = self._ensure_strategy(
                session,
                name=strategy_name,
                version=strategy_version,
                description=str(run.get("notes", ""))[:2000],
                status=str(run.get("status", "active")),
            )
            session.execute(
                text("""
                    INSERT INTO research.replay_runs
                        (run_id, strategy_id, symbol, start_date, end_date, scenario, data_source)
                    VALUES (:run_id, :strategy_id, :symbol, :start_date, :end_date,
                            :scenario, :data_source)
                    ON CONFLICT (run_id) DO UPDATE SET
                        strategy_id = EXCLUDED.strategy_id,
                        symbol      = EXCLUDED.symbol,
                        start_date  = EXCLUDED.start_date,
                        end_date    = EXCLUDED.end_date,
                        scenario    = EXCLUDED.scenario,
                        data_source = EXCLUDED.data_source
                """),
                {
                    "run_id":      run_id,
                    "strategy_id": strategy_id,
                    "symbol":      run.get("symbol", "EURUSD"),
                    "start_date":  run.get("start_date"),
                    "end_date":    run.get("end_date"),
                    "scenario":    run.get("scenario", "standard"),
                    "data_source": run.get("data_source", "csv"),
                },
            )
        return run_id

    def update_run_summary(self, run_id: str, metrics: dict) -> None:
        with self._session() as session:
            if session is None:
                return
            session.execute(
                text("""
                    UPDATE research.replay_runs SET
                        scenario    = COALESCE(:scenario,    scenario),
                        data_source = COALESCE(:data_source, data_source)
                    WHERE run_id = :run_id
                """),
                {
                    "run_id":      run_id,
                    "scenario":    metrics.get("scenario"),
                    "data_source": metrics.get("data_source"),
                },
            )

    # ── trades ────────────────────────────────────────────────────────────

    def save_trade(self, trade: dict) -> int:
        with self._session() as session:
            if session is None:
                return 0
            strategy_name, strategy_version = _strategy_name_version(trade)
            strategy_id = trade.get("strategy_id") or self._ensure_strategy(
                session,
                name=strategy_name,
                version=strategy_version,
                description=str(trade.get("notes", ""))[:2000],
                status=str(trade.get("status", "active")),
            )
            trade_id = (
                trade.get("trade_id")
                or f"{trade.get('run_id', 'run')}_{trade.get('symbol', 'SYM')}"
                   f"_{trade.get('entry_time', datetime.now(timezone.utc).isoformat())}"
                   f"_{uuid.uuid4().hex[:8]}"
            )
            spread_cost = trade.get("spread_cost_pips", trade.get("spread_pip", 0.0))
            cost_in_r   = trade.get("cost_in_r")
            if cost_in_r is None:
                sl_pips   = float(trade.get("sl_pips") or 0.0)
                cost_in_r = float(spread_cost or 0.0) / sl_pips if sl_pips > 0 else 0.0
            gross_r = trade.get("gross_result_r", trade.get("gross_r", trade.get("result_r", 0.0)))
            net_r   = trade.get("net_result_r", trade.get("result_r", 0.0))
            tp1_hit = trade.get("tp1_hit")
            if tp1_hit is None:
                tp1_hit = bool(
                    trade.get("result_r_2x") is not None
                    and float(trade.get("result_r_2x", 0.0)) != float(net_r)
                )
            row = session.execute(
                text("""
                    INSERT INTO research.trades
                        (trade_id, run_id, strategy_id, symbol, session, direction,
                         setup_type, entry_time, exit_time, entry_price, stop_price,
                         take_profit, tp2_price, sl_pips, risk_reward, spread_cost_pips,
                         cost_in_r, gross_result_r, net_result_r, exit_reason, tp1_hit,
                         session_high, session_low, session_range_pips)
                    VALUES
                        (:trade_id, :run_id, :strategy_id, :symbol, :session, :direction,
                         :setup_type, :entry_time, :exit_time, :entry_price, :stop_price,
                         :take_profit, :tp2_price, :sl_pips, :risk_reward, :spread_cost_pips,
                         :cost_in_r, :gross_result_r, :net_result_r, :exit_reason, :tp1_hit,
                         :session_high, :session_low, :session_range_pips)
                    ON CONFLICT (trade_id) DO UPDATE SET
                        run_id        = EXCLUDED.run_id,
                        strategy_id   = EXCLUDED.strategy_id,
                        exit_time     = EXCLUDED.exit_time,
                        exit_reason   = EXCLUDED.exit_reason,
                        net_result_r  = EXCLUDED.net_result_r,
                        gross_result_r = EXCLUDED.gross_result_r
                    RETURNING id
                """),
                {
                    "trade_id":          trade_id,
                    "run_id":            trade.get("run_id"),
                    "strategy_id":       strategy_id,
                    "symbol":            trade.get("symbol"),
                    "session":           trade.get("session"),
                    "direction":         trade.get("direction"),
                    "setup_type":        trade.get("setup_type", "A"),
                    "entry_time":        trade.get("entry_time"),
                    "exit_time":         trade.get("exit_time"),
                    "entry_price":       trade.get("entry_price"),
                    "stop_price":        trade.get("stop_price", trade.get("stop_loss")),
                    "take_profit":       trade.get("take_profit"),
                    "tp2_price":         trade.get("tp2_price"),
                    "sl_pips":           trade.get("sl_pips"),
                    "risk_reward":       trade.get("risk_reward", trade.get("rr")),
                    "spread_cost_pips":  spread_cost,
                    "cost_in_r":         cost_in_r,
                    "gross_result_r":    gross_r,
                    "net_result_r":      net_r,
                    "exit_reason":       trade.get("exit_reason"),
                    "tp1_hit":           tp1_hit,
                    "session_high":      trade.get("session_high"),
                    "session_low":       trade.get("session_low"),
                    "session_range_pips": trade.get("session_range_pips"),
                },
            ).fetchone()
            return row[0] if row else 0

    # ── smc_events ────────────────────────────────────────────────────────

    def save_smc_event(self, event: dict) -> int:
        import json
        _skip = {"run_id", "symbol", "event_type", "timeframe", "event_time",
                 "direction", "price_level", "price_high", "price_low",
                 "htf_bias", "session", "detail", "lineage"}
        extra = {k: v for k, v in event.items() if k not in _skip}
        event_price = event.get(
            "event_price",
            event.get("price_level", event.get("price_high", event.get("price_low"))),
        )
        metadata_payload = json.dumps({
            "run_id":     event.get("run_id"),
            "direction":  event.get("direction"),
            "price_high": event.get("price_high"),
            "price_low":  event.get("price_low"),
            "htf_bias":   event.get("htf_bias"),
            "session":    event.get("session"),
            "detail":     event.get("detail"),
            **extra,
            "lineage": build_lineage_metadata(
                source="research_db.client",
                strategy=str(event.get("strategy", "unknown")),
                strategy_version=str(event.get("strategy_version", "unknown")),
                artifact="smc_event",
            ),
        })
        with self._session() as session:
            if session is None:
                return 0
            row = session.execute(
                text("""
                    INSERT INTO market.smc_events
                        (symbol, timeframe, timestamp, event_type, event_price,
                         strength_score, metadata_json)
                    VALUES
                        (:symbol, :timeframe, :timestamp, :event_type, :event_price,
                         :strength_score, CAST(:metadata_json AS jsonb))
                    RETURNING id
                """),
                {
                    "symbol":         event.get("symbol"),
                    "timeframe":      event.get("timeframe"),
                    "timestamp":      event.get("timestamp") or event.get("event_time"),
                    "event_type":     event.get("event_type"),
                    "event_price":    event_price,
                    "strength_score": event.get("strength_score"),
                    "metadata_json":  metadata_payload,
                },
            ).fetchone()
            return row[0] if row else 0

    # ── daily_equity ──────────────────────────────────────────────────────

    def save_daily_equity(self, row: dict) -> None:
        with self._session() as session:
            if session is None:
                return
            session.execute(
                text("""
                    INSERT INTO research.daily_equity
                        (run_id, date, daily_r, equity_r, drawdown)
                    VALUES (:run_id, :date, :daily_r, :equity_r, :drawdown)
                    ON CONFLICT (run_id, date) DO UPDATE SET
                        daily_r  = EXCLUDED.daily_r,
                        equity_r = EXCLUDED.equity_r,
                        drawdown = EXCLUDED.drawdown
                """),
                {
                    "run_id":  row.get("run_id"),
                    "date":    row.get("date", row.get("trade_date")),
                    "daily_r": row.get("daily_r", row.get("daily_return_r")),
                    "equity_r": row.get("equity_r", row.get("cumulative_r")),
                    "drawdown": row.get("drawdown"),
                },
            )

    # ── strategy_metrics ──────────────────────────────────────────────────

    def save_strategy_metrics(self, metrics: dict) -> None:
        total = int(metrics.get("total_trades", metrics.get("trade_count", 0)) or 0)
        wr    = float(metrics.get("win_rate", 0.0) or 0.0)
        wins  = int(metrics.get("wins", metrics.get("winning_trades", round(total * wr / 100.0))) or 0)
        losses = int(metrics.get("losses", metrics.get("losing_trades", max(total - wins, 0))) or 0)
        with self._session() as session:
            if session is None:
                return
            session.execute(
                text("""
                    INSERT INTO analytics.strategy_metrics
                        (run_id, strategy, total_trades, winning_trades, losing_trades,
                         win_rate, profit_factor, expectancy, average_win, average_loss,
                         max_drawdown, net_r)
                    VALUES
                        (:run_id, :strategy, :total_trades, :winning_trades, :losing_trades,
                         :win_rate, :profit_factor, :expectancy, :average_win, :average_loss,
                         :max_drawdown, :net_r)
                """),
                {
                    "run_id":         metrics.get("run_id"),
                    "strategy":       metrics.get("strategy", "ST-A2"),
                    "total_trades":   total,
                    "winning_trades": wins,
                    "losing_trades":  losses,
                    "win_rate":       wr,
                    "profit_factor":  metrics.get("profit_factor", 0.0),
                    "expectancy":     metrics.get("expectancy", metrics.get("avg_r", 0.0)),
                    "average_win":    metrics.get("average_win", 0.0),
                    "average_loss":   metrics.get("average_loss", 0.0),
                    "max_drawdown":   metrics.get("max_drawdown", 0.0),
                    "net_r":          metrics.get("net_r", metrics.get("total_r", 0.0)),
                },
            )

    # ── query helpers ─────────────────────────────────────────────────────

    def get_run(self, run_id: str) -> Optional[dict]:
        with self._session() as session:
            if session is None:
                return None
            row = session.execute(
                text("SELECT * FROM research.replay_runs WHERE run_id = :rid"),
                {"rid": run_id},
            ).mappings().fetchone()
            return dict(row) if row else None

    def get_trades_for_run(self, run_id: str) -> list[dict]:
        with self._session() as session:
            if session is None:
                return []
            rows = session.execute(
                text("SELECT * FROM research.trades WHERE run_id = :rid ORDER BY entry_time"),
                {"rid": run_id},
            ).mappings().fetchall()
            return [dict(r) for r in rows]

    # ── lifecycle ─────────────────────────────────────────────────────────

    def is_available(self) -> bool:
        return self._available

    def close(self) -> None:
        """No-op — sessions are per-call; the engine pool manages connections."""

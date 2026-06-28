#!/usr/bin/env python3
"""Ingest D2E3 trade journal events into the research PostgreSQL database.

This bridges the structured JSONL journal produced by `scripts/run_d2_e3_demo.py`
into the quant research schema:
  - research.replay_runs
  - research.trades
  - research.trade_features
  - research.daily_equity
  - analytics.strategy_metrics
  - analytics.monthly_metrics

The script is idempotent at the row level via ON CONFLICT DO NOTHING / UPDATE
where appropriate. It is safe to run repeatedly on the same journal file.
"""
from __future__ import annotations

import argparse
import json
import math
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import psycopg2
from psycopg2.extras import RealDictCursor

from db.runtime import resolve_database_url

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG = ROOT / "logs" / "d2e3_trades.jsonl"
DEFAULT_DATABASE_URL = resolve_database_url()

STRATEGY_NAME = "ST-D2-E3-OPT2"
STRATEGY_VERSION = "1.0"
log = logging.getLogger("d2e3_journal_to_db")


def _parse_ts(raw: str | None) -> datetime | None:
    if not raw:
        return None
    ts = datetime.fromisoformat(raw)
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def load_events(log_file: Path = DEFAULT_LOG) -> list[dict]:
    if not log_file.exists():
        return []
    events: list[dict] = []
    for line in log_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        ev["_ts"] = _parse_ts(ev.get("ts"))
        if ev["_ts"] is not None:
            events.append(ev)
    return sorted(events, key=lambda ev: ev["_ts"])


def build_trade_records(events: Iterable[dict]) -> list[dict]:
    """Correlate the journal into closed trade records suitable for SQL writes."""
    last_signal: dict[str, dict] = {}
    open_fills: dict[str, list[dict]] = defaultdict(list)
    trades: list[dict] = []

    for ev in events:
        sym = ev.get("symbol", "")
        etype = ev.get("event", "")

        if etype == "SIGNAL_CREATED":
            last_signal[sym] = ev
            continue

        if etype == "ORDER_FILLED":
            sig = last_signal.pop(sym, None)
            if sig is None:
                continue

            entry = float(ev.get("entry_price") or sig.get("entry") or 0.0)
            stop = float(ev.get("sl") or sig.get("sl") or 0.0)
            tp = float(ev.get("tp") or sig.get("tp") or 0.0)
            risk = abs(entry - stop)
            rr = round(abs(tp - entry) / risk, 4) if risk > 0 else 0.0
            trade = {
                "symbol": sym,
                "session": sig.get("session", ""),
                "direction": sig.get("side", ""),
                "signal_ts": sig.get("_ts"),
                "fill_ts": ev["_ts"],
                "close_ts": None,
                "entry_price": entry,
                "stop_price": stop,
                "take_profit": tp,
                "sl_pips": float(sig.get("sl_pips") or 0.0),
                "risk_reward": rr,
                "volume": float(ev.get("volume") or 0.0),
                "order_id": ev.get("order_id", ""),
                "dry_run": bool(ev.get("dry_run", False)),
                "result_r": None,
                "exit_reason": None,
                "signal_reason": sig.get("reason", ""),
                "trade_id": None,
            }
            open_fills[sym].append(trade)
            continue

        if etype == "POSITION_CLOSED":
            if not open_fills[sym]:
                continue
            trade = open_fills[sym].pop(0)
            trade["close_ts"] = ev["_ts"]
            trade["result_r"] = float(ev.get("result_r") or 0.0)
            trade["exit_reason"] = ev.get("exit_reason", "")
            trade["trade_id"] = trade["trade_id"] or (
                f"{sym}:{trade['fill_ts'].isoformat()}:{trade.get('order_id') or uuid.uuid4().hex[:8]}"
            )
            trades.append(trade)

    return trades


def _profit_factor(results: list[float]) -> float:
    wins = sum(r for r in results if r > 0)
    losses = abs(sum(r for r in results if r <= 0))
    return round(wins / losses, 4) if losses > 0 else (math.inf if wins > 0 else 0.0)


def build_daily_equity(trades: list[dict]) -> list[dict]:
    by_day: dict[str, list[float]] = defaultdict(list)
    for trade in trades:
        close_ts = trade.get("close_ts")
        if close_ts is None:
            continue
        by_day[str(close_ts.date())].append(float(trade.get("result_r") or 0.0))

    rows: list[dict] = []
    equity = 0.0
    peak = 0.0
    for day in sorted(by_day):
        daily_r = sum(by_day[day])
        equity += daily_r
        peak = max(peak, equity)
        drawdown = (peak - equity) / peak if peak > 0 else 0.0
        rows.append(
            {
                "date": day,
                "daily_r": round(daily_r, 4),
                "equity_r": round(equity, 4),
                "drawdown": round(drawdown, 6),
            }
        )
    return rows


def build_metrics(trades: list[dict]) -> dict:
    results = [float(t.get("result_r") or 0.0) for t in trades]
    wins = [r for r in results if r > 0]
    losses = [r for r in results if r <= 0]
    total = len(results)
    gross_pf = _profit_factor(results)
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for r in results:
        equity += r
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return {
        "total_trades": total,
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate": round((len(wins) / total) * 100.0, 2) if total else 0.0,
        "profit_factor": gross_pf if math.isfinite(gross_pf) else 9999.0,
        "expectancy": round(sum(results) / total, 4) if total else 0.0,
        "average_win": round(sum(wins) / len(wins), 4) if wins else 0.0,
        "average_loss": round(abs(sum(losses)) / len(losses), 4) if losses else 0.0,
        "max_drawdown": round(max_dd, 4),
        "net_r": round(sum(results), 2),
    }


def build_monthly_metrics(trades: list[dict]) -> list[dict]:
    by_month: dict[str, list[float]] = defaultdict(list)
    for trade in trades:
        close_ts = trade.get("close_ts")
        if close_ts is None:
            continue
        by_month[str(close_ts)[:7]].append(float(trade.get("result_r") or 0.0))

    rows: list[dict] = []
    for month in sorted(by_month):
        values = by_month[month]
        wins = [r for r in values if r > 0]
        losses = [r for r in values if r <= 0]
        rows.append(
            {
                "month": month,
                "trades": len(values),
                "win_rate": round((len(wins) / len(values)) * 100.0, 2) if values else 0.0,
                "profit_factor": _profit_factor(values) if values else 0.0,
                "net_r": round(sum(values), 2),
                "drawdown": 0.0 if not values else round(max(0.0, abs(sum(losses))), 4),
            }
        )
    return rows


def _connect_database(database_url: str):
    """Open a PostgreSQL connection if available, otherwise return None.

    The D2E3 journal sync is a best-effort bridge from the local JSONL journal
    into the research warehouse. If PostgreSQL is down or unreachable, the
    timer should skip cleanly instead of turning an expected outage into a hard
    failure.
    """
    try:
        return psycopg2.connect(database_url)
    except psycopg2.Error as exc:
        log.warning("Research DB unavailable at %s: %s", database_url.split("@")[-1], exc)
        return None


def _get_strategy_id(cur) -> int:
    cur.execute(
        """
        INSERT INTO research.strategies (strategy_name, version, description, status)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (strategy_name, version) DO NOTHING
        """,
        (
            STRATEGY_NAME,
            STRATEGY_VERSION,
            "D2 E3 research branch: PDH/PDL sweep + MSS + pullback limit",
            "research",
        ),
    )
    cur.execute(
        "SELECT id FROM research.strategies WHERE strategy_name = %s AND version = %s",
        (STRATEGY_NAME, STRATEGY_VERSION),
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError("could not resolve strategy id")
    return int(row["id"])


def sync_journal(database_url: str, log_file: Path, run_id: str | None = None) -> dict:
    events = load_events(log_file)
    trades = build_trade_records(events)
    if not events or not trades:
        return {"run_id": run_id, "trades": len(trades), "events": len(events), "skipped": True}
    if run_id is None:
        first_ts = events[0]["_ts"] if events else datetime.now(timezone.utc)
        run_id = f"d2e3_demo_{first_ts.strftime('%Y%m%dT%H%M%SZ')}"

    conn = _connect_database(database_url)
    if conn is None:
        return {
            "run_id": run_id,
            "trades": len(trades),
            "events": len(events),
            "skipped": True,
            "reason": "research database unavailable",
        }

    with conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            strategy_id = _get_strategy_id(cur)
            symbol = trades[0]["symbol"] if trades else "EURUSD"
            start_date = trades[0]["signal_ts"].date() if trades and trades[0]["signal_ts"] else None
            end_date = trades[-1]["close_ts"].date() if trades and trades[-1]["close_ts"] else None
            cur.execute(
                """
                INSERT INTO research.replay_runs
                    (run_id, strategy_id, symbol, start_date, end_date, scenario, data_source)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (run_id) DO UPDATE SET
                    strategy_id = EXCLUDED.strategy_id,
                    symbol = EXCLUDED.symbol,
                    start_date = COALESCE(EXCLUDED.start_date, research.replay_runs.start_date),
                    end_date = COALESCE(EXCLUDED.end_date, research.replay_runs.end_date),
                    scenario = EXCLUDED.scenario,
                    data_source = EXCLUDED.data_source
                """,
                    (run_id, strategy_id, symbol, start_date, end_date, "demo", "MetaAPI_Demo"),
                )

            cur.execute(
                "DELETE FROM analytics.strategy_metrics WHERE run_id = %s AND strategy = %s",
                (run_id, STRATEGY_NAME),
            )
            cur.execute(
                "DELETE FROM analytics.monthly_metrics WHERE run_id = %s",
                (run_id,),
            )

            for trade in trades:
                cur.execute(
                    """
                    INSERT INTO research.trades (
                        trade_id, run_id, strategy_id, symbol, session, direction,
                        setup_type, entry_time, exit_time, entry_price, stop_price,
                        take_profit, sl_pips, risk_reward, spread_cost_pips, cost_in_r,
                        gross_result_r, net_result_r, exit_reason, tp1_hit,
                        session_high, session_low, session_range_pips
                    ) VALUES (
                        %(trade_id)s, %(run_id)s, %(strategy_id)s, %(symbol)s, %(session)s, %(direction)s,
                        %(setup_type)s, %(entry_time)s, %(exit_time)s, %(entry_price)s, %(stop_price)s,
                        %(take_profit)s, %(sl_pips)s, %(risk_reward)s, %(spread_cost_pips)s, %(cost_in_r)s,
                        %(gross_result_r)s, %(net_result_r)s, %(exit_reason)s, %(tp1_hit)s,
                        %(session_high)s, %(session_low)s, %(session_range_pips)s
                    )
                    ON CONFLICT (trade_id) DO NOTHING
                    """,
                    {
                        "trade_id": trade["trade_id"],
                        "run_id": run_id,
                        "strategy_id": strategy_id,
                        "symbol": trade["symbol"],
                        "session": trade["session"],
                        "direction": trade["direction"],
                        "setup_type": "D2E3",
                        "entry_time": trade["fill_ts"],
                        "exit_time": trade["close_ts"],
                        "entry_price": trade["entry_price"],
                        "stop_price": trade["stop_price"],
                        "take_profit": trade["take_profit"],
                        "sl_pips": trade["sl_pips"] or None,
                        "risk_reward": trade["risk_reward"],
                        "spread_cost_pips": None,
                        "cost_in_r": None,
                        "gross_result_r": trade["result_r"],
                        "net_result_r": trade["result_r"],
                        "exit_reason": trade["exit_reason"],
                        "tp1_hit": False,
                        "session_high": None,
                        "session_low": None,
                        "session_range_pips": None,
                    },
                )
                cur.execute(
                    """
                    INSERT INTO research.trade_features
                        (trade_id, bos_present, choch_present, fvg_present,
                         liquidity_sweep_present, spread_scenario, feature_json)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (trade_id) DO NOTHING
                    """,
                    (
                        trade["trade_id"],
                        True,
                        True,
                        True,
                        True,
                        "demo",
                        json.dumps(
                            {
                                "signal_reason": trade["signal_reason"],
                                "dry_run": trade["dry_run"],
                                "order_id": trade["order_id"],
                            }
                        ),
                    ),
                )

            for row in build_daily_equity(trades):
                cur.execute(
                    """
                    INSERT INTO research.daily_equity (run_id, date, daily_r, equity_r, drawdown)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (run_id, date) DO UPDATE SET
                        daily_r = EXCLUDED.daily_r,
                        equity_r = EXCLUDED.equity_r,
                        drawdown = EXCLUDED.drawdown
                    """,
                    (run_id, row["date"], row["daily_r"], row["equity_r"], row["drawdown"]),
                )

            metrics = build_metrics(trades)
            cur.execute(
                """
                INSERT INTO analytics.strategy_metrics (
                    run_id, strategy, total_trades, winning_trades, losing_trades,
                    win_rate, profit_factor, expectancy, average_win, average_loss,
                    max_drawdown, net_r
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    run_id,
                    STRATEGY_NAME,
                    metrics["total_trades"],
                    metrics["winning_trades"],
                    metrics["losing_trades"],
                    metrics["win_rate"],
                    metrics["profit_factor"],
                    metrics["expectancy"],
                    metrics["average_win"],
                    metrics["average_loss"],
                    metrics["max_drawdown"],
                    metrics["net_r"],
                ),
            )

            for row in build_monthly_metrics(trades):
                cur.execute(
                    """
                    INSERT INTO analytics.monthly_metrics (
                        run_id, month, trades, win_rate, profit_factor, net_r, drawdown
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (run_id, row["month"], row["trades"], row["win_rate"], row["profit_factor"], row["net_r"], row["drawdown"]),
                )
        conn.commit()

    return {"run_id": run_id, "trades": len(trades), "events": len(events)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync D2E3 journal into PostgreSQL")
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--database-url", default=DEFAULT_DATABASE_URL)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    events = load_events(args.log)
    trades = build_trade_records(events)
    if args.dry_run:
        print(json.dumps({
            "log": str(args.log),
            "events": len(events),
            "trades": len(trades),
            "sample_run_id": args.run_id or (f"d2e3_demo_{events[0]['_ts'].strftime('%Y%m%dT%H%M%SZ')}" if events else None),
            "skipped": not events or not trades,
        }, indent=2, default=str))
        return

    result = sync_journal(args.database_url, args.log, args.run_id)
    print(json.dumps(result, indent=2))

    if result.get("skipped"):
        return


if __name__ == "__main__":
    main()

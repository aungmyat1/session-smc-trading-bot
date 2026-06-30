"""
pipeline/04_write_db.py
PostgreSQL Writer — loads replay results from cache Parquet and writes to DB.

Writes:
  research.strategies       — one row per strategy spec
  research.replay_runs      — one row per run_id / scenario
  research.trades           — one row per trade (net-of-fees fields)
  research.trade_features   — per-trade SMC feature flags
  research.daily_equity     — day-by-day equity curve
  analytics.strategy_metrics — aggregate PF, WR, DD per run
  analytics.monthly_metrics  — month-by-month breakdown
  analytics.phase0_gate      — gate pass/fail verdict per run

Run after 03_replay_engine.py:
    python -m pipeline.04_write_db
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import polars as pl
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from db.runtime import resolve_database_url
from .config import FEATURES_DIR, PHASE0_MIN_NET_PF, PHASE0_MIN_TRADES

_UTC = timezone.utc
_DB_URL = resolve_database_url()


def _engine():
    if not _DB_URL:
        raise RuntimeError(
            "DATABASE_URL is required for PostgreSQL writes; set it or use --skip-db"
        )
    return create_engine(_DB_URL, pool_pre_ping=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_py(v: Any) -> Any:
    """Polars scalars → plain Python for SQLAlchemy binds."""
    if hasattr(v, "item"):     # numpy/polars scalar
        return v.item()
    if isinstance(v, (pl.Series,)):
        return v.to_list()[0]
    return v


def _equity_curve(trades: list[dict]) -> list[dict]:
    """Build daily equity rows (cumulative net R, drawdown)."""
    by_date: dict[date, list[float]] = {}
    for t in trades:
        et = t.get("exit_time")
        if et is None:
            continue
        if isinstance(et, str):
            et = datetime.fromisoformat(et.replace("Z", "+00:00"))
        d = et.date() if hasattr(et, "date") else et
        by_date.setdefault(d, []).append(float(t["net_result_r"]))

    rows: list[dict] = []
    equity = 0.0
    peak   = 0.0
    for d in sorted(by_date):
        daily_r = sum(by_date[d])
        equity += daily_r
        peak    = max(peak, equity)
        dd      = (peak - equity) / max(abs(peak), 1e-9)
        rows.append({"date": d, "daily_r": round(daily_r, 4),
                     "equity_r": round(equity, 4), "drawdown": round(dd, 6)})
    return rows


def _compute_metrics(trades: list[dict]) -> dict:
    if not trades:
        return {}
    rs    = [float(t["net_result_r"]) for t in trades]
    wins  = [r for r in rs if r > 0]
    losses= [r for r in rs if r <= 0]
    gp    = sum(wins)
    gl    = abs(sum(losses))
    pf    = round(gp / gl, 4) if gl > 0 else 0.0
    eq    = 0.0
    peak  = 0.0
    max_dd= 0.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        max_dd = max(max_dd, peak - eq)
    return {
        "total_trades":   len(trades),
        "winning_trades": len(wins),
        "losing_trades":  len(losses),
        "win_rate":       round(len(wins) / len(trades) * 100, 2),
        "profit_factor":  pf,
        "expectancy":     round(sum(rs) / len(rs), 4),
        "average_win":    round(gp / len(wins), 4) if wins else 0.0,
        "average_loss":   round(gl / len(losses), 4) if losses else 0.0,
        "max_drawdown":   round(max_dd, 4),
        "net_r":          round(sum(rs), 2),
    }


def _monthly_breakdown(trades: list[dict]) -> list[dict]:
    by_month: dict[str, list[float]] = {}
    for t in trades:
        et = t.get("exit_time")
        if et is None:
            continue
        if isinstance(et, str):
            et = datetime.fromisoformat(et.replace("Z", "+00:00"))
        key = str(et)[:7]   # "YYYY-MM"
        by_month.setdefault(key, []).append(float(t["net_result_r"]))

    rows: list[dict] = []
    for month in sorted(by_month):
        rs  = by_month[month]
        wins= [r for r in rs if r > 0]
        los = [r for r in rs if r <= 0]
        gp  = sum(wins)
        gl  = abs(sum(los))
        eq  = 0.0; peak = 0.0; mdd = 0.0
        for r in rs:
            eq += r; peak = max(peak, eq); mdd = max(mdd, peak - eq)
        rows.append({
            "month":         month,
            "trades":        len(rs),
            "win_rate":      round(len(wins) / len(rs) * 100, 2) if rs else 0.0,
            "profit_factor": round(gp / gl, 4) if gl > 0 else 0.0,
            "net_r":         round(sum(rs), 2),
            "drawdown":      round(mdd, 4),
        })
    return rows


# ── Main writer ───────────────────────────────────────────────────────────────

def write_all(
    engine,
    replay_df: pl.DataFrame,
    strategy_name: str = "ST-A2",
    strategy_version: str = "1.0",
) -> None:
    run_ids = replay_df.select("run_id").unique()["run_id"].to_list()

    with Session(engine) as session:
        # ── strategy row (upsert by name+version) ────────────────────────────
        session.execute(text("""
            INSERT INTO research.strategies (strategy_name, version, description, status)
            VALUES (:sname, :sver, :sdesc, 'active')
            ON CONFLICT DO NOTHING
        """), {
            "sname": strategy_name,
            "sver": strategy_version,
            "sdesc": f"Strategy: {strategy_name} v{strategy_version}",
        })
        strategy_id_row = session.execute(text(
            "SELECT id FROM research.strategies WHERE strategy_name=:sname AND version=:sver"
        ), {"sname": strategy_name, "sver": strategy_version}).fetchone()
        strategy_id = strategy_id_row[0] if strategy_id_row else 1

        for run_id in run_ids:
            run_df = replay_df.filter(pl.col("run_id") == run_id)
            trades = run_df.to_dicts()
            if not trades:
                continue

            first = trades[0]
            symbol  = first.get("symbol", "")
            # Derive date range from entry times
            entry_times = [t["entry_time"] for t in trades if t.get("entry_time")]
            start_date  = min(entry_times).date() if entry_times else None
            end_date    = max(entry_times).date() if entry_times else None
            scenario    = "standard" if "standard" in run_id else "stress_2x"

            # ── replay_run ────────────────────────────────────────────────────
            session.execute(text("""
                INSERT INTO research.replay_runs
                    (run_id, strategy_id, symbol, start_date, end_date, data_source, scenario)
                VALUES (:run_id, :sid, :sym, :sd, :ed, 'Dukascopy_Parquet', :scenario)
                ON CONFLICT (run_id) DO NOTHING
            """), {
                "run_id": run_id, "sid": strategy_id, "sym": symbol,
                "sd": start_date, "ed": end_date, "scenario": scenario,
            })

            # ── trades ────────────────────────────────────────────────────────
            for t in trades:
                session.execute(text("""
                    INSERT INTO research.trades (
                        trade_id, run_id, strategy_id, symbol, session, direction,
                        setup_type, entry_time, exit_time, entry_price, stop_price,
                        take_profit, sl_pips, risk_reward, spread_cost_pips, cost_in_r,
                        gross_result_r, net_result_r, exit_reason, tp1_hit,
                        session_high, session_low, session_range_pips
                    ) VALUES (
                        :trade_id, :run_id, :sid, :symbol, :session, :direction,
                        :setup_type, :entry_time, :exit_time, :entry_price, :stop_price,
                        :tp1_price, :sl_pips, :risk_reward, :spread_cost_pips, :cost_in_r,
                        :gross_result_r, :net_result_r, :exit_reason, :tp1_hit,
                        :session_high, :session_low, :session_range_pips
                    )
                    ON CONFLICT (trade_id) DO NOTHING
                """), {**t, "sid": strategy_id})

                # ── trade_features ────────────────────────────────────────────
                session.execute(text("""
                    INSERT INTO research.trade_features
                        (trade_id, bos_present, choch_present, fvg_present,
                         liquidity_sweep_present, spread_scenario)
                    VALUES (:trade_id, :bos, :choch, :fvg, :sweep, :scenario)
                    ON CONFLICT (trade_id) DO NOTHING
                """), {
                    "trade_id": t["trade_id"],
                    "bos":      t.get("bos_present", False),
                    "choch":    t.get("choch_present", False),
                    "fvg":      t.get("fvg_present", False),
                    "sweep":    t.get("liquidity_sweep_present", False),
                    "scenario": scenario,
                })

            # ── daily equity ──────────────────────────────────────────────────
            for eq_row in _equity_curve(trades):
                session.execute(text("""
                    INSERT INTO research.daily_equity
                        (run_id, date, daily_r, equity_r, drawdown)
                    VALUES (:run_id, :date, :daily_r, :equity_r, :drawdown)
                    ON CONFLICT (run_id, date) DO NOTHING
                """), {"run_id": run_id, **eq_row})

            # ── strategy_metrics ──────────────────────────────────────────────
            m = _compute_metrics(trades)
            if m:
                session.execute(text("""
                    INSERT INTO analytics.strategy_metrics (
                        run_id, strategy, total_trades, winning_trades, losing_trades,
                        win_rate, profit_factor, expectancy, average_win, average_loss,
                        max_drawdown, net_r
                    ) VALUES (
                        :run_id, :strategy_name, :total_trades, :winning_trades, :losing_trades,
                        :win_rate, :profit_factor, :expectancy, :average_win, :average_loss,
                        :max_drawdown, :net_r
                    )
                """), {"run_id": run_id, "strategy_name": strategy_name, **m})

            # ── monthly_metrics ───────────────────────────────────────────────
            for mr in _monthly_breakdown(trades):
                session.execute(text("""
                    INSERT INTO analytics.monthly_metrics
                        (run_id, month, trades, win_rate, profit_factor, net_r, drawdown)
                    VALUES (:run_id, :month, :trades, :win_rate, :profit_factor, :net_r, :drawdown)
                """), {"run_id": run_id, **mr})

            # ── phase0_gate ───────────────────────────────────────────────────
            n  = m.get("total_trades", 0)
            pf = m.get("profit_factor", 0.0)
            passed = n >= PHASE0_MIN_TRADES and pf > PHASE0_MIN_NET_PF
            session.execute(text("""
                INSERT INTO analytics.phase0_gate
                    (run_id, symbol, scenario, n_trades, net_pf, min_trades_req,
                     min_pf_req, gate_pass, evaluated_at)
                VALUES
                    (:run_id, :symbol, :scenario, :n, :pf, :min_n, :min_pf, :passed, NOW())
                ON CONFLICT (run_id) DO UPDATE
                    SET net_pf=EXCLUDED.net_pf, gate_pass=EXCLUDED.gate_pass
            """), {
                "run_id": run_id, "symbol": symbol, "scenario": scenario,
                "n": n, "pf": pf, "min_n": PHASE0_MIN_TRADES,
                "min_pf": PHASE0_MIN_NET_PF, "passed": passed,
            })

        session.commit()
    print("✅ All data written to PostgreSQL.")


def main() -> None:
    cache = FEATURES_DIR / "_replay_results.parquet"
    if not cache.exists():
        print(f"No replay cache at {cache}. Run 03_replay_engine.py first.")
        return

    df = pl.read_parquet(cache)
    print(f"Loaded {len(df):,} trades from {cache}")

    eng = _engine()
    write_all(eng, df)


if __name__ == "__main__":
    main()

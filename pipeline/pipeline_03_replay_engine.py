"""
pipeline/03_replay_engine.py
ST-A2 Phase-0 Deterministic Replay Engine

Key upgrades over archive prototype:
  - Uses generate_signal_A() from session_smc — full 11-phase AND-gate, no shortcuts
  - Trade outcomes simulated by walking M1 bars forward — no random outcomes
  - TP1 at 4R closes 75%, SL moves to BE, TP2 runner at 5R (per CLAUDE.md §4)
  - Net-of-fees P&L: spread + commission deducted per CLAUDE.md §1 cost model
  - Session-end auto-close enforced (CLAUDE.md §4)
  - Supports standard and 2× spread stress in a single pass

Run:
    python -m pipeline.03_replay_engine --symbol EURUSD --start 2020-01-01 --end 2025-01-01
    python -m pipeline.03_replay_engine --all
    python -m pipeline.03_replay_engine --all --stress   # runs both cost scenarios
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import polars as pl

from .config import (
    DATA_DIR,
    FEATURES_DIR,
    PHASE0_MIN_NET_PF,
    PHASE0_MIN_TRADES,
    PIP,
    SESSIONS,
    SIGNAL_CONFIG,
    SPREAD_STANDARD,
    SPREAD_STRESS_2X,
    SYMBOLS,
    SpreadConfig,
)
from session_smc.confirmation_entry import Signal, generate_signal_A

_UTC = timezone.utc


# ── Data loading ──────────────────────────────────────────────────────────────

def _load_tf(symbol: str, tf: str) -> Optional[pl.DataFrame]:
    """Load a timeframe Parquet, normalise timestamp column, return UTC-aware."""
    for fname in [f"{symbol}_{tf}.parquet", f"{symbol}_{tf}_raw.parquet"]:
        path = DATA_DIR / symbol / fname
        if path.exists():
            df = pl.read_parquet(path)
            if "time" in df.columns and "timestamp" not in df.columns:
                df = df.rename({"time": "timestamp"})
            df = df.with_columns(pl.col("timestamp").cast(pl.Datetime("us", "UTC")))
            return df.sort("timestamp")
    return None


def _df_to_candles(df: pl.DataFrame) -> list[dict]:
    """Polars frame → list[dict] with key 'time', UTC-aware datetimes."""
    if "timestamp" in df.columns and "time" not in df.columns:
        df = df.rename({"timestamp": "time"})
    rows = df.to_dicts()
    for r in rows:
        t = r.get("time")
        if isinstance(t, datetime) and t.tzinfo is None:
            r["time"] = t.replace(tzinfo=_UTC)
    return rows


def _slice_before(df: pl.DataFrame, ts: datetime) -> pl.DataFrame:
    """Bars whose timestamp is strictly before ts (bar CLOSED before ts)."""
    return df.filter(pl.col("timestamp") < ts)


def _slice_window(df: pl.DataFrame, t_open: datetime, t_close: datetime) -> pl.DataFrame:
    """Bars inside [t_open, t_close)."""
    return df.filter(
        (pl.col("timestamp") >= t_open) & (pl.col("timestamp") < t_close)
    )


# ── Trade outcome simulation ──────────────────────────────────────────────────

def _simulate_outcome(
    signal: Signal,
    m1_from_entry: list[dict],
    spread_cfg: SpreadConfig,
    session_end: datetime,
) -> dict:
    """
    Walk M1 bars forward from the entry bar close to determine trade outcome.

    Trade management (CLAUDE.md §4):
      TP1 = 4R → close 75%, move SL to breakeven
      TP2 = 5R → close remaining 25%
      Session end → close remainder at open of first bar at/after session end

    Costs deducted once as cost_in_r = total_cost_pips / sl_pips.
    """
    direction = signal.direction   # 'long' | 'short'
    entry     = signal.entry
    sl        = signal.sl
    tp1       = signal.tp1
    tp2       = signal.tp2
    sl_pips   = signal.sl_pips

    cost_in_r = spread_cfg.total_cost_pips / sl_pips if sl_pips > 0 else 0.0

    partial_closed = False  # True once TP1 hit
    sl_at_be       = False  # True once SL moved to breakeven
    gross_r        = 0.0
    exit_reason    = "DATA_END"
    exit_time: Optional[datetime] = None

    # Skip the entry bar itself (index 0) — we entered at its close
    for bar in m1_from_entry[1:]:
        bar_time = bar["time"]
        if isinstance(bar_time, str):
            bar_time = datetime.fromisoformat(bar_time.replace("Z", "+00:00"))
        if bar_time.tzinfo is None:
            bar_time = bar_time.replace(tzinfo=_UTC)

        h  = float(bar["high"])
        lo = float(bar["low"])

        # Session end: close remainder at bar open before any level check
        if bar_time >= session_end:
            exit_price = float(bar["open"])
            if direction == "long":
                exit_r_raw = (exit_price - entry) / (sl_pips * PIP)
            else:
                exit_r_raw = (entry - exit_price) / (sl_pips * PIP)
            gross_r = (0.75 * 4.0 + 0.25 * exit_r_raw) if partial_closed else exit_r_raw
            exit_reason = "SESSION_END"
            exit_time   = bar_time
            break

        current_sl = entry if sl_at_be else sl

        if direction == "long":
            # Pessimistic bar: assume SL can be hit before TP within same bar
            if lo <= current_sl:
                if sl_at_be:
                    gross_r     = 0.75 * 4.0 + 0.25 * 0.0  # runner exits at BE
                    exit_reason = "TP1_THEN_BE"
                else:
                    gross_r     = -1.0
                    exit_reason = "SL_HIT"
                exit_time = bar_time
                break

            if not partial_closed and h >= tp1:
                partial_closed = True
                sl_at_be       = True

            if partial_closed and h >= tp2:
                gross_r     = 0.75 * 4.0 + 0.25 * 5.0
                exit_reason = "TP2_HIT"
                exit_time   = bar_time
                break

        else:  # short
            if h >= current_sl:
                if sl_at_be:
                    gross_r     = 0.75 * 4.0 + 0.25 * 0.0
                    exit_reason = "TP1_THEN_BE"
                else:
                    gross_r     = -1.0
                    exit_reason = "SL_HIT"
                exit_time = bar_time
                break

            if not partial_closed and lo <= tp1:
                partial_closed = True
                sl_at_be       = True

            if partial_closed and lo <= tp2:
                gross_r     = 0.75 * 4.0 + 0.25 * 5.0
                exit_reason = "TP2_HIT"
                exit_time   = bar_time
                break

    if exit_time is None and m1_from_entry:
        # Ran out of M1 bars without resolving — use last close
        last = m1_from_entry[-1]
        exit_price = float(last["close"])
        if direction == "long":
            raw_r = (exit_price - entry) / (sl_pips * PIP)
        else:
            raw_r = (entry - exit_price) / (sl_pips * PIP)
        gross_r    = (0.75 * 4.0 + 0.25 * raw_r) if partial_closed else raw_r
        exit_time  = last["time"]

    net_r = gross_r - cost_in_r

    return {
        "gross_r":     round(gross_r, 4),
        "net_r":       round(net_r, 4),
        "cost_in_r":   round(cost_in_r, 4),
        "exit_reason": exit_reason,
        "exit_time":   exit_time,
        "tp1_hit":     partial_closed,
    }


# ── Per-symbol replay ─────────────────────────────────────────────────────────

def replay_symbol(
    symbol: str,
    start: date,
    end: date,
    spread_cfg: SpreadConfig,
    run_id: str,
) -> list[dict]:
    """
    Iterate day-by-day, session-by-session and run the full 11-phase AND-gate.
    Returns a list of trade dicts ready for PostgreSQL insertion.
    """
    df_h4  = _load_tf(symbol, "H4")
    df_h1  = _load_tf(symbol, "H1")
    df_m15 = _load_tf(symbol, "M15")
    df_m1  = _load_tf(symbol, "M1")

    if df_h4 is None or df_h1 is None or df_m15 is None:
        print(f"  [{symbol}] Missing required timeframe data (need H4, H1, M15)")
        return []

    if df_m1 is None:
        print(f"  [{symbol}] No M1 data — using M15 for outcome simulation (less precise)")
        df_m1 = df_m15

    trades: list[dict] = []
    current = start
    delta   = timedelta(days=1)

    while current <= end:
        d_start = datetime(current.year, current.month, current.day, tzinfo=_UTC)

        for sess in SESSIONS:
            t_open  = d_start.replace(hour=sess.open_utc)
            t_close = d_start.replace(hour=sess.close_utc)

            # Candles known BEFORE session open (no lookahead into session)
            h4_pre  = _df_to_candles(_slice_before(df_h4,  t_open))
            h1_pre  = _df_to_candles(_slice_before(df_h1,  t_open))

            if len(h4_pre) < 20 or len(h1_pre) < 20:
                continue  # not enough history for bias

            # 15M session bars: full session window (signal chain is bar-close safe)
            m15_sess = _df_to_candles(_slice_window(df_m15, t_open, t_close))
            if not m15_sess:
                continue

            # Run full 11-phase AND-gate
            signal = generate_signal_A(
                symbol=symbol,
                candles_4h=h4_pre,
                candles_1h=h1_pre,
                session_candles=m15_sess,
                session_name=sess.name,
                config=SIGNAL_CONFIG,
            )
            if signal is None:
                continue

            # Entry time = close time of the retest bar
            entry_bar = m15_sess[signal.retest_idx]
            entry_time = entry_bar["time"]
            if isinstance(entry_time, str):
                entry_time = datetime.fromisoformat(entry_time.replace("Z", "+00:00"))

            # M1 bars from entry bar close to session end + 2H buffer for runners
            m1_from_entry = _df_to_candles(
                _slice_window(df_m1, entry_time, t_close + timedelta(hours=2))
            )

            outcome = _simulate_outcome(signal, m1_from_entry, spread_cfg, t_close)

            trades.append({
                "trade_id":       f"{run_id}-{symbol}-{entry_time.isoformat()}",
                "run_id":         run_id,
                "symbol":         symbol,
                "session":        sess.name,
                "direction":      signal.direction,
                "setup_type":     signal.setup_type,
                "entry_time":     entry_time,
                "exit_time":      outcome["exit_time"],
                "entry_price":    signal.entry,
                "stop_price":     signal.sl,
                "tp1_price":      signal.tp1,
                "tp2_price":      signal.tp2,
                "sl_pips":        signal.sl_pips,
                "risk_reward":    signal.rr,
                "spread_cost_pips": spread_cfg.total_cost_pips,
                "cost_in_r":      outcome["cost_in_r"],
                "gross_result_r": outcome["gross_r"],
                "net_result_r":   outcome["net_r"],
                "exit_reason":    outcome["exit_reason"],
                "tp1_hit":        outcome["tp1_hit"],
                "session_high":   signal.session_range["high"],
                "session_low":    signal.session_range["low"],
                "session_range_pips": signal.session_range["range_pips"],
            })

        current += delta

    return trades


# ── Gate evaluation ───────────────────────────────────────────────────────────

def evaluate_gate(trades: list[dict], label: str) -> dict:
    """Compute PF and gate verdict for a trade set."""
    if not trades:
        return {"label": label, "n": 0, "pf": 0.0, "pass": False, "reason": "no trades"}

    net_rs = [t["net_result_r"] for t in trades]
    wins   = [r for r in net_rs if r > 0]
    losses = [r for r in net_rs if r <= 0]

    gross_profit = sum(wins)
    gross_loss   = abs(sum(losses))
    pf           = gross_profit / gross_loss if gross_loss > 0 else 0.0
    n            = len(trades)

    passed = n >= PHASE0_MIN_TRADES and pf > PHASE0_MIN_NET_PF

    return {
        "label":        label,
        "n":            n,
        "win_rate":     round(len(wins) / n * 100, 2),
        "net_pf":       round(pf, 3),
        "avg_net_r":    round(sum(net_rs) / n, 4),
        "total_net_r":  round(sum(net_rs), 2),
        "pass":         passed,
        "reason":       "PASS" if passed else f"n={n} (need {PHASE0_MIN_TRADES}), PF={pf:.3f} (need {PHASE0_MIN_NET_PF})",
    }


# ── CLI entry ─────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="ST-A2 Phase-0 Replay Engine")
    parser.add_argument("--symbol", choices=SYMBOLS, help="Single symbol")
    parser.add_argument("--all",    action="store_true")
    parser.add_argument("--start",  default="2020-01-01")
    parser.add_argument("--end",    default="2025-01-01")
    parser.add_argument("--stress", action="store_true",
                        help="Run both standard and 2x spread scenarios")
    args = parser.parse_args()

    targets = SYMBOLS if (args.all or not args.symbol) else [args.symbol]
    start   = date.fromisoformat(args.start)
    end     = date.fromisoformat(args.end)

    scenarios: list[tuple[str, dict]] = [("standard", SPREAD_STANDARD)]
    if args.stress:
        scenarios.append(("stress_2x", SPREAD_STRESS_2X))

    print("=" * 60)
    print("ST-A2 Phase-0 Replay Engine — deterministic, net-of-fees")
    print(f"Period: {start} → {end}")
    print(f"Symbols: {targets}")
    print("=" * 60)

    all_results: list[dict] = []

    for scenario_name, spread_map in scenarios:
        print(f"\n── Scenario: {scenario_name} ──")
        for sym in targets:
            run_id = f"ST-A-{sym}-{scenario_name}-{start}-{end}"
            print(f"\n{sym}  run_id={run_id}")
            trades = replay_symbol(sym, start, end, spread_map[sym], run_id)
            gate   = evaluate_gate(trades, f"{sym}/{scenario_name}")
            print(
                f"  n={gate['n']}  win_rate={gate['win_rate']}%  "
                f"net_PF={gate['net_pf']}  avg_R={gate['avg_net_r']}  "
                f"→ {'✅ PASS' if gate['pass'] else '❌ FAIL'}  ({gate['reason']})"
            )
            all_results.append({
                "run_id":    run_id,
                "symbol":    sym,
                "scenario":  scenario_name,
                "trades":    trades,
                "gate":      gate,
            })

    # Save to Parquet for 04_write_db.py to consume
    FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    replay_cache = FEATURES_DIR / "_replay_results.parquet"

    flat_trades: list[dict] = []
    for r in all_results:
        flat_trades.extend(r["trades"])

    if flat_trades:
        df_out = pl.DataFrame(flat_trades)
        df_out.write_parquet(replay_cache, compression="zstd")
        print(f"\nReplay cache → {replay_cache}  ({len(flat_trades):,} trades)")

    print("\nSummary")
    print("-" * 40)
    for r in all_results:
        g = r["gate"]
        mark = "✅" if g["pass"] else "❌"
        print(f"  {mark}  {g['label']}  n={g['n']}  PF={g['net_pf']}  {g['reason']}")


if __name__ == "__main__":
    main()

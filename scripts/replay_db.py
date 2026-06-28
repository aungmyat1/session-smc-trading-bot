"""
ST-A2 historical replay with PostgreSQL research database integration.

Reads Parquet data (falls back to CSV), runs the canonical ST-A2 signal chain,
simulates trades, and persists every result to:
    research.replay_runs
    research.trades
    market.smc_events
    analytics.daily_equity
    analytics.strategy_metrics

Usage:
    python scripts/replay_db.py
    python scripts/replay_db.py --symbol EURUSD --start 2020-01-01 --end 2025-12-31
    python scripts/replay_db.py --symbol EURUSD --start 2025-01-01 --end 2025-12-31 --dry-run
    python scripts/replay_db.py --symbol EURUSD --start 2020-01-01 --end 2025-12-31 --rr 3.0

DO NOT modify: strategy logic, risk rules, execution code, SL/TP calculation.
This script is measurement-only.
"""

import argparse
import csv
import logging
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)

from research_db.client import ResearchDB

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("replay_db")

DATA_DIR = ROOT / "data" / "historical"
DATA_PROC = ROOT / "data" / "processed"

_PIP = 0.0001
SPREAD_PIPS = {
    "EURUSD": {"standard": 1.4, "2x": 2.8},
    "GBPUSD": {"standard": 1.8, "2x": 3.6},
}
CSV_FILES = {
    "EURUSD": {"m15": "EUR_USD_M15.csv", "h4": "EUR_USD_H4.csv"},
    "GBPUSD": {"m15": "GBP_USD_M15.csv", "h4": "GBP_USD_H4.csv"},
}
MAX_BARS = 96   # 24h at M15


# ── Data loading ──────────────────────────────────────────────────────────────

def _load_parquet(sym: str, tf: str, start: str = None, end: str = None) -> list[dict]:
    try:
        import pandas as pd
        path = DATA_PROC / sym / f"{tf}.parquet"
        if not path.exists():
            return []
        df = pd.read_parquet(path, columns=["timestamp_utc", "open", "high", "low", "close", "volume"])
        df["time"] = pd.to_datetime(df["timestamp_utc"], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        if start:
            df = df[df["time"] >= start]
        if end:
            df = df[df["time"] <= end + "T23:59:59Z"]
        return df[["time", "open", "high", "low", "close", "volume"]].to_dict("records")
    except Exception:
        return []


def _load_csv(sym: str, tf: str, start: str = None, end: str = None) -> list[dict]:
    key = "m15" if tf == "M15" else "h4"
    path = DATA_DIR / CSV_FILES[sym][key]
    if not path.exists():
        return []
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            t = row["time"]
            if start and t < start:
                continue
            if end and t > end + "T23:59:59Z":
                break
            rows.append({
                "time":   t,
                "open":   float(row["open"]),
                "high":   float(row["high"]),
                "low":    float(row["low"]),
                "close":  float(row["close"]),
                "volume": float(row.get("volume", 0)),
            })
    return rows


def load_bars(sym: str, tf: str, start: str = None, end: str = None) -> list[dict]:
    bars = _load_parquet(sym, tf, start, end)
    if bars:
        log.info("Loaded %d %s %s bars from Parquet", len(bars), sym, tf)
        return bars
    bars = _load_csv(sym, tf, start, end)
    if bars:
        log.info("Loaded %d %s %s bars from CSV (Parquet not built)", len(bars), sym, tf)
    return bars


# ── Trade simulation (matches backtest_session_liquidity.py exactly) ──────────

def simulate_trade(entry, sl, side, rr, future_bars):
    risk = abs(entry - sl)
    if risk == 0:
        return "session_end", 0.0, entry, "", 0
    tp = (entry + risk * rr) if side == "long" else (entry - risk * rr)
    for i, bar in enumerate(future_bars[:MAX_BARS]):
        h, lo = float(bar["high"]), float(bar["low"])
        if side == "long":
            if lo <= sl:
                return "sl", -1.0, sl, bar["time"], i + 1
            if h >= tp:
                return "tp", rr, tp, bar["time"], i + 1
        else:
            if h >= sl:
                return "sl", -1.0, sl, bar["time"], i + 1
            if lo <= tp:
                return "tp", rr, tp, bar["time"], i + 1
    if future_bars:
        last = future_bars[min(MAX_BARS - 1, len(future_bars) - 1)]
        ep = float(last["close"])
        raw = (ep - entry) / risk if side == "long" else (entry - ep) / risk
        return "session_end", raw, ep, last["time"], min(MAX_BARS, len(future_bars))
    return "session_end", 0.0, entry, "", 0


def spread_cost_r(spread_pip, sl_pips):
    return spread_pip / sl_pips if sl_pips > 0 else 0.0


# ── SMC event extraction from debug records ───────────────────────────────────

def _parse_smc_events(events: list, run_id: str, symbol: str) -> list[dict]:
    smc_rows = []
    for ev in events:
        etype  = ev.get("event", "")
        detail = ev.get("detail", "")
        date   = ev.get("date", "")

        if etype == "SWEEP":
            m_bias = re.search(r"bias=(\w+)", detail)
            m_side = re.search(r"\] (\w+) side=", detail)
            m_time = re.search(r"\[(\d{2}:\d{2}) UTC\]", detail)
            m_lvl  = re.search(r"level=([\d.]+)", detail)
            sess   = m_side.group(1) if m_side else ""
            t_str  = f"{date}T{m_time.group(1)}:00Z" if m_time else f"{date}T00:00:00Z"
            smc_rows.append({
                "run_id":      run_id,
                "symbol":      symbol,
                "event_type":  "LIQUIDITY_SWEEP",
                "timeframe":   "M15",
                "event_time":  t_str,
                "direction":   m_bias.group(1) if m_bias else "",
                "price_level": float(m_lvl.group(1)) if m_lvl else None,
                "price_high":  None,
                "price_low":   None,
                "htf_bias":    m_bias.group(1) if m_bias else "",
                "session":     sess,
                "detail":      detail[:255],
            })
        elif etype in ("BOS", "CHOCH", "FVG"):
            smc_rows.append({
                "run_id":      run_id,
                "symbol":      symbol,
                "event_type":  etype,
                "timeframe":   "M15",
                "event_time":  f"{date}T00:00:00Z",
                "direction":   ev.get("direction", ""),
                "price_level": ev.get("level"),
                "price_high":  ev.get("high"),
                "price_low":   ev.get("low"),
                "htf_bias":    ev.get("bias", ""),
                "session":     ev.get("session", ""),
                "detail":      detail[:255],
            })
    return smc_rows


# ── Metrics calculation ───────────────────────────────────────────────────────

def compute_metrics(net_rs: list[float]) -> dict:
    if not net_rs:
        return {k: 0 for k in ["n", "wins", "losses", "win_rate", "avg_r",
                                 "pf", "total_r", "max_dd", "expectancy", "sharpe_r"]}
    wins   = [r for r in net_rs if r > 0]
    losses = [r for r in net_rs if r <= 0]
    gw = sum(wins)
    gl = abs(sum(losses))
    pf = gw / gl if gl > 0 else (float("inf") if gw > 0 else 1.0)
    avg = sum(net_rs) / len(net_rs)
    std = (sum((r - avg) ** 2 for r in net_rs) / len(net_rs)) ** 0.5
    sharpe = avg / std if std > 0 else 0.0

    peak = run = max_dd = 0.0
    for r in net_rs:
        run += r
        peak = max(peak, run)
        max_dd = max(max_dd, peak - run)

    return {
        "n": len(net_rs), "wins": len(wins), "losses": len(losses),
        "win_rate": len(wins) / len(net_rs),
        "avg_r": avg, "pf": pf, "total_r": sum(net_rs),
        "max_dd": max_dd, "expectancy": avg, "sharpe_r": round(sharpe, 3),
    }


def pct(v):  return f"{v * 100:.1f}%"
def pfmt(v): return "∞" if v == float("inf") else f"{v:.3f}"


# ── Daily equity curve ────────────────────────────────────────────────────────

def build_daily_equity(trades: list[dict], run_id: str, symbol: str) -> list[dict]:
    daily: dict[str, dict] = {}
    cum_r = 0.0
    for t in sorted(trades, key=lambda x: x["entry_time"] or ""):
        if not t["entry_time"]:
            continue
        day = str(t["entry_time"])[:10]
        if day not in daily:
            daily[day] = {"n": 0, "r": 0.0}
        daily[day]["n"] += 1
        daily[day]["r"] += t["result_r"]

    rows = []
    cum_r = 0.0
    for day in sorted(daily):
        cum_r += daily[day]["r"]
        rows.append({
            "run_id":       run_id,
            "trade_date":   day,
            "symbol":       symbol,
            "trades_today": daily[day]["n"],
            "daily_r":      round(daily[day]["r"], 4),
            "cumulative_r": round(cum_r, 4),
            "equity_curve": round(100.0 + cum_r * 2.0, 4),  # notional: 100 base + 2% per R
        })
    return rows


# ── Report writers ────────────────────────────────────────────────────────────

def write_baseline_report(run_id: str, trades: list, m_std: dict, m_stress: dict, sym: str, start: str, end: str):
    lines = [
        "# STA2 Baseline Report",
        f"Run ID: {run_id}",
        f"Symbol: {sym} | Period: {start} → {end} | RR: 3.0",
        f"Generated: {datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "",
        "## Core Metrics",
        "",
        "| Metric | Gross | Net (std) | Net (2× stress) |",
        "|---|---|---|---|",
    ]
    gross_rs = [t["gross_r"] for t in trades]
    m_gross = compute_metrics(gross_rs)
    for label, m in [("Trades (n)", None), ("Wins", None), ("Win Rate", None),
                     ("Avg R", None), ("PF", None), ("Max DD", None)]:
        pass

    lines += [
        f"| Trades (n) | {m_gross['n']} | {m_std['n']} | {m_stress['n']} |",
        f"| Win Rate | {pct(m_gross['win_rate'])} | {pct(m_std['win_rate'])} | {pct(m_stress['win_rate'])} |",
        f"| Profit Factor | {pfmt(m_gross['pf'])} | {pfmt(m_std['pf'])} | {pfmt(m_stress['pf'])} |",
        f"| Avg R | {m_gross['avg_r']:+.3f} | {m_std['avg_r']:+.3f} | {m_stress['avg_r']:+.3f} |",
        f"| Total R | {m_gross['total_r']:+.2f} | {m_std['total_r']:+.2f} | {m_stress['total_r']:+.2f} |",
        f"| Max DD | {m_gross['max_dd']:.2f}R | {m_std['max_dd']:.2f}R | {m_stress['max_dd']:.2f}R |",
        "",
        "## Monthly Breakdown (net std)",
        "",
        "| Month | Trades | WR | PF | Net R |",
        "|---|---|---|---|---|",
    ]
    monthly: dict[str, list] = {}
    for t in trades:
        mo = (t["entry_time"] or "")[:7]
        if mo:
            monthly.setdefault(mo, []).append(t["result_r"])
    for mo in sorted(monthly):
        m = compute_metrics(monthly[mo])
        lines.append(f"| {mo} | {m['n']} | {pct(m['win_rate'])} | {pfmt(m['pf'])} | {m['total_r']:+.2f}R |")

    (REPORTS / "STA2_BASELINE_REPORT.md").write_text("\n".join(lines))
    log.info("Written: STA2_BASELINE_REPORT.md")


def write_winner_loser_analysis(trades: list, run_id: str):
    winners = sorted([t for t in trades if t["gross_r"] > 0],
                     key=lambda t: -t["gross_r"])
    losers  = sorted([t for t in trades if t["gross_r"] <= 0],
                     key=lambda t: t["gross_r"])

    def _table(ts):
        if not ts:
            return ["| — | No trades | — | — | — | — |"]
        rows = ["| Date | Session | Dir | SL pip | Gross R | Net R (std) | Exit |",
                "|---|---|---|---|---|---|---|"]
        for t in ts[:20]:
            rows.append(
                f"| {(t['entry_time'] or '')[:10]} | {t['session']} | {t['direction']} "
                f"| {t['sl_pips']:.1f} | {t['gross_r']:+.2f} | {t['result_r']:+.3f} | {t['exit_reason']} |"
            )
        return rows

    w_lines = [f"# Winner Analysis | Run: {run_id}", "", "## Top Winners", ""] + _table(winners)
    l_lines = [f"# Loser Analysis | Run: {run_id}", "", "## All Losses", ""] + _table(losers)

    # Winner characteristics
    if winners:
        w_rs = [t["gross_r"] for t in winners]
        w_lines += ["", "## Winner Stats", f"- Count: {len(winners)}",
                    f"- Avg gross R: {sum(w_rs)/len(w_rs):.3f}",
                    f"- Max win: {max(w_rs):.3f}R",
                    f"- Sessions: London={sum(1 for t in winners if t['session']=='london')} "
                    f"NY={sum(1 for t in winners if t['session']=='new_york')}"]
    if losers:
        l_rs = [t["gross_r"] for t in losers]
        l_lines += ["", "## Loss Stats", f"- Count: {len(losers)}",
                    f"- Avg gross R: {sum(l_rs)/len(l_rs):.3f}",
                    f"- Max loss: {min(l_rs):.3f}R",
                    f"- Sessions: London={sum(1 for t in losers if t['session']=='london')} "
                    f"NY={sum(1 for t in losers if t['session']=='new_york')}"]

    (REPORTS / "WINNER_ANALYSIS.md").write_text("\n".join(w_lines))
    (REPORTS / "LOSER_ANALYSIS.md").write_text("\n".join(l_lines))
    log.info("Written: WINNER_ANALYSIS.md, LOSER_ANALYSIS.md")


def write_session_analysis(trades: list, run_id: str):
    london = [t for t in trades if t["session"] == "london"]
    ny     = [t for t in trades if t["session"] == "new_york"]

    def _stats(ts, name):
        if not ts:
            return [f"### {name}", "No trades."]
        m = compute_metrics([t["result_r"] for t in ts])
        m2 = compute_metrics([t["result_r_2x"] for t in ts])
        return [
            f"### {name}",
            "",
            "| Metric | Std spread | 2× stress |",
            "|---|---|---|",
            f"| Trades | {m['n']} | {m2['n']} |",
            f"| Win Rate | {pct(m['win_rate'])} | {pct(m2['win_rate'])} |",
            f"| PF | {pfmt(m['pf'])} | {pfmt(m2['pf'])} |",
            f"| Avg R | {m['avg_r']:+.3f} | {m2['avg_r']:+.3f} |",
            f"| Total R | {m['total_r']:+.2f} | {m2['total_r']:+.2f} |",
            f"| Max DD | {m['max_dd']:.2f}R | {m2['max_dd']:.2f}R |",
        ]

    lines = [f"# Session Analysis | Run: {run_id}", ""] + _stats(london, "London") + [""] + _stats(ny, "New York")

    # Direction breakdown per session
    lines += ["", "## Direction Breakdown", "", "| Session | Dir | n | WR | Avg R |", "|---|---|---|---|---|"]
    for sess, ts in [("london", london), ("new_york", ny)]:
        for dirn in ["long", "short"]:
            dt = [t for t in ts if t["direction"] == dirn]
            if dt:
                m = compute_metrics([t["result_r"] for t in dt])
                lines.append(f"| {sess} | {dirn} | {m['n']} | {pct(m['win_rate'])} | {m['avg_r']:+.3f} |")

    (REPORTS / "SESSION_ANALYSIS.md").write_text("\n".join(lines))
    log.info("Written: SESSION_ANALYSIS.md")


# ── Main replay ───────────────────────────────────────────────────────────────

def run_replay(symbol: str, start: str, end: str, rr: float, dry_run: bool, db: ResearchDB) -> str:
    from strategy.session_liquidity.session_strategy import run_strategy

    run_id = f"rdb_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:6]}"
    log.info("=== ST-A2 Replay | %s | %s → %s | RR=%.1f | run_id=%s ===", symbol, start, end, rr, run_id)

    # Load data — M15 needs context window before start for session bias
    ctx_start = f"{int(start[:4]) - 1}-{start[5:]}" if start else None  # 1yr prior for H4 context
    m15_bars = load_bars(symbol, "M15", ctx_start, end)
    h4_bars  = load_bars(symbol, "H4",  None, end)    # full H4 history for bias

    if not m15_bars or not h4_bars:
        log.error("No data loaded for %s — aborting", symbol)
        return run_id

    # Register run in DB
    if not dry_run:
        sp = SPREAD_PIPS.get(symbol, {"standard": 1.4, "2x": 2.8})
        db.save_run({
            "run_id": run_id, "strategy": "ST-A2 v1", "symbol": symbol,
            "start_date": start, "end_date": end, "data_source": "csv",
            "rr": rr, "spread_std_pip": sp["standard"], "spread_2x_pip": sp["2x"],
            "notes": f"CLI replay {symbol} {start}→{end}",
        })

    log.info("Running signal chain on %d M15 + %d H4 bars...", len(m15_bars), len(h4_bars))
    sigs, events = run_strategy(m15_bars, h4_bars, symbol, config={"rr": rr}, debug=True)

    # Filter to requested date range
    sigs_in_range = [s for s in sigs if start <= s.timestamp.strftime("%Y-%m-%d") <= end]
    log.info("Signals in range: %d / %d total", len(sigs_in_range), len(sigs))

    # Build time index on full M15 (for forward simulation)
    time_idx = {b["time"]: i for i, b in enumerate(m15_bars)}

    # Persist SMC events
    if not dry_run and events:
        smc_rows = _parse_smc_events(events, run_id, symbol)
        for smc_ev in smc_rows:
            db.save_smc_event(smc_ev)
        log.info("Saved %d SMC events", len(smc_rows))

    sp = SPREAD_PIPS.get(symbol, {"standard": 1.4, "2x": 2.8})
    std_sp    = sp["standard"]
    stress_sp = sp["2x"]

    trade_records = []

    for sig in sigs_in_range:
        sig_time = sig.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
        idx = time_idx.get(sig_time)
        if idx is None:
            log.warning("Signal bar not in M15 index: %s", sig_time)
            continue

        future = m15_bars[idx + 1:]
        exit_reason, gross_r, exit_p, exit_t, n_bars = simulate_trade(
            sig.entry, sig.stop_loss, sig.side, rr, future
        )

        sl_pips    = sig.risk_pips
        cost_std   = spread_cost_r(std_sp, sl_pips)
        cost_2x    = spread_cost_r(stress_sp, sl_pips)
        net_r_std  = gross_r - cost_std
        net_r_2x   = gross_r - cost_2x

        tp = sig.entry + abs(sig.entry - sig.stop_loss) * rr \
             if sig.side == "long" \
             else sig.entry - abs(sig.entry - sig.stop_loss) * rr

        trade = {
            "run_id":       run_id,
            "strategy_id":  "ST-A2",
            "symbol":       symbol,
            "timeframe":    "M15",
            "session":      sig.session,
            "direction":    sig.side,
            "entry_time":   sig_time,
            "exit_time":    exit_t or None,
            "entry_price":  round(sig.entry, 5),
            "stop_price":   round(sig.stop_loss, 5),
            "take_profit":  round(tp, 5),
            "sl_pips":      round(sl_pips, 1),
            "risk_reward":  rr,
            "gross_r":      round(gross_r, 4),
            "result_r":     round(net_r_std, 4),
            "result_r_2x":  round(net_r_2x, 4),
            "profit_loss":  round(net_r_std, 4),  # in R units
            "exit_reason":  exit_reason,
            "spread_pip":   round(std_sp, 2),
            "bars_held":    n_bars,
        }
        trade_records.append(trade)

        if not dry_run:
            db.save_trade(trade)

    log.info("Simulated %d trades", len(trade_records))

    # Compute metrics
    net_rs     = [t["result_r"]     for t in trade_records]
    stress_rs  = [t["result_r_2x"]  for t in trade_records]
    gross_rs   = [t["gross_r"]       for t in trade_records]
    m_std      = compute_metrics(net_rs)
    m_stress   = compute_metrics(stress_rs)

    log.info("n=%d WR=%s PF_std=%s PF_2x=%s MaxDD=%.2fR",
             m_std["n"], pct(m_std["win_rate"]), pfmt(m_std["pf"]),
             pfmt(m_stress["pf"]), m_std["max_dd"])

    # Session-level PF for metrics
    london_rs = [t["result_r"] for t in trade_records if t["session"] == "london"]
    ny_rs     = [t["result_r"] for t in trade_records if t["session"] == "new_york"]
    l_m = compute_metrics(london_rs)
    n_m = compute_metrics(ny_rs)

    if not dry_run:
        # Update run summary
        verdict = "PASS" if m_std["pf"] > 1.0 and m_stress["pf"] > 1.0 else "FAIL"
        db.update_run_summary(run_id, {
            "n_trades": m_std["n"], "win_rate": round(m_std["win_rate"], 4),
            "pf_std": round(m_std["pf"], 4) if m_std["pf"] != float("inf") else 99.99,
            "pf_2x": round(m_stress["pf"], 4) if m_stress["pf"] != float("inf") else 99.99,
            "avg_r": round(m_std["avg_r"], 4), "total_r": round(m_std["total_r"], 4),
            "max_dd": round(m_std["max_dd"], 4), "verdict": verdict,
        })

        # Daily equity curve
        equity_rows = build_daily_equity(trade_records, run_id, symbol)
        for row in equity_rows:
            db.save_daily_equity(row)
        log.info("Saved %d daily equity rows", len(equity_rows))

        # Strategy metrics
        db.save_strategy_metrics({
            "run_id":          run_id,
            "strategy":        "ST-A2",
            "symbol":          symbol,
            "period_start":    start,
            "period_end":      end,
            "total_trades":    m_std["n"],
            "wins":            m_std["wins"],
            "losses":          m_std["losses"],
            "win_rate":        round(m_std["win_rate"], 4),
            "profit_factor":   round(m_std["pf"], 4) if m_std["pf"] != float("inf") else 99.99,
            "pf_2x":           round(m_stress["pf"], 4) if m_stress["pf"] != float("inf") else 99.99,
            "expectancy":      round(m_std["expectancy"], 4),
            "max_drawdown":    round(m_std["max_dd"], 4),
            "total_r":         round(m_std["total_r"], 4),
            "avg_r":           round(m_std["avg_r"], 4),
            "sharpe_r":        round(m_std["sharpe_r"], 4),
            "session_london_pf": round(l_m["pf"], 4) if l_m["pf"] != float("inf") else 99.99,
            "session_ny_pf":   round(n_m["pf"], 4) if n_m["pf"] != float("inf") else 99.99,
        })

    # Write report files
    write_baseline_report(run_id, trade_records, m_std, m_stress, symbol, start, end)
    write_winner_loser_analysis(trade_records, run_id)
    write_session_analysis(trade_records, run_id)

    return run_id


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ST-A2 replay with PostgreSQL research DB")
    parser.add_argument("--symbol", default="EURUSD")
    parser.add_argument("--start",  default="2021-06-21")
    parser.add_argument("--end",    default="2025-12-31")
    parser.add_argument("--rr",     type=float, default=3.0)
    parser.add_argument("--dry-run", action="store_true", help="Run without writing to DB")
    args = parser.parse_args()

    db = ResearchDB()
    if not db.is_available() and not args.dry_run:
        log.warning("DB unavailable — running in dry-run mode")
        args.dry_run = True

    try:
        run_id = run_replay(args.symbol, args.start, args.end, args.rr, args.dry_run, db)
        log.info("Replay complete. run_id=%s  dry_run=%s", run_id, args.dry_run)
    finally:
        db.close()


if __name__ == "__main__":
    main()

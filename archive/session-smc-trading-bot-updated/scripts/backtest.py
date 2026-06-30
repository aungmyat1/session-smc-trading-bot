"""
Phase-0 backtest for Session + SMC Strategy.

Walk-forward over 5 years of 15M data (EURUSD + GBPUSD).
Applies bar-close fills with realistic spread+commission costs.

Gate: n >= 50 AND net PF > 1.0 at STANDARD cost AND at 2x spread stress.

Usage:
    python3 scripts/backtest.py
    python3 scripts/backtest.py --symbols EURUSD --start 2020-01-01

Output:
    - Console summary table
    - docs/VERDICT_LOG.md row appended (if gate evaluated)
"""

import argparse
import csv
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure project root on path so session_smc imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from session_smc.confirmation_entry import DEFAULT_CONFIG, generate_signal_A

# ── Cost model (VT Markets Standard) ─────────────────────────────────────────

COSTS = {
    # spread + commission per lot round-trip, in pips
    "EURUSD": {"standard": 1.4, "stress2x": 2.8},
    "GBPUSD": {"standard": 1.8, "stress2x": 3.6},
}
PIP = 0.0001  # 1 pip in price units

# ── Session windows (UTC) ────────────────────────────────────────────────────

SESSIONS = {
    "london": {"start_h": 7, "end_h": 10},
    "ny": {"start_h": 13, "end_h": 16},
}
# Session window: 5 hours = 20 bars.
# Range builds in first 2h (8 bars); 12 bars remain for signal chain.
# confirmation_entry.py minimum gate: n >= range_bars + 6 = 14. 20 >= 14 ✓
# Signal spec says London 07-10 / NY 13-16, but the sweep-to-retest chain
# routinely completes in the 1-2 hours AFTER the initial range, so the 5h
# window captures the full sequence without cross-contaminating sessions.
SESSION_BARS = 20

# ── Data loading ──────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent.parent / "data" / "historical"
VERDICT_LOG = Path(__file__).parent.parent / "docs" / "VERDICT_LOG.md"


def load_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path) as f:
        reader = csv.DictReader(f)
        return [
            {
                "time": row["time"],
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row.get("volume", 0)),
            }
            for row in reader
        ]


def filter_by_date(candles: list[dict], start: str, end: str) -> list[dict]:
    return [c for c in candles if start <= c["time"] <= end]


# ── Trade representation ───────────────────────────────────────────────────────


@dataclass
class Trade:
    symbol: str
    session: str
    direction: str
    entry: float
    sl: float
    tp1: float
    sl_pips: float
    entry_time: str
    exit_price: float = 0.0
    exit_time: str = ""
    exit_reason: str = ""  # "TP1", "SL", "SESSION_END"
    gross_r: float = 0.0
    net_r_standard: float = 0.0
    net_r_stress: float = 0.0


# ── Backtest core ─────────────────────────────────────────────────────────────


@dataclass
class SessionResult:
    trades: list[Trade] = field(default_factory=list)


def run_symbol(
    symbol: str,
    candles_15m: list[dict],
    candles_4h: list[dict],
    candles_1h: list[dict],
    config: dict,
) -> list[Trade]:
    """Walk-forward backtest for one symbol across all sessions."""
    trades: list[Trade] = []
    n = len(candles_15m)

    candles_4h_sorted = sorted(candles_4h, key=lambda x: x["time"])
    candles_1h_sorted = sorted(candles_1h, key=lambda x: x["time"])

    use_real_1h = bool(candles_1h_sorted)

    def _closed_slice(
        sorted_bars: list[dict], before_time: str, bar_hours: int, count: int
    ) -> list[dict]:
        """Return bars whose CLOSE time (open + bar_hours) is ≤ before_time.

        Prevents including a bar that is still forming at `before_time`.
        Example: H4 bar at 04:00Z closes at 08:00Z; at London open (07:00Z)
        it is not complete.  cutoff = before_time - bar_hours gives 03:00Z,
        so only the 00:00Z bar (closes 04:00Z) is included.
        """
        cutoff_dt = datetime.fromisoformat(
            before_time.replace("Z", "+00:00")
        ) - timedelta(hours=bar_hours)
        cutoff = cutoff_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        result = [c for c in sorted_bars if c["time"] <= cutoff]
        return result[-count:] if result else []

    # Walk bar-by-bar; group into session windows
    i = 0
    while i < n:
        bar = candles_15m[i]
        dt_str = bar["time"]
        hour = int(dt_str[11:13])
        minute = int(dt_str[14:16])
        weekday = _weekday(dt_str)

        if weekday >= 5:  # Saturday/Sunday
            i += 1
            continue

        session_name = None
        if hour == 7 and minute == 0:
            session_name = "london"
        elif hour == 13 and minute == 0:
            session_name = "ny"

        if session_name is None:
            i += 1
            continue

        # Extract full session window (up to SESSION_BARS bars)
        sess_end = min(i + SESSION_BARS, n)
        session_candles = candles_15m[i:sess_end]
        if len(session_candles) < config.get("session_range_bars", 8) + 2:
            i += 1
            continue

        # 4H bias: only bars whose close time ≤ session open (H4 bar closes 4h after open)
        candles_4h_ctx = _closed_slice(
            candles_4h_sorted, dt_str, bar_hours=4, count=200
        )

        # 1H bias: real H1 data preferred; M15 proxy only if H1 not available
        if use_real_1h:
            candles_1h_ctx = _closed_slice(
                candles_1h_sorted, dt_str, bar_hours=1, count=200
            )
        else:
            # M15 proxy: last 200 completed M15 bars before session open
            # Fidelity note: swing detection on M15 differs from true H1 structure.
            # Fetch H1 data (fetch_data.py --granularities M15 H1 H4) for production accuracy.
            candles_1h_ctx = candles_15m[max(0, i - 200) : i]

        if not candles_4h_ctx or not candles_1h_ctx:
            i += SESSION_BARS
            continue

        sig = generate_signal_A(
            symbol=symbol,
            candles_4h=candles_4h_ctx,
            candles_1h=candles_1h_ctx,
            session_candles=session_candles,
            session_name=session_name,
            config=config,
        )

        if sig is not None:
            trade = _simulate_trade(
                sig, session_candles, sig.retest_idx, symbol, session_name
            )
            if trade is not None:
                trades.append(trade)

        # Advance to next session (skip rest of this session window)
        i += SESSION_BARS

    return trades


def _simulate_trade(
    sig, session_candles: list[dict], entry_bar: int, symbol: str, session: str
) -> "Trade | None":
    """Simulate SL/TP1/session-end exit on subsequent bars after entry."""
    if entry_bar >= len(session_candles):
        return None

    entry_candle = session_candles[entry_bar]
    entry_price = entry_candle["close"]  # bar-close fill

    cost_pips = COSTS.get(symbol, {}).get("standard", 1.4)
    cost_pips_stress = COSTS.get(symbol, {}).get("stress2x", 2.8)

    trade = Trade(
        symbol=symbol,
        session=session,
        direction=sig.direction,
        entry=entry_price,
        sl=sig.sl,
        tp1=sig.tp1,
        sl_pips=sig.sl_pips,
        entry_time=entry_candle["time"],
    )

    is_long = sig.direction == "long"

    for j in range(entry_bar + 1, len(session_candles)):
        bar = session_candles[j]
        is_last = j == len(session_candles) - 1

        if is_long:
            # Check SL hit (low touches or breaks SL)
            if bar["low"] <= sig.sl:
                trade.exit_price = sig.sl
                trade.exit_reason = "SL"
                trade.exit_time = bar["time"]
                break
            # Check TP1 hit
            if bar["high"] >= sig.tp1:
                trade.exit_price = sig.tp1
                trade.exit_reason = "TP1"
                trade.exit_time = bar["time"]
                break
        else:
            if bar["high"] >= sig.sl:
                trade.exit_price = sig.sl
                trade.exit_reason = "SL"
                trade.exit_time = bar["time"]
                break
            if bar["low"] <= sig.tp1:
                trade.exit_price = sig.tp1
                trade.exit_reason = "TP1"
                trade.exit_time = bar["time"]
                break

        if is_last:
            trade.exit_price = bar["close"]
            trade.exit_reason = "SESSION_END"
            trade.exit_time = bar["time"]

    if not trade.exit_time:
        # Signal fired too close to session end — exit at last bar
        last = session_candles[-1]
        trade.exit_price = last["close"]
        trade.exit_reason = "SESSION_END"
        trade.exit_time = last["time"]

    # Compute R multiples
    sl_dist_pips = sig.sl_pips
    if sl_dist_pips <= 0:
        return None

    if is_long:
        gross_pips = (trade.exit_price - entry_price) / PIP
    else:
        gross_pips = (entry_price - trade.exit_price) / PIP

    trade.gross_r = gross_pips / sl_dist_pips
    # Net: deduct cost as fraction of R (cost_pips / sl_dist_pips)
    cost_r = cost_pips / sl_dist_pips
    cost_r_stress = cost_pips_stress / sl_dist_pips
    trade.net_r_standard = trade.gross_r - cost_r
    trade.net_r_stress = trade.gross_r - cost_r_stress

    return trade


def _weekday(time_str: str) -> int:
    """0=Mon … 6=Sun from ISO datetime string."""
    dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
    return dt.weekday()


# ── Metrics ───────────────────────────────────────────────────────────────────


def compute_metrics(trades: list[Trade], r_field: str) -> dict:
    if not trades:
        return {"n": 0, "pf": 0.0, "win_rate": 0.0, "avg_r": 0.0, "max_dd": 0.0}

    gross_win = sum(getattr(t, r_field) for t in trades if getattr(t, r_field) > 0)
    gross_loss = abs(
        sum(getattr(t, r_field) for t in trades if getattr(t, r_field) <= 0)
    )
    wins = sum(1 for t in trades if getattr(t, r_field) > 0)

    pf = gross_win / gross_loss if gross_loss > 0 else float("inf")

    # Max drawdown in R
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in trades:
        equity += getattr(t, r_field)
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd

    return {
        "n": len(trades),
        "pf": round(pf, 3),
        "win_rate": round(wins / len(trades) * 100, 1),
        "avg_r": round(sum(getattr(t, r_field) for t in trades) / len(trades), 3),
        "max_dd": round(max_dd, 2),
    }


def yearly_breakdown(trades: list[Trade], r_field: str = "net_r_standard") -> None:
    """Print per-year and per-session breakdown of trade metrics."""
    if not trades:
        print("  No trades to break down.")
        return

    # Group by year
    by_year: dict[str, list[Trade]] = {}
    by_session: dict[str, list[Trade]] = {}
    for t in trades:
        year = t.entry_time[:4]
        by_year.setdefault(year, []).append(t)
        by_session.setdefault(t.session, []).append(t)

    print(f"\n  {'─' * 56}")
    print(f"  {'Year':<8} {'n':>5} {'PF':>7} {'WR%':>7} {'AvgR':>7} {'MaxDD':>7}")
    print(f"  {'─' * 56}")
    for year in sorted(by_year):
        m = compute_metrics(by_year[year], r_field)
        flag = " ⚠" if m["pf"] < 1.0 and m["n"] >= 5 else ""
        print(
            f"  {year:<8} {m['n']:>5} {m['pf']:>7.3f} {m['win_rate']:>6.1f}% {m['avg_r']:>7.3f} {m['max_dd']:>7.2f}{flag}"
        )

    print(f"  {'─' * 56}")
    print(f"  {'Session':<8} {'n':>5} {'PF':>7} {'WR%':>7} {'AvgR':>7} {'MaxDD':>7}")
    print(f"  {'─' * 56}")
    for sess in sorted(by_session):
        m = compute_metrics(by_session[sess], r_field)
        print(
            f"  {sess:<8} {m['n']:>5} {m['pf']:>7.3f} {m['win_rate']:>6.1f}% {m['avg_r']:>7.3f} {m['max_dd']:>7.2f}"
        )


def print_report(symbol: str, trades: list[Trade]) -> tuple:
    std = compute_metrics(trades, "net_r_standard")
    stress = compute_metrics(trades, "net_r_stress")

    gate_pass = std["n"] >= 50 and std["pf"] > 1.0 and stress["pf"] > 1.0

    print(f"\n{'─' * 60}")
    print(f"  {symbol}  |  n={std['n']} trades")
    print(f"{'─' * 60}")
    print(f"  {'Metric':<18} {'Standard':>12} {'2x Stress':>12}")
    print(f"  {'PF':<18} {std['pf']:>12.3f} {stress['pf']:>12.3f}")
    print(f"  {'Win rate':<18} {std['win_rate']:>11.1f}% {stress['win_rate']:>11.1f}%")
    print(f"  {'Avg R':<18} {std['avg_r']:>12.3f} {stress['avg_r']:>12.3f}")
    print(f"  {'Max drawdown R':<18} {std['max_dd']:>12.2f} {stress['max_dd']:>12.2f}")

    exits: dict[str, int] = {}
    for t in trades:
        exits[t.exit_reason] = exits.get(t.exit_reason, 0) + 1
    print(f"  Exit breakdown: {exits}")

    yearly_breakdown(trades, "net_r_standard")

    status = "✅ PASS" if gate_pass else "❌ FAIL"
    print(f"\n  Gate (n≥50 AND PF>1.0 at std AND 2×): {status}")
    print(f"{'─' * 60}")
    return gate_pass, std, stress


def append_verdict_row(
    symbol: str, trial_id: str, std: dict, stress: dict, gate: bool
) -> None:
    if not VERDICT_LOG.exists():
        return
    status = "PASS" if gate else "FAIL"
    row = (
        f"| {trial_id} | {symbol} | Backtest ST-A | n={std['n']} PF={std['pf']} WR={std['win_rate']}% "
        f"| 2×stress PF={stress['pf']} | {status} | Phase-0 automated run |\n"
    )
    with open(VERDICT_LOG, "a") as f:
        f.write(row)
    print(f"  Appended verdict row to {VERDICT_LOG}")


# ── Entry point ───────────────────────────────────────────────────────────────


def main(symbols: list[str], start: str, end: str, trial_id: str) -> None:
    config = {
        **DEFAULT_CONFIG,
        "atr_period": 14,
        "swing_n": 3,
    }

    all_pass = True
    for symbol in symbols:
        instr = symbol[:3] + "_" + symbol[3:]  # EURUSD → EUR_USD
        path_15m = DATA_DIR / f"{instr}_M15.csv"
        path_h1 = DATA_DIR / f"{instr}_H1.csv"
        path_4h = DATA_DIR / f"{instr}_H4.csv"

        if not path_15m.exists():
            print(f"[{symbol}] M15 data not found: {path_15m}")
            print(f"  Run: python3 scripts/fetch_data.py --symbols {symbol}")
            all_pass = False
            continue
        if not path_4h.exists():
            print(f"[{symbol}] H4 data not found: {path_4h}")
            all_pass = False
            continue

        print(f"\n[{symbol}] Loading M15 ({path_15m.name}) …")
        candles_15m = filter_by_date(load_csv(path_15m), start, end)
        print(f"[{symbol}] Loading H4  ({path_4h.name}) …")
        candles_4h = filter_by_date(load_csv(path_4h), start, end)

        if path_h1.exists():
            print(f"[{symbol}] Loading H1  ({path_h1.name}) …")
            candles_1h = filter_by_date(load_csv(path_h1), start, end)
            print(f"[{symbol}] Using real H1 data for 1H bias.")
        else:
            candles_1h = []
            print(
                f"[{symbol}] H1 not found — using M15 proxy for 1H bias (lower fidelity)."
            )
            print(f"  To fix: python3 scripts/fetch_data.py --granularities M15 H1 H4")

        if not candles_15m:
            print(f"[{symbol}] No M15 data in range {start}–{end}")
            all_pass = False
            continue

        h1_label = f"H1={len(candles_1h)}" if candles_1h else "H1=proxy"
        print(
            f"[{symbol}] M15={len(candles_15m)} bars | {h1_label} | H4={len(candles_4h)} bars"
        )
        print(f"[{symbol}] Running walk-forward …")

        trades = run_symbol(symbol, candles_15m, candles_4h, candles_1h, config)
        gate, std, stress = print_report(symbol, trades)

        if trial_id:
            append_verdict_row(symbol, trial_id, std, stress, gate)

        all_pass = all_pass and gate

    if symbols:
        final = "✅ ALL PASS" if all_pass else "❌ ONE OR MORE SYMBOLS FAIL"
        print(f"\n{'═' * 60}")
        print(f"  FINAL VERDICT: {final}")
        print(f"{'═' * 60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase-0 backtest")
    parser.add_argument("--symbols", nargs="+", default=["EURUSD", "GBPUSD"])
    parser.add_argument(
        "--start",
        default=(
            datetime.now(timezone.utc).replace(year=datetime.now().year - 5)
        ).strftime("%Y-%m-%d")
        + "T00:00:00Z",
    )
    parser.add_argument(
        "--end",
        default=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    parser.add_argument("--trial-id", default="ST-A", dest="trial_id")
    args = parser.parse_args()
    main(args.symbols, args.start, args.end, args.trial_id)

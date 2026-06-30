#!/usr/bin/env python3
"""
VWAP mean-reversion backtest for the session portfolio.

Walks historical M15 data bar-by-bar, asks the VWAP adapter for a signal,
then simulates a simple bar-close trade with SL/TP and round-trip cost.

Defaults to the repo's EURUSD and GBPUSD history when available.
Output:
  - console summary
  - backtest_output_vwap_mean_reversion/report.json
  - backtest_output_vwap_mean_reversion/trades.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from strategies.adapters.vwap_adapter import VWAPMeanReversionAdapter

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "historical"
OUTDIR = ROOT / "backtest_output_vwap_mean_reversion"
OUTDIR.mkdir(exist_ok=True)

_SESSION_WINDOWS = {
    "london": (7, 10),
    "new_york": (13, 16),
}

_DEFAULT_COSTS = {
    "EURUSD": 1.4,
    "GBPUSD": 1.8,
    "USDJPY": 1.9,
    "XAUUSD": 3.0,
}

_PIP_SIZE = {
    "EURUSD": 0.0001,
    "GBPUSD": 0.0001,
    "USDJPY": 0.01,
    "XAUUSD": 0.1,
}


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _load_costs() -> dict[str, float]:
    path = ROOT / "config" / "costs.json"
    if not path.exists():
        return _DEFAULT_COSTS
    try:
        payload = json.loads(path.read_text())
        profile_name = payload.get("active_profile")
        profile = payload.get("profiles", {}).get(profile_name, {})
        costs = {}
        for symbol, default in _DEFAULT_COSTS.items():
            entry = profile.get(symbol, {})
            costs[symbol] = float(entry.get("standard", default) or default)
        return costs
    except Exception:
        return _DEFAULT_COSTS


def _load_portfolio_config() -> dict:
    path = ROOT / "config" / "strategy_portfolio.yaml"
    if not path.exists():
        return {}
    try:
        import yaml  # type: ignore

        return yaml.safe_load(path.read_text()) or {}
    except Exception:
        return {}


def _csv_path(symbol: str) -> Path:
    sym = symbol.replace("/", "").replace("_", "").upper()
    return DATA_DIR / f"{sym[:3]}_{sym[3:]}_M15.csv"


def _load_candles(symbol: str) -> list[dict]:
    path = _csv_path(symbol)
    if not path.exists():
        return []
    candles: list[dict] = []
    with path.open() as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            candles.append(
                {
                    "time": row["time"],
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": int(float(row.get("volume", 0) or 0)),
                }
            )
    candles.sort(key=lambda c: c["time"])
    return candles


def _session_name(hour: int) -> str:
    for name, (start, end) in _SESSION_WINDOWS.items():
        if start <= hour <= end:
            return name
    return ""


def _group_sessions(candles: list[dict]) -> dict[tuple[str, str], list[dict]]:
    sessions: dict[tuple[str, str], list[dict]] = {}
    for candle in candles:
        ts = _parse_time(candle["time"])
        day = ts.date().isoformat()
        sess = _session_name(ts.hour)
        if not sess:
            continue
        sessions.setdefault((day, sess), []).append(candle)
    return sessions


@dataclass
class TradeRow:
    symbol: str
    day: str
    session: str
    direction: str
    entry_time: str
    exit_time: str
    entry: float
    stop_loss: float
    take_profit: float
    exit_price: float
    exit_reason: str
    gross_r: float
    net_r: float
    cost_pips: float
    sl_pips: float
    strategy: str


def _simulate_trade(signal, session_bars: list[dict], cost_pips: float) -> TradeRow | None:
    entry_idx = None
    for idx, candle in enumerate(session_bars):
        if candle["time"] == signal.timestamp:
            entry_idx = idx
            break

    if entry_idx is None:
        entry_idx = max(0, len(session_bars) - 2)

    if entry_idx >= len(session_bars) - 1:
        return None

    entry_time = session_bars[entry_idx]["time"]
    is_long = signal.action == "BUY"
    exit_price = signal.take_profit
    exit_time = session_bars[-1]["time"]
    exit_reason = "SESSION_END"

    for bar in session_bars[entry_idx + 1:]:
        if is_long:
            if bar["low"] <= signal.stop_loss:
                exit_price = signal.stop_loss
                exit_time = bar["time"]
                exit_reason = "SL"
                break
            if bar["high"] >= signal.take_profit:
                exit_price = signal.take_profit
                exit_time = bar["time"]
                exit_reason = "TP"
                break
        else:
            if bar["high"] >= signal.stop_loss:
                exit_price = signal.stop_loss
                exit_time = bar["time"]
                exit_reason = "SL"
                break
            if bar["low"] <= signal.take_profit:
                exit_price = signal.take_profit
                exit_time = bar["time"]
                exit_reason = "TP"
                break

    pip = _PIP_SIZE.get(signal.symbol, 0.0001)
    sl_pips = abs(signal.entry_price - signal.stop_loss) / pip
    if sl_pips <= 0:
        return None
    risk = abs(signal.entry_price - signal.stop_loss)
    if risk <= 0:
        return None
    if is_long:
        gross_r = (exit_price - signal.entry_price) / risk
    else:
        gross_r = (signal.entry_price - exit_price) / risk
    net_r = gross_r - (cost_pips / sl_pips)

    return TradeRow(
        symbol=signal.symbol,
        day=signal.timestamp[:10],
        session=signal.session,
        direction=signal.action,
        entry_time=entry_time,
        exit_time=exit_time,
        entry=signal.entry_price,
        stop_loss=signal.stop_loss,
        take_profit=signal.take_profit,
        exit_price=exit_price,
        exit_reason=exit_reason,
        gross_r=round(gross_r, 3),
        net_r=round(net_r, 3),
        cost_pips=round(cost_pips, 2),
        sl_pips=round(sl_pips, 1),
        strategy=signal.strategy_name,
    )


def run_symbol(symbol: str, config: dict, costs: dict[str, float]) -> list[TradeRow]:
    candles = _load_candles(symbol)
    if not candles:
        return []

    sessions = _group_sessions(candles)
    adapter = VWAPMeanReversionAdapter()
    trades: list[TradeRow] = []

    # Use session-scoped data and stop after the first valid signal per session.
    for (day, session), session_bars in sorted(sessions.items()):
        if len(session_bars) < 12:
            continue

        params = config.get("strategies", {}).get("VWAPMeanReversion", {})
        signal = None
        for i in range(11, len(session_bars)):
            signal = adapter.generate_signal(
                {
                    "symbol": symbol,
                    "m15": session_bars[: i + 1],
                    "config": params,
                }
            )
            if signal is not None:
                break

        if signal is None:
            continue

        trade = _simulate_trade(signal, session_bars[i:], costs.get(symbol, _DEFAULT_COSTS[symbol]))
        if trade is not None:
            trades.append(trade)

    return trades


def _summary(trades: list[TradeRow]) -> dict:
    if not trades:
        return {"n": 0}

    gross = [t.gross_r for t in trades]
    net = [t.net_r for t in trades]
    wins = [r for r in gross if r > 0]
    losses = [r for r in gross if r <= 0]
    pf = (sum(wins) / abs(sum(losses))) if losses else math.inf
    net_wins = [r for r in net if r > 0]
    net_losses = [r for r in net if r <= 0]
    net_pf = (sum(net_wins) / abs(sum(net_losses))) if net_losses else math.inf
    days = {t.day for t in trades}

    return {
        "n": len(trades),
        "win_rate_pct": round((len(wins) / len(trades)) * 100, 1),
        "gross_pf": round(pf, 3) if pf != math.inf else "inf",
        "net_pf": round(net_pf, 3) if net_pf != math.inf else "inf",
        "avg_gross_r": round(sum(gross) / len(gross), 3),
        "avg_net_r": round(sum(net) / len(net), 3),
        "trades_per_day": round(len(trades) / max(len(days), 1), 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest VWAP mean reversion")
    parser.add_argument("--symbols", nargs="*", default=["EURUSD", "GBPUSD", "XAUUSD"])
    args = parser.parse_args()

    config = _load_portfolio_config()
    costs = _load_costs()
    all_trades: list[TradeRow] = []
    per_symbol: dict[str, dict] = {}

    for symbol in args.symbols:
        trades = run_symbol(symbol, config, costs)
        per_symbol[symbol] = _summary(trades)
        all_trades.extend(trades)
        if trades:
            print(f"{symbol}: n={len(trades)} win_rate={per_symbol[symbol]['win_rate_pct']}% net_pf={per_symbol[symbol]['net_pf']}")
        else:
            print(f"{symbol}: no trades")

    portfolio = _summary(all_trades)
    output = {
        "strategy": "VWAPMeanReversion",
        "symbols": args.symbols,
        "per_symbol": per_symbol,
        "portfolio": portfolio,
    }

    (OUTDIR / "report.json").write_text(json.dumps(output, indent=2))
    with (OUTDIR / "trades.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(all_trades[0]).keys()) if all_trades else [])
        if all_trades:
            writer.writeheader()
            for row in all_trades:
                writer.writerow(asdict(row))

    print(json.dumps(output, indent=2))
    print(f"Saved to {OUTDIR}")


if __name__ == "__main__":
    main()

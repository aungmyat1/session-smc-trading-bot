#!/usr/bin/env python3
"""
ST-A2 Trade Autopsy.

Analyze losing ST-A2 backtest trades and surface the weak point.

Default scope:
  - run_id: 20260621T100458-183aaa
  - rr:     5.0

Inputs:
  - research/trades.csv
  - data/historical/EUR_USD_M15.csv
  - data/historical/GBP_USD_M15.csv

Outputs:
  - reports/ST_A2_TRADE_AUTOPSY.md
  - reports/ST_A2_TRADE_AUTOPSY.csv

The report is intentionally conservative:
  - "Sweep type" is derived from trade direction (long → bullish sweep, short → bearish sweep).
  - "BOS quality" is a proxy derived from displacement candle strength and close position.
  - "FVG size" is derived from the 3-bar FVG rule already used elsewhere in this repo.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from strategy.session_liquidity.displacement_detector import \
    wilder_atr  # noqa: E402

TRADES_CSV = ROOT / "research" / "trades.csv"
REPORT_MD = ROOT / "reports" / "ST_A2_TRADE_AUTOPSY.md"
REPORT_CSV = ROOT / "reports" / "ST_A2_TRADE_AUTOPSY.csv"

HISTORICAL_FILES = {
    "EURUSD": ROOT / "data" / "historical" / "EUR_USD_M15.csv",
    "GBPUSD": ROOT / "data" / "historical" / "GBP_USD_M15.csv",
}

PIP_SIZE = {
    "EURUSD": 0.0001,
    "GBPUSD": 0.0001,
}

CANONICAL_RUN_ID = "20260621T100458-183aaa"
CANONICAL_RR = 5.0


@dataclass(frozen=True)
class TradeContext:
    trade_id: str
    run_id: str
    timestamp_utc: str
    symbol: str
    session: str
    side: str
    entry: float
    stop_loss: float
    take_profit: float
    sl_pips: float
    rr: float
    exit_price: float
    exit_reason: str
    bars_held: int
    gross_r: float
    spread_pips: float
    spread_cost_r: float
    net_r: float
    asian_high: float
    asian_low: float
    asian_range_pips: float
    htf_bias: str
    sweep_bar_time: str
    displacement_bar_time: str
    sweep_type: str
    atr_pips: float | None
    body_pips: float | None
    body_to_atr: float | None
    close_pos: float | None
    bos_quality: str
    fvg_size_pips: float | None
    fvg_atr_ratio: float | None
    fvg_quality: str
    primary_cause: str


def _parse_ts(raw: str) -> datetime:
    ts = raw.strip()
    if ts.endswith("Z"):
        ts = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(ts)


def _load_trade_rows(path: Path, run_id: str, rr: float) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("run_id") != run_id:
                continue
            try:
                if float(row.get("rr", "0")) != rr:
                    continue
            except ValueError:
                continue
            rows.append(row)
    return rows


def _load_bars(symbol: str) -> list[dict]:
    path = HISTORICAL_FILES.get(symbol)
    if path is None or not path.exists():
        raise FileNotFoundError(f"missing historical data for {symbol}: {path}")

    bars: list[dict] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            ts = _parse_ts(row["time"])
            bars.append(
                {
                    "time": ts,
                    "time_iso": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row.get("volume", 0) or 0),
                }
            )
    bars.sort(key=lambda b: b["time"])
    return bars


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    vals = sorted(values)
    if len(vals) == 1:
        return vals[0]
    k = (len(vals) - 1) * pct / 100.0
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return vals[int(k)]
    return vals[f] * (c - k) + vals[c] * (k - f)


def _bucket_from_threshold(
    value: float | None, low: float | None, high: float | None
) -> str:
    if value is None or low is None or high is None:
        return "unknown"
    if value < low:
        return "small"
    if value < high:
        return "medium"
    return "large"


def _bos_quality(side: str, body_to_atr: float | None, close_pos: float | None) -> str:
    if body_to_atr is None or close_pos is None:
        return "unknown"

    if side == "long":
        if body_to_atr >= 1.5 and close_pos >= 0.80:
            return "strong"
        if body_to_atr < 1.2 or close_pos < 0.65:
            return "weak"
        return "medium"

    if side == "short":
        if body_to_atr >= 1.5 and close_pos <= 0.20:
            return "strong"
        if body_to_atr < 1.2 or close_pos > 0.35:
            return "weak"
        return "medium"

    return "unknown"


def _fvg_context(
    bars: list[dict], idx: int, pip_size: float
) -> tuple[float | None, float | None, str]:
    if idx <= 0 or idx >= len(bars) - 1:
        return None, None, "unknown"

    prev_c = bars[idx - 1]
    disp_c = bars[idx]
    next_c = bars[idx + 1]

    if next_c["low"] > prev_c["high"]:
        size = (next_c["low"] - prev_c["high"]) / pip_size
        atr_v = disp_c.get("atr")
        ratio = (
            (next_c["low"] - prev_c["high"]) / atr_v if atr_v and atr_v > 0 else None
        )
        return round(size, 2), round(ratio, 3) if ratio is not None else None, "bullish"

    if next_c["high"] < prev_c["low"]:
        size = (prev_c["low"] - next_c["high"]) / pip_size
        atr_v = disp_c.get("atr")
        ratio = (
            (prev_c["low"] - next_c["high"]) / atr_v if atr_v and atr_v > 0 else None
        )
        return round(size, 2), round(ratio, 3) if ratio is not None else None, "bearish"

    return None, None, "none"


def _classify_primary_cause(
    session: str,
    spread_pips: float | None,
    spread_threshold: float | None,
    bos_quality: str,
    fvg_quality: str,
) -> str:
    if (
        spread_pips is not None
        and spread_threshold is not None
        and spread_pips >= spread_threshold
    ):
        return "large_spread"
    if bos_quality == "weak":
        return "weak_BOS"
    if fvg_quality == "small":
        return "small_FVG"
    if session == "new_york":
        return "NY_session"
    return "random"


def _build_contexts(rows: list[dict[str, str]]) -> list[TradeContext]:
    bars_cache: dict[str, list[dict]] = {}
    atr_cache: dict[str, list[float | None]] = {}
    idx_cache: dict[str, dict[str, int]] = {}

    contexts: list[TradeContext] = []
    for row in rows:
        symbol = row["symbol"]
        if symbol not in bars_cache:
            bars_cache[symbol] = _load_bars(symbol)
            atrs = wilder_atr(bars_cache[symbol], 14)
            atr_cache[symbol] = atrs
            idx_cache[symbol] = {
                bar["time_iso"]: i for i, bar in enumerate(bars_cache[symbol])
            }

        bars = bars_cache[symbol]
        atrs = atr_cache[symbol]
        idx_map = idx_cache[symbol]
        pip_size = PIP_SIZE.get(symbol, 0.0001)

        disp_time = row.get("displacement_bar_time") or row.get("sweep_bar_time") or ""
        idx = idx_map.get(disp_time)
        if idx is None:
            raise KeyError(
                f"could not locate displacement bar {disp_time} for {symbol}"
            )

        bar = bars[idx]
        atr = atrs[idx]
        atr_pips = round(atr / pip_size, 2) if atr and atr > 0 else None
        body_pips = round(abs(bar["close"] - bar["open"]) / pip_size, 2)
        body_to_atr = (
            round((abs(bar["close"] - bar["open"]) / atr), 3)
            if atr and atr > 0
            else None
        )
        candle_range = bar["high"] - bar["low"]
        close_pos = (
            round((bar["close"] - bar["low"]) / candle_range, 3)
            if candle_range > 0
            else None
        )
        bos_quality = _bos_quality(row["side"], body_to_atr, close_pos)
        fvg_size_pips, fvg_atr_ratio, _ = _fvg_context(bars, idx, pip_size)

        spread_pips = round(float(row["spread_cost_r"]) * float(row["sl_pips"]), 3)
        contexts.append(
            TradeContext(
                trade_id=row["trade_id"],
                run_id=row["run_id"],
                timestamp_utc=row["timestamp_utc"],
                symbol=symbol,
                session=row["session"],
                side=row["side"],
                entry=float(row["entry"]),
                stop_loss=float(row["stop_loss"]),
                take_profit=float(row["take_profit"]),
                sl_pips=float(row["sl_pips"]),
                rr=float(row["rr"]),
                exit_price=float(row["exit_price"]),
                exit_reason=row["exit_reason"],
                bars_held=int(float(row["bars_held"])),
                gross_r=float(row["gross_r"]),
                spread_pips=spread_pips,
                spread_cost_r=float(row["spread_cost_r"]),
                net_r=float(row["net_r"]),
                asian_high=float(row["asian_high"]),
                asian_low=float(row["asian_low"]),
                asian_range_pips=float(row["asian_range_pips"]),
                htf_bias=row["htf_bias"],
                sweep_bar_time=row["sweep_bar_time"],
                displacement_bar_time=disp_time,
                sweep_type="bullish" if row["side"] == "long" else "bearish",
                atr_pips=atr_pips,
                body_pips=body_pips,
                body_to_atr=body_to_atr,
                close_pos=close_pos,
                bos_quality=bos_quality,
                fvg_size_pips=fvg_size_pips,
                fvg_atr_ratio=fvg_atr_ratio,
                fvg_quality="unknown",
                primary_cause="",
            )
        )

    # Thresholds for the exclusive root-cause heuristic are derived from the full sample.
    fvg_sizes_all = [c.fvg_size_pips for c in contexts if c.fvg_size_pips is not None]
    fvg_q25_all = _percentile(fvg_sizes_all, 25)
    fvg_q75_all = _percentile(fvg_sizes_all, 75)
    for i, ctx in enumerate(contexts):
        if ctx.fvg_size_pips is not None:
            contexts[i] = TradeContext(
                **{
                    **ctx.__dict__,
                    "fvg_quality": _bucket_from_threshold(
                        ctx.fvg_size_pips, fvg_q25_all, fvg_q75_all
                    ),
                }
            )

    # Thresholds for the exclusive root-cause heuristic are derived from the loss set.
    loss_spreads = [
        c.spread_pips for c in contexts if c.net_r < 0 and c.spread_pips is not None
    ]
    spread_threshold = _percentile(loss_spreads, 75)

    fvg_sizes = [
        c.fvg_size_pips for c in contexts if c.net_r < 0 and c.fvg_size_pips is not None
    ]
    fvg_q25 = _percentile(fvg_sizes, 25)
    fvg_q75 = _percentile(fvg_sizes, 75)

    for i, ctx in enumerate(contexts):
        if ctx.net_r >= 0:
            continue
        fvg_bucket = _bucket_from_threshold(ctx.fvg_size_pips, fvg_q25, fvg_q75)
        contexts[i] = TradeContext(
            **{
                **ctx.__dict__,
                "primary_cause": _classify_primary_cause(
                    ctx.session,
                    ctx.spread_pips,
                    spread_threshold,
                    ctx.bos_quality,
                    fvg_bucket,
                ),
            }
        )

    return contexts


def _write_csv(path: Path, contexts: list[TradeContext]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(contexts[0].__dict__.keys()) if contexts else []
        )
        if contexts:
            writer.writeheader()
        for ctx in contexts:
            writer.writerow(ctx.__dict__)


def _pct(n: int, total: int) -> str:
    return f"{(n / total * 100.0):.1f}%" if total else "0.0%"


def _table_from_counter(title: str, counter: Counter, total: int) -> list[str]:
    lines = [f"### {title}", "", "| Bucket | Count | Share |", "|---|---:|---:|"]
    for key, count in counter.most_common():
        lines.append(f"| {key} | {count} | {_pct(count, total)} |")
    lines.append("")
    return lines


def _table_loss_rate(title: str, contexts: list[TradeContext], key_fn) -> list[str]:
    buckets: dict[str, list[float]] = {}
    for ctx in contexts:
        key = key_fn(ctx)
        row = buckets.setdefault(key, [0.0, 0.0, 0.0])  # trades, losses, net_r_sum
        row[0] += 1
        row[1] += 1 if ctx.net_r < 0 else 0
        row[2] += ctx.net_r

    lines = [
        f"### {title}",
        "",
        "| Bucket | Trades | Losses | Loss rate | Avg net R |",
        "|---|---:|---:|---:|---:|",
    ]
    for key, (trades, losses, net_r_sum) in sorted(
        buckets.items(), key=lambda kv: (-kv[1][1], kv[0])
    ):
        loss_rate = (losses / trades * 100.0) if trades else 0.0
        avg_net_r = (net_r_sum / trades) if trades else 0.0
        lines.append(
            f"| {key} | {int(trades)} | {int(losses)} | {loss_rate:.1f}% | {avg_net_r:+.3f}R |"
        )
    lines.append("")
    return lines


def _render_report(
    contexts: list[TradeContext],
    rows: list[dict[str, str]],
    run_id: str,
    rr: float,
) -> str:
    losses = [c for c in contexts if c.net_r < 0]
    wins = [c for c in contexts if c.net_r > 0]

    spread_values = [c.spread_pips for c in contexts if c.spread_pips is not None]
    spread_q25 = _percentile(spread_values, 25)
    spread_q50 = _percentile(spread_values, 50)
    spread_q75 = _percentile(spread_values, 75)

    _loss_spreads = [c.spread_pips for c in losses if c.spread_pips is not None]
    loss_bos = Counter(c.bos_quality for c in losses)
    loss_sessions = Counter(c.session for c in losses)
    loss_sweep_types = Counter(c.sweep_type for c in losses)
    loss_primary = Counter(c.primary_cause for c in losses)

    fvg_sizes = [c.fvg_size_pips for c in losses if c.fvg_size_pips is not None]
    fvg_q25 = _percentile(fvg_sizes, 25)
    fvg_q50 = _percentile(fvg_sizes, 50)
    fvg_q75 = _percentile(fvg_sizes, 75)

    bos_strengths = [c.body_to_atr for c in losses if c.body_to_atr is not None]
    bos_q25 = _percentile(bos_strengths, 25)
    bos_q50 = _percentile(bos_strengths, 50)
    bos_q75 = _percentile(bos_strengths, 75)

    lines: list[str] = []
    lines.extend(
        [
            "# ST-A2 Trade Autopsy",
            "",
            f"Scope: `run_id={run_id}` | `rr={rr}` | `trades={len(contexts)}` | `losses={len(losses)}` | `wins={len(wins)}`",
            "",
            "Methodology:",
            "- `Sweep type` is derived from trade direction: long = bullish sweep, short = bearish sweep.",
            "- `BOS quality` is a proxy from displacement body/ATR and close location, because the raw trade ledger does not store a separate BOS score.",
            "- `FVG size` is computed from the repo's 3-bar FVG rule around the displacement bar.",
            "",
            "## Executive Summary",
            "",
            f"- Loss rate: {len(losses)}/{len(contexts)} ({_pct(len(losses), len(contexts))})",
            f"- Median spread: {spread_q50:.2f} pips",
            f"- Median BOS strength proxy (body/ATR): {bos_q50:.3f}",
            f"- Median FVG size: {fvg_q50:.2f} pips",
            "",
            "## Loss Table",
            "",
            "| Trade ID | Session | Direction | Sweep type | BOS quality | FVG size (pips) | ATR (pips) | Spread (pips) | Result |",
            "|---|---|---|---|---|---:|---:|---:|---:|",
        ]
    )

    for ctx in losses:
        lines.append(
            f"| {ctx.trade_id} | {ctx.session} | {ctx.side} | {ctx.sweep_type} | {ctx.bos_quality} | "
            f"{ctx.fvg_size_pips if ctx.fvg_size_pips is not None else 'n/a'} | "
            f"{ctx.atr_pips if ctx.atr_pips is not None else 'n/a'} | "
            f"{ctx.spread_pips:.2f} | {ctx.net_r:+.3f}R |"
        )

    lines.extend(["", "## Breakdown By Dimension", ""])
    lines.extend(
        _table_from_counter("Primary Cause Heuristic", loss_primary, len(losses))
    )
    lines.extend(_table_from_counter("Session", loss_sessions, len(losses)))
    lines.extend(_table_from_counter("Sweep Type", loss_sweep_types, len(losses)))
    lines.extend(_table_from_counter("BOS Quality", loss_bos, len(losses)))

    spread_buckets = Counter(
        _bucket_from_threshold(c.spread_pips, spread_q25, spread_q75) for c in losses
    )
    lines.extend(_table_from_counter("Spread Bucket", spread_buckets, len(losses)))

    fvg_buckets = Counter(
        _bucket_from_threshold(c.fvg_size_pips, fvg_q25, fvg_q75) for c in losses
    )
    lines.extend(_table_from_counter("FVG Size Bucket", fvg_buckets, len(losses)))

    bos_buckets = Counter(
        _bucket_from_threshold(c.body_to_atr, bos_q25, bos_q75) for c in losses
    )
    lines.extend(
        _table_from_counter("BOS Strength Proxy Bucket", bos_buckets, len(losses))
    )

    lines.extend(
        [
            "## Loss Rate By Dimension",
            "",
        ]
    )
    lines.extend(_table_loss_rate("Session Loss Rate", contexts, lambda c: c.session))
    lines.extend(
        _table_loss_rate("Sweep Type Loss Rate", contexts, lambda c: c.sweep_type)
    )
    lines.extend(
        _table_loss_rate("BOS Quality Loss Rate", contexts, lambda c: c.bos_quality)
    )
    lines.extend(
        _table_loss_rate(
            "Spread Bucket Loss Rate",
            contexts,
            lambda c: _bucket_from_threshold(c.spread_pips, spread_q25, spread_q75),
        )
    )
    lines.extend(
        _table_loss_rate("FVG Quality Loss Rate", contexts, lambda c: c.fvg_quality)
    )

    lines.extend(
        [
            "## Takeaway",
            "",
            "The autopsy is intentionally exclusive at the `Primary Cause Heuristic` level, while the other tables are dimension-wise breakdowns.",
            "Use the primary cause to decide what to improve first; use the dimension tables to verify whether the issue clusters around session timing, spread, or weak confirmation.",
            "",
        ]
    )

    if loss_sessions:
        top_session = loss_sessions.most_common(1)[0]
        lines.append(
            f"Largest session loss cluster: **{top_session[0]}** ({top_session[1]}/{len(losses)} losses, {_pct(top_session[1], len(losses))})."
        )
        lines.append("")

    if loss_primary:
        top = loss_primary.most_common(1)[0]
        lines.append(
            f"Most likely improvement target: **{top[0]}** ({top[1]}/{len(losses)} losses, {_pct(top[1], len(losses))})."
        )
        lines.append("")

    lines.extend(
        [
            "## Notes",
            "",
            f"- Spread bucket thresholds are derived from the full {len(contexts)}-trade sample: q25={spread_q25:.2f}, q50={spread_q50:.2f}, q75={spread_q75:.2f}.",
            f"- BOS proxy thresholds (body/ATR): q25={bos_q25:.3f}, q50={bos_q50:.3f}, q75={bos_q75:.3f}.",
            f"- FVG thresholds: q25={fvg_q25:.2f} pips, q50={fvg_q50:.2f} pips, q75={fvg_q75:.2f} pips.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate the ST-A2 trade autopsy report"
    )
    parser.add_argument("--run-id", default=CANONICAL_RUN_ID)
    parser.add_argument("--rr", type=float, default=CANONICAL_RR)
    parser.add_argument("--trades-csv", type=Path, default=TRADES_CSV)
    parser.add_argument("--report-md", type=Path, default=REPORT_MD)
    parser.add_argument("--report-csv", type=Path, default=REPORT_CSV)
    args = parser.parse_args()

    rows = _load_trade_rows(args.trades_csv, args.run_id, args.rr)
    if not rows:
        print(f"[ERROR] No rows found for run_id={args.run_id} rr={args.rr}")
        return 1

    contexts = _build_contexts(rows)
    _write_csv(args.report_csv, contexts)
    report = _render_report(contexts, rows, args.run_id, args.rr)
    args.report_md.parent.mkdir(parents=True, exist_ok=True)
    args.report_md.write_text(report, encoding="utf-8")

    losses = sum(1 for c in contexts if c.net_r < 0)
    print(f"[OK] wrote {args.report_md}")
    print(f"[OK] wrote {args.report_csv}")
    print(f"[OK] trades={len(contexts)} losses={losses}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

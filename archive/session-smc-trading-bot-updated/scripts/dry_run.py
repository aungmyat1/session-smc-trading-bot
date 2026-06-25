#!/usr/bin/env python3
"""
VALIDATION-01 — Single-day dry run of the Session Liquidity signal chain.

Usage:
    python3 scripts/dry_run.py --date 2023-03-14 --symbol EURUSD
    python3 scripts/dry_run.py --date 2023-03-14           # both pairs

Outputs:
    - Console timeline with all gate decisions
    - docs/DRY_RUN_<DATE>.md  audit report

Modules used: SA-01 session_builder, SA-02 bias_filter, SA-04 sweep_detector,
SA-05 displacement_detector.

No trade execution. No order placement. Audit mode only.
"""

import argparse
import csv
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

# ── Path setup ────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from strategy.session_liquidity.session_builder import (
    AsianRange,
    build_asian_range,
    classify_session,
)
from strategy.session_liquidity.bias_filter import htf_bias
from strategy.session_liquidity.sweep_detector import detect_sweep, SweepResult
from strategy.session_liquidity.displacement_detector import (
    detect_displacement,
    wilder_atr as _wilder_atr_module,
)

_UTC = timezone.utc
_EST = ZoneInfo("America/New_York")
_DATA = _ROOT / "data" / "historical"
_DOCS = _ROOT / "docs"

# ── Config (mirrors DEFAULT_CONFIG from session_strategy.py spec) ─────────────
RR_LIST = [2, 3, 4, 5]
SL_BUFFER_PIPS = 2
DISPLACEMENT_ATR_MULT = 1.2
ATR_PERIOD = 14
MIN_RANGE_PIPS = {"EUR_USD": 15, "GBP_USD": 20}
SWEEP_TIMEOUT_BARS = 4   # bars after sweep before setup is cancelled

# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_utc(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _load_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["open"]  = float(r["open"])
        r["high"]  = float(r["high"])
        r["low"]   = float(r["low"])
        r["close"] = float(r["close"])
    return rows


def _symbol_file(symbol: str, tf: str) -> Path:
    # EURUSD → EUR_USD_M15.csv
    prefix = symbol[:3] + "_" + symbol[3:]
    return _DATA / f"{prefix}_{tf}.csv"


def _wilder_atr(candles: list[dict], period: int = ATR_PERIOD) -> list[float | None]:
    return _wilder_atr_module(candles, period)


def _detect_displacement_inline(
    candle: dict,
    atr: float | None,
    direction: str,
    mult: float = DISPLACEMENT_ATR_MULT,
) -> tuple[bool, str]:
    r = detect_displacement(candle, atr, direction, mult)
    return r.detected, r.reason


# ── Signal chain ──────────────────────────────────────────────────────────────

class GateResult:
    def __init__(self, gate: str, passed: bool, value: str, detail: str = ""):
        self.gate = gate
        self.passed = passed
        self.value = value
        self.detail = detail

    def icon(self) -> str:
        return "✅" if self.passed else "❌"

    def __str__(self) -> str:
        suffix = f" | {self.detail}" if self.detail else ""
        return f"{self.icon()} [{self.gate}] {self.value}{suffix}"


def run_dry_run(symbol: str, trade_date: date) -> dict:
    """
    Execute the full signal chain for one symbol on one date.
    Returns a structured result dict.
    """
    csv_sym = symbol[:3] + "_" + symbol[3:]
    m15_path = _symbol_file(symbol, "M15")
    h4_path  = _symbol_file(symbol, "H4")

    gates: list[GateResult] = []
    log: list[tuple[str, str, str]] = []  # (time_utc, event, detail)

    def gate(name, passed, value, detail=""):
        g = GateResult(name, passed, value, detail)
        gates.append(g)
        return g

    def logline(time_utc, event, detail=""):
        log.append((time_utc, event, detail))

    # ── Load data ─────────────────────────────────────────────────────────────
    all_m15 = _load_csv(m15_path)
    all_h4  = _load_csv(h4_path)

    if not all_m15:
        return {"symbol": symbol, "date": str(trade_date), "error": f"No M15 data at {m15_path}"}
    if not all_h4:
        return {"symbol": symbol, "date": str(trade_date), "error": f"No H4 data at {h4_path}"}

    # Pre-compute ATR for all M15 bars
    all_m15_sorted = sorted(all_m15, key=lambda c: c["time"])
    m15_atrs = _wilder_atr(all_m15_sorted)
    m15_atr_map = {c["time"]: atr for c, atr in zip(all_m15_sorted, m15_atrs)}

    # ── GATE 1: Asian Range ───────────────────────────────────────────────────
    asian = build_asian_range(all_m15, trade_date)
    logline("pre-London", "Asian session scan", f"date={trade_date}")

    if not asian:
        gate("Asian Range", False, "None", "< 4 M15 bars in 18:00–02:00 EST window")
        return _build_result(symbol, trade_date, gates, log, asian=None)

    gate("Asian Range", True,
         f"H={asian.high:.5f}  L={asian.low:.5f}  ({asian.range_pips:.1f} pips)")
    logline("pre-London", "Asian Range built",
            f"high={asian.high:.5f}  low={asian.low:.5f}  range={asian.range_pips:.1f}pip")

    # ── GATE 2: Minimum range filter ─────────────────────────────────────────
    min_pips = MIN_RANGE_PIPS.get(csv_sym, 15)
    range_ok = asian.range_pips >= min_pips
    gate("Min Range",
         range_ok,
         f"{asian.range_pips:.1f} pips vs {min_pips} pip minimum")
    if not range_ok:
        return _build_result(symbol, trade_date, gates, log, asian=asian)

    # ── Session bar loop ──────────────────────────────────────────────────────
    # Filter to London + NY killzone bars on trade_date
    session_bars = [
        c for c in all_m15_sorted
        if classify_session(_parse_utc(c["time"])) is not None
        and _parse_utc(c["time"]).date() == trade_date
    ]

    trade_signals: list[dict] = []
    session_traded: set[str] = set()
    pending_sweep: dict | None = None   # {"sweep_result", "bar_time", "bar_idx", "session", "atr"}

    for idx, candle in enumerate(all_m15_sorted):
        bar_time = _parse_utc(candle["time"])
        if bar_time.date() != trade_date:
            continue

        session = classify_session(bar_time)
        if session is None:
            continue

        bar_label = bar_time.strftime("%H:%M UTC")

        # ── GATE 3: HTF Bias (evaluated fresh each bar) ───────────────────────
        bias = htf_bias(all_h4, bar_time)

        if idx == session_bars.index(candle) + (len(all_m15_sorted) - len(session_bars)):
            pass  # logged below per bar

        # ── GATE 4: One trade per session ─────────────────────────────────────
        if session in session_traded:
            continue

        # ── Sweep check ───────────────────────────────────────────────────────
        if pending_sweep is None:
            # Check this candle for a fresh sweep
            sweep_result = detect_sweep(candle, asian.high, asian.low, bias)

            if sweep_result.detected:
                pending_sweep = {
                    "sweep": sweep_result,
                    "bar_time": bar_time,
                    "bar_idx": idx,
                    "session": session,
                    "atr": m15_atr_map.get(candle["time"]),
                }
                logline(
                    bar_label,
                    f"SWEEP DETECTED ({sweep_result.side.upper()})",
                    f"sweep_price={sweep_result.sweep_price:.5f}  bias={bias}",
                )
            else:
                logline(
                    bar_label,
                    f"No sweep  [{sweep_result.reason}]",
                    f"H={candle['high']:.5f} L={candle['low']:.5f} C={candle['close']:.5f}  bias={bias}",
                )

        else:
            # We have a pending sweep — look for displacement on this bar
            bars_since_sweep = idx - pending_sweep["bar_idx"]

            if bars_since_sweep > SWEEP_TIMEOUT_BARS:
                logline(bar_label, "Sweep TIMEOUT",
                        f"no displacement in {SWEEP_TIMEOUT_BARS} bars — setup cancelled")
                pending_sweep = None
                continue

            sweep = pending_sweep["sweep"]
            atr = m15_atr_map.get(candle["time"])
            is_disp, disp_reason = _detect_displacement_inline(candle, atr, sweep.side)

            if is_disp:
                # ── ENTRY CALCULATION ─────────────────────────────────────────
                entry = candle["close"]
                buf = SL_BUFFER_PIPS * 0.0001

                if sweep.side == "long":
                    sl = sweep.sweep_price - buf
                else:
                    sl = sweep.sweep_price + buf

                sl_dist = abs(entry - sl)
                sl_pips = round(sl_dist / 0.0001, 1)

                if sl_dist <= 0:
                    logline(bar_label, "ENTRY REJECTED",
                            f"degenerate SL distance ({sl_dist:.6f}) — signal dropped")
                    pending_sweep = None
                    continue

                tps = {rr: (entry + rr * sl_dist if sweep.side == "long"
                             else entry - rr * sl_dist)
                       for rr in RR_LIST}

                sig = {
                    "session":     pending_sweep["session"],
                    "side":        sweep.side,
                    "sweep_bar":   pending_sweep["bar_time"].strftime("%H:%M UTC"),
                    "disp_bar":    bar_label,
                    "entry":       entry,
                    "stop_loss":   sl,
                    "sl_pips":     sl_pips,
                    "take_profits": tps,
                    "sweep_price": sweep.sweep_price,
                    "atr":         atr,
                    "bias":        bias,
                    "disp_reason": disp_reason,
                    "candle":      candle,
                }
                trade_signals.append(sig)
                session_traded.add(pending_sweep["session"])
                pending_sweep = None

                logline(bar_label, "DISPLACEMENT CONFIRMED → SIGNAL GENERATED",
                        f"entry={entry:.5f}  sl={sl:.5f}  ({sl_pips:.1f}pip)")

            else:
                logline(bar_label, f"Displacement pending [{bars_since_sweep}/{SWEEP_TIMEOUT_BARS}]",
                        f"reject: {disp_reason}  H={candle['high']:.5f} L={candle['low']:.5f}")

    # Build gate summary from last-evaluated bias (use the last session bar)
    if session_bars:
        last_bar_time = _parse_utc(session_bars[-1]["time"])
        final_bias = htf_bias(all_h4, last_bar_time)
    else:
        final_bias = "neutral"

    gate("HTF Bias",
         final_bias != "neutral",
         final_bias,
         "4H swing structure (HH+HL / LH+LL)")

    return _build_result(
        symbol, trade_date, gates, log, asian=asian,
        bias=final_bias, signals=trade_signals,
        session_bars=session_bars, all_m15=all_m15_sorted,
    )


def _build_result(
    symbol, trade_date, gates, log, asian=None,
    bias=None, signals=None, session_bars=None, all_m15=None,
):
    return {
        "symbol":       symbol,
        "date":         str(trade_date),
        "asian":        asian,
        "bias":         bias,
        "gates":        gates,
        "log":          log,
        "signals":      signals or [],
        "session_bars": session_bars or [],
    }


# ── Report generator ──────────────────────────────────────────────────────────

def _fmt_tp_table(sig: dict) -> str:
    lines = []
    for rr, tp in sig["take_profits"].items():
        dist_pips = round(abs(tp - sig["entry"]) / 0.0001, 1)
        lines.append(f"| RR {rr} | `{tp:.5f}` | {dist_pips:.1f} pip |")
    return "\n".join(lines)


def generate_report(results: list[dict], trade_date: date) -> str:
    date_str = trade_date.strftime("%Y-%m-%d")
    lines = [
        f"# DRY_RUN_{date_str.replace('-', '_')}.md",
        f"# VALIDATION-01 — Session Liquidity Dry Run: {date_str}",
        f"# Audit mode only. No trades executed.",
        "",
        "---",
        "",
        "## Run Parameters",
        "",
        "| Parameter | Value |",
        "|---|---|",
        f"| Date | {date_str} |",
        f"| Symbols | {', '.join(r['symbol'] for r in results)} |",
        f"| ATR period | {ATR_PERIOD} (Wilder's, M15) |",
        f"| Displacement mult | {DISPLACEMENT_ATR_MULT}× ATR |",
        f"| SL buffer | {SL_BUFFER_PIPS} pips |",
        f"| Sweep timeout | {SWEEP_TIMEOUT_BARS} bars |",
        f"| Min range EUR | {MIN_RANGE_PIPS['EUR_USD']} pips |",
        f"| Min range GBP | {MIN_RANGE_PIPS['GBP_USD']} pips |",
        "",
        "---",
        "",
    ]

    for result in results:
        sym = result["symbol"]
        lines += [f"## {sym}", ""]

        if "error" in result:
            lines += [f"**ERROR:** {result['error']}", ""]
            continue

        asian = result["asian"]
        bias  = result["bias"]

        # ── Phase 1: Asian Range ───────────────────────────────────────────────
        lines += [
            "### Phase 1 — Asian Session Range",
            "",
            "| | Value |",
            "|---|---|",
        ]
        if asian:
            lines += [
                f"| Asian High | `{asian.high:.5f}` |",
                f"| Asian Low  | `{asian.low:.5f}` |",
                f"| Range      | {asian.range_pips:.1f} pips |",
            ]
        else:
            lines += ["| Result | No Asian range (< 4 bars) |"]
        lines += [""]

        # ── Phase 2: HTF Bias ─────────────────────────────────────────────────
        bias_icon = "✅" if bias and bias != "neutral" else "❌"
        lines += [
            "### Phase 2 — 4H Bias Filter",
            "",
            f"{bias_icon} **Bias: {bias or 'N/A'}**",
            "",
        ]

        # ── Gate Decision Tree ─────────────────────────────────────────────────
        lines += [
            "### Gate Decision Tree",
            "",
        ]
        for g in result["gates"]:
            lines.append(f"- {g}")
        lines += [""]

        # ── Timeline ──────────────────────────────────────────────────────────
        lines += [
            "### Intraday Timeline",
            "",
            "| Time (UTC) | Event | Detail |",
            "|---|---|---|",
        ]
        for (ts, event, detail) in result["log"]:
            detail_escaped = detail.replace("|", "∣")
            lines.append(f"| {ts} | {event} | {detail_escaped} |")
        lines += [""]

        # ── Signals ───────────────────────────────────────────────────────────
        if result["signals"]:
            for i, sig in enumerate(result["signals"], 1):
                side_icon = "🟢 LONG" if sig["side"] == "long" else "🔴 SHORT"
                lines += [
                    f"### Signal {i} — {sig['session'].upper()} — {side_icon}",
                    "",
                    "#### Entry Details",
                    "",
                    "| Field | Value |",
                    "|---|---|",
                    f"| Session | {sig['session']} |",
                    f"| Side | {sig['side']} |",
                    f"| HTF Bias | {sig['bias']} |",
                    f"| Sweep bar | {sig['sweep_bar']} |",
                    f"| Sweep price | `{sig['sweep_price']:.5f}` |",
                    f"| Displacement bar | {sig['disp_bar']} |",
                    f"| ATR (M15) | `{sig['atr']:.5f}`  ({sig['atr']/0.0001:.2f} pips) |" if sig['atr'] else "| ATR | N/A |",
                    f"| **Entry price** | **`{sig['entry']:.5f}`** |",
                    f"| **Stop Loss** | **`{sig['stop_loss']:.5f}`** ({sig['sl_pips']:.1f} pip) |",
                    "",
                    "#### Take Profit Levels",
                    "",
                    "| Risk-Reward | Price | Distance |",
                    "|---|---|---|",
                ]
                lines.append(_fmt_tp_table(sig))
                lines += [
                    "",
                    "#### Displacement Confirmation",
                    "",
                    f"- Candle: H={sig['candle']['high']:.5f}  L={sig['candle']['low']:.5f}  "
                    f"O={sig['candle']['open']:.5f}  C={sig['candle']['close']:.5f}",
                    f"- {sig['disp_reason']}",
                    "",
                ]
        else:
            lines += [
                "### Signals",
                "",
                "**No signals generated.**",
                "",
            ]

        # ── Rejections summary ────────────────────────────────────────────────
        rejections = [(ts, ev, det) for ts, ev, det in result["log"]
                      if "No sweep" in ev or "reject" in ev.lower()
                      or "TIMEOUT" in ev or "pending" in ev.lower()]
        if rejections:
            lines += [
                "### Rejection Log (sweep-phase bars only)",
                "",
                "| Time | Reason | Detail |",
                "|---|---|---|",
            ]
            for ts, ev, det in rejections:
                lines.append(f"| {ts} | {ev} | {det.replace('|', '∣')} |")
            lines += [""]

        lines += ["---", ""]

    # ── Overall verdict ───────────────────────────────────────────────────────
    total_signals = sum(len(r.get("signals", [])) for r in results)
    lines += [
        "## Overall Verdict",
        "",
        f"- **Date:** {date_str}",
        f"- **Total signals:** {total_signals}",
    ]
    for r in results:
        sigs = len(r.get("signals", []))
        label = "SIGNAL" if sigs else "no signal"
        lines.append(f"- **{r['symbol']}:** {sigs} {label}")

    lines += [
        "",
        "---",
        "",
        "*Generated by `scripts/dry_run.py` — audit mode, no execution.*",
    ]
    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Session Liquidity dry run on one date")
    p.add_argument("--date", required=True, metavar="YYYY-MM-DD",
                   help="Trade date to evaluate")
    p.add_argument("--symbols", nargs="+", default=["EURUSD", "GBPUSD"],
                   metavar="SYM", help="Pairs to evaluate (default: both)")
    args = p.parse_args()

    trade_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    results = []

    for sym in args.symbols:
        print(f"\n{'='*60}")
        print(f"  {sym}  —  {trade_date}")
        print(f"{'='*60}")
        result = run_dry_run(sym, trade_date)
        results.append(result)

        if "error" in result:
            print(f"  ERROR: {result['error']}")
            continue

        asian = result["asian"]
        if asian:
            print(f"  Asian High : {asian.high:.5f}")
            print(f"  Asian Low  : {asian.low:.5f}")
            print(f"  Range      : {asian.range_pips:.1f} pips")
        else:
            print("  Asian Range: NOT BUILT")

        print(f"  HTF Bias   : {result['bias'] or 'N/A'}")
        print()
        for ts, event, detail in result["log"]:
            print(f"  [{ts}]  {event}")
            if detail:
                print(f"           {detail}")

        if result["signals"]:
            for sig in result["signals"]:
                print(f"\n  *** SIGNAL: {sig['side'].upper()} in {sig['session']} ***")
                print(f"      Entry  : {sig['entry']:.5f}")
                print(f"      SL     : {sig['stop_loss']:.5f}  ({sig['sl_pips']:.1f} pip)")
                for rr, tp in sig["take_profits"].items():
                    print(f"      TP{rr}    : {tp:.5f}  (RR {rr})")
        else:
            print("\n  No signals.")

    # Generate report
    report = generate_report(results, trade_date)
    date_str = trade_date.strftime("%Y_%m_%d")
    out_path = _DOCS / f"DRY_RUN_{date_str}.md"
    _DOCS.mkdir(exist_ok=True)
    out_path.write_text(report)
    print(f"\nReport written → {out_path}")


if __name__ == "__main__":
    main()

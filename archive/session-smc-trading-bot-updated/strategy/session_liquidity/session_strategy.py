"""
SA-07 — Session Strategy Orchestrator.

Wires SA-01 through SA-06 into a complete signal generation pipeline.
No broker execution, no position sizing, no order management.

Public API:
    DEFAULT_CONFIG  — reference config dict
    run_strategy()  — entry point
"""

from datetime import datetime, timezone

from strategy.session_liquidity.session_builder import (
    build_asian_range, classify_session,
)
from strategy.session_liquidity.bias_filter import htf_bias
from strategy.session_liquidity.sweep_detector import detect_sweep
from strategy.session_liquidity.displacement_detector import (
    detect_displacement, wilder_atr,
)
from strategy.session_liquidity.entry_engine import Signal, build_signal

_UTC = timezone.utc

DEFAULT_CONFIG: dict = {
    "rr":                  3.0,
    "sl_buffer_pips":      2.0,
    "displacement_mult":   1.2,
    "atr_period":          14,
    "sweep_timeout_bars":  4,
    "min_sl_pips":         5.0,
    "min_range_pips": {
        "EURUSD": 15.0,
        "GBPUSD": 20.0,
    },
}


def run_strategy(
    candles_m15: list,
    candles_4h: list,
    symbol: str,
    config: "dict | None" = None,
    debug: bool = False,
) -> "list[Signal] | tuple[list[Signal], list[dict]]":
    """
    Run Strategy A over M15 + H4 history and return all valid signals.

    Args:
        candles_m15:  M15 OHLCV dicts. 'time' may be ISO string or datetime.
                      Need not be sorted — sorted internally.
        candles_4h:   H4 OHLCV dicts. Used for HTF bias only (no lookahead).
        symbol:       'EURUSD' | 'GBPUSD' (used for min-range lookup).
        config:       Overrides for DEFAULT_CONFIG fields. Merged, not replaced.
        debug:        When True returns (signals, events) instead of signals.
                      events is list[dict] with per-bar decisions.

    Returns:
        list[Signal] normally.
        tuple[list[Signal], list[dict]] when debug=True.

    One signal per session (london / new_york) per calendar day.
    Displacement must appear within sweep_timeout_bars killzone bars of the sweep.
    """
    cfg          = {**DEFAULT_CONFIG, **(config or {})}
    rr           = float(cfg["rr"])
    sl_buf       = float(cfg["sl_buffer_pips"])
    mult         = float(cfg["displacement_mult"])
    period       = int(cfg["atr_period"])
    timeout      = int(cfg["sweep_timeout_bars"])
    min_sl_pips  = float(cfg.get("min_sl_pips", 0.0))
    min_range    = float(cfg["min_range_pips"].get(_norm(symbol), 15.0))

    signals: list[Signal] = []
    events:  list[dict]   = []

    if not candles_m15:
        return (signals, events) if debug else signals

    # ── Sort once; pre-compute ATR across the full history ────────────────────
    sorted_m15 = sorted(candles_m15, key=lambda c: c["time"])
    atrs       = wilder_atr(sorted_m15, period)
    atr_map    = {c["time"]: atr for c, atr in zip(sorted_m15, atrs)}

    # ── Pre-group killzone bars by UTC date (one O(n) pass) ───────────────────
    # Avoids O(n_bars × n_days) rescanning inside the day loop.
    _kz_by_date: dict = {}
    for _c in sorted_m15:
        _dt = _utc(_c["time"])
        _s  = classify_session(_dt)
        if _s is not None:
            _kz_by_date.setdefault(_dt.date(), []).append((_c, _s))

    trade_dates = sorted(_kz_by_date.keys())

    for trade_date in trade_dates:

        # ── Phase 1: Asian Range ───────────────────────────────────────────────
        asian = build_asian_range(sorted_m15, trade_date)
        if asian is None:
            _evt(events, debug, trade_date, "SKIP_DAY", "asian_range_missing")
            continue

        # ── Phase 4: Minimum range filter ─────────────────────────────────────
        if asian.range_pips < min_range:
            _evt(events, debug, trade_date, "SKIP_DAY",
                 f"range={asian.range_pips:.1f}pip < {min_range}pip min")
            continue

        _evt(events, debug, trade_date, "ASIAN_RANGE",
             f"H={asian.high:.5f} L={asian.low:.5f} range={asian.range_pips:.1f}pip")

        # Killzone bars for this date — pre-grouped, O(1) lookup
        day_bars = _kz_by_date.get(trade_date, [])

        session_traded: set = set()
        pending: "dict | None" = None   # {sweep, bar_idx, session}

        for bar_idx, (candle, session) in enumerate(day_bars):
            bar_time  = _utc(candle["time"])
            bar_label = bar_time.strftime("%H:%M UTC")

            # ── Phase 10: one signal per session ──────────────────────────────
            if session in session_traded:
                continue

            # Cancel pending sweep when session changes
            if pending and pending["session"] != session:
                _evt(events, debug, trade_date, "SWEEP_CANCEL",
                     f"[{bar_label}] session changed {pending['session']}→{session}")
                pending = None

            # ── Phase 2: HTF Bias ──────────────────────────────────────────────
            bias = htf_bias(candles_4h, bar_time)

            if pending is None:
                # ── Phase 5: Sweep detection ───────────────────────────────────
                if bias == "neutral":
                    _evt(events, debug, trade_date, "NO_TRADE",
                         f"[{bar_label}] {session} bias=neutral")
                    continue

                sweep = detect_sweep(candle, asian.high, asian.low, bias)

                if sweep.detected:
                    pending = {"sweep": sweep, "bar_idx": bar_idx, "session": session}
                    _evt(events, debug, trade_date, "SWEEP",
                         f"[{bar_label}] {session} side={sweep.side} "
                         f"price={sweep.sweep_price:.5f} bias={bias}")
                else:
                    _evt(events, debug, trade_date, "NO_SWEEP",
                         f"[{bar_label}] {session} {sweep.reason} bias={bias}")

            else:
                # ── Phase 6: Displacement search ───────────────────────────────
                bars_since = bar_idx - pending["bar_idx"]

                if bars_since > timeout:
                    _evt(events, debug, trade_date, "SWEEP_TIMEOUT",
                         f"[{bar_label}] {session} no displacement in {timeout} bars")
                    pending = None
                    continue

                atr  = atr_map.get(candle["time"])
                disp = detect_displacement(candle, atr, pending["sweep"].side, mult)

                if disp.detected:
                    # ── Phases 7-9: Build signal ───────────────────────────────
                    sig = build_signal(
                        candle, pending["sweep"], disp,
                        asian, session, rr, sl_buf,
                    )
                    pending = None
                    if sig is None:
                        _evt(events, debug, trade_date, "SIGNAL_REJECTED",
                             f"[{bar_label}] {session} build_signal returned None")
                    elif sig.risk_pips < min_sl_pips:
                        _evt(events, debug, trade_date, "SIGNAL_REJECTED",
                             f"[{bar_label}] {session} "
                             f"sl={sig.risk_pips:.1f}pip < min_sl={min_sl_pips:.1f}pip")
                    else:
                        signals.append(sig)
                        session_traded.add(session)
                        _evt(events, debug, trade_date, "SIGNAL",
                             f"[{bar_label}] {session} {sig.side} "
                             f"entry={sig.entry:.5f} sl={sig.stop_loss:.5f} "
                             f"rr={sig.rr}")
                else:
                    _evt(events, debug, trade_date, "DISP_REJECT",
                         f"[{bar_label}] {session} [{bars_since}/{timeout}] "
                         f"{disp.reason}")

    if debug:
        return signals, events
    return signals


# ── Helpers ───────────────────────────────────────────────────────────────────

def _utc(t) -> datetime:
    if isinstance(t, datetime):
        return t if t.tzinfo else t.replace(tzinfo=_UTC)
    return datetime.fromisoformat(str(t).replace("Z", "+00:00"))


def _norm(symbol: str) -> str:
    """'EUR/USD' | 'EUR_USD' | 'EURUSD' → 'EURUSD'."""
    return symbol.replace("/", "").replace("_", "").upper()


def _evt(events: list, debug: bool, date, event_type: str, detail: str) -> None:
    if debug:
        events.append({"date": str(date), "event": event_type, "detail": detail})

"""
Setup A — Sweep Reversal signal chain (11-phase AND gate).

Phases implemented here
------------------------
1  Session active                  (enforced by caller / backtest)
2  HTF Bias (4H + 1H)              htf_bias()
3  Session range build             build_session_range()
4  Session classification          classify_session()
5  Liquidity sweep                 detect_sweep()
6  15M CHoCH                       detect_choch()
7  15M BOS                         detect_bos()
8  15M Displacement                detect_displacement()
9  15M FVG + retest                find_fvg() / check_fvg_retest()
10 Risk params (SL / TP)           computed here
11 Min session time remaining      enforced here

Entry: close of FVG retest bar (bar-close, no lookahead).
SL: tighter of (25% session range | sweep wick extreme ± 3 pip buffer).
TP1: entry ± 4 R.   TP2: entry ± 5 R.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from .structure_detector import atr, detect_choch, detect_bos, detect_displacement, htf_bias
from .liquidity_detector import build_session_range, classify_session, detect_sweep
from .poi_detector import find_fvg, check_fvg_retest
from .swing_detector import last_swing_high, last_swing_low

Candle = dict
PIP: float = 0.0001


@dataclass
class Signal:
    symbol: str
    direction: str      # 'long' | 'short'
    entry: float
    sl: float
    tp1: float
    tp2: float
    sl_pips: float
    rr: float
    setup_type: str     # 'A'
    session: str        # 'london' | 'newyork'
    bar_time: Optional[str]
    # diagnostic fields
    sweep_idx: int
    choch_idx: int
    bos_idx: int
    displacement_idx: int
    retest_idx: int
    session_range: dict


# ── Default config ─────────────────────────────────────────────────────────────

DEFAULT_CONFIG: dict = {
    "swing_n": 3,
    "choch_lookback": 8,
    "displacement_atr_mult": 1.5,
    "min_session_range_pips": 10.0,
    "session_range_bars": 8,
    "sweep_start_bar": 8,
    "min_bars_remaining": 2,
    "sl_range_pct": 0.25,
    "sl_buffer_pips": 3.0,
    "tp1_r": 4.0,
    "tp2_r": 5.0,
    "atr_period": 14,
}


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_signal_A(
    symbol: str,
    candles_4h: list[Candle],
    candles_1h: list[Candle],
    session_candles: list[Candle],
    session_name: str,
    config: Optional[dict] = None,
) -> Optional[Signal]:
    """
    Run the full Setup A signal chain on the current session's 15M candles.

    Parameters
    ----------
    candles_4h       : 4H bars available *before* session start (for HTF bias)
    candles_1h       : 1H bars available *before* session start (for HTF bias)
    session_candles  : 15M bars from session open up to and including current bar
    session_name     : 'london' | 'newyork'
    config           : override DEFAULT_CONFIG keys as needed

    Returns
    -------
    Signal  if all 11 phases pass,  None otherwise.
    The signal is based on the MOST RECENT complete sequence found in session_candles.
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}

    n = len(session_candles)
    range_bars = cfg["session_range_bars"]
    sweep_start = cfg["sweep_start_bar"]

    # Minimum bars needed: range + 1 sweep + 1 CHoCH + 1 BOS + 1 disp + 1 FVG-next + 1 retest
    if n < range_bars + 6:
        return None

    # ── Phase 2 — HTF Bias ───────────────────────────────────────────────────
    bias = htf_bias(candles_4h, candles_1h, cfg["swing_n"])
    if bias == "neutral":
        return None

    # ── Phase 3 — Session Range ───────────────────────────────────────────────
    sess_range = build_session_range(session_candles, range_bars, cfg["min_session_range_pips"])
    if sess_range is None:
        return None

    # ── Phase 4 — Session classification (informational, not a hard gate) ────
    # RANGE sessions with low ATR are still valid; classification is logged only.
    _sess_class = classify_session(session_candles, sess_range, cfg["atr_period"])

    # ── Pre-compute ATR for displacement detection ────────────────────────────
    atr_vals = atr(session_candles, cfg["atr_period"])

    # ── Phase 5 — Sweep ───────────────────────────────────────────────────────
    sweep = detect_sweep(session_candles, sess_range, bias, sweep_start)
    if sweep is None:
        return None
    si = sweep["index"]

    # ── Phase 6 — CHoCH ───────────────────────────────────────────────────────
    choch = detect_choch(session_candles, si, bias, cfg["choch_lookback"])
    if choch is None:
        return None
    ci = choch["index"]

    # ── Phase 7 — BOS ─────────────────────────────────────────────────────────
    # BOS level = last confirmed swing in trade direction before the sweep
    if bias == "bullish":
        bos_swing = last_swing_high(session_candles, cfg["swing_n"], before_idx=si)
        bos_level = bos_swing["price"] if bos_swing else None
    else:
        bos_swing = last_swing_low(session_candles, cfg["swing_n"], before_idx=si)
        bos_level = bos_swing["price"] if bos_swing else None

    bos = detect_bos(session_candles, ci, bias, bos_level)
    if bos is None:
        return None
    bi = bos["index"]

    # ── Phase 8 — Displacement ────────────────────────────────────────────────
    disp = detect_displacement(
        session_candles, si, bi, bias, atr_vals, cfg["displacement_atr_mult"]
    )
    if disp is None:
        return None
    di = disp["index"]

    # FVG needs bar di+1 to exist
    if di + 1 >= n:
        return None

    # ── Phase 9a — FVG ───────────────────────────────────────────────────────
    fvg = find_fvg(session_candles, di, bias)
    if fvg is None:
        return None

    # ── Phase 9b — FVG Retest ────────────────────────────────────────────────
    # Start looking from di+2 (di+1 is the FVG-confirming bar already closed)
    retest_idx = check_fvg_retest(session_candles, fvg, bias, di + 2)
    if retest_idx is None:
        return None

    # ── Phase 11 — Min bars remaining ────────────────────────────────────────
    bars_remaining = n - 1 - retest_idx
    if bars_remaining < cfg["min_bars_remaining"]:
        return None

    # ── Phase 10 — Risk parameters ────────────────────────────────────────────
    entry = session_candles[retest_idx]["close"]
    range_size = sess_range["high"] - sess_range["low"]
    wick_ext = sweep["wick_extreme"]
    buf = cfg["sl_buffer_pips"] * PIP
    range_sl_dist = cfg["sl_range_pct"] * range_size

    if bias == "bullish":
        wick_sl = wick_ext - buf
        range_sl = entry - range_sl_dist
        sl = max(wick_sl, range_sl)   # tighter = higher price (closer to entry)
        if sl >= entry:               # degenerate: SL above/at entry
            return None
        sl_pips = (entry - sl) / PIP
        tp1 = entry + cfg["tp1_r"] * sl_pips * PIP
        tp2 = entry + cfg["tp2_r"] * sl_pips * PIP
        direction = "long"
    else:
        wick_sl = wick_ext + buf
        range_sl = entry + range_sl_dist
        sl = min(wick_sl, range_sl)   # tighter = lower price
        if sl <= entry:
            return None
        sl_pips = (sl - entry) / PIP
        tp1 = entry - cfg["tp1_r"] * sl_pips * PIP
        tp2 = entry - cfg["tp2_r"] * sl_pips * PIP
        direction = "short"

    return Signal(
        symbol=symbol,
        direction=direction,
        entry=entry,
        sl=sl,
        tp1=tp1,
        tp2=tp2,
        sl_pips=sl_pips,
        rr=cfg["tp1_r"],
        setup_type="A",
        session=session_name,
        bar_time=session_candles[retest_idx].get("time"),
        sweep_idx=si,
        choch_idx=ci,
        bos_idx=bi,
        displacement_idx=di,
        retest_idx=retest_idx,
        session_range=sess_range,
    )

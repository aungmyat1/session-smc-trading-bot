"""
smc_bot/session_range.py
Multi-instrument · Multi-session signal engine
Instruments : EURUSD, GBPUSD, XAUUSD
Sessions    : Asian | London | Overlap | New York
Imports ONLY: structure, liquidity, tp_engine, dataclasses, pandas, datetime
NO broker SDK — passes tests/test_ast_guard.py
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from smc_bot import structure, tp_engine          # internal only — no SDK

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Dataclasses
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SessionBox:
    box_high:   float
    box_low:    float
    box_range:  float
    atr:        float
    session:    str
    instrument: str


@dataclass
class SweepEvent:
    direction: str    # 'high' | 'low'
    candle:    pd.Series


@dataclass
class SessionSignal:
    instrument:   str           # 'EURUSD' | 'GBPUSD' | 'XAUUSD'
    session:      str           # 'asian' | 'london' | 'overlap' | 'newyork'
    setup:        str           # 'sweep' | 'range' | 'trend'
    side:         str           # 'long' | 'short'
    entry:        float
    sl:           float
    tp:           float
    box_high:     float
    box_low:      float
    signal_weight: float = 1.0
    mgmt: dict = field(default_factory=dict)
    # mgmt keys: first_close_pct, first_close_target, trail_remainder


# ─────────────────────────────────────────────────────────────────────────────
# A. Session box builder
# ─────────────────────────────────────────────────────────────────────────────

def build_session_box(
    df_1h: pd.DataFrame,
    start_h: int,
    end_h: int,
    instrument: str,
    session: str,
) -> SessionBox:
    """
    Filter df_1h to candles whose UTC hour falls in [start_h, end_h).
    Compute box high/low/range and ATR(14) on the full series.
    Raises ValueError if fewer than 3 session candles found.
    """
    df = df_1h.copy()

    # Ensure datetime index in UTC
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index, utc=True)
    elif df.index.tz is None:
        df.index = df.index.tz_localize("UTC")

    session_df = df[
        (df.index.hour >= start_h) & (df.index.hour < end_h)
    ].tail(24)  # last 24h window to avoid stale sessions

    if len(session_df) < 3:
        raise ValueError(
            f"[{instrument}/{session}] Only {len(session_df)} candles in "
            f"{start_h:02d}:00–{end_h:02d}:00 UTC — session not yet complete."
        )

    box_high  = session_df["high"].max()
    box_low   = session_df["low"].min()
    box_range = box_high - box_low

    # ATR(14) on full series
    high_low   = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close  = (df["low"]  - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(14).mean().iloc[-1]

    return SessionBox(
        box_high=round(box_high, 6),
        box_low=round(box_low, 6),
        box_range=round(box_range, 6),
        atr=round(atr, 6),
        session=session,
        instrument=instrument,
    )


# ─────────────────────────────────────────────────────────────────────────────
# B. Session classifier
# ─────────────────────────────────────────────────────────────────────────────

def classify_session(box: SessionBox, session_cfg: dict) -> str:
    """
    ratio = box_range / ATR
    < range_thr  → 'range'
    > trend_thr  → 'trend'
    else         → 'neutral'
    """
    if box.atr == 0:
        return "neutral"

    ratio = box.box_range / box.atr

    if ratio < session_cfg["range_thr"]:
        return "range"
    if ratio > session_cfg["trend_thr"]:
        return "trend"
    return "neutral"


# ─────────────────────────────────────────────────────────────────────────────
# C. Sweep detector
# ─────────────────────────────────────────────────────────────────────────────

def detect_sweep(
    df_1h: pd.DataFrame,
    box: SessionBox,
    instr_cfg: dict,
    end_h: int,
) -> Optional[SweepEvent]:
    """
    Scan candles AFTER the session window closes (hour >= end_h).
    A sweep is valid when:
      - Wick exceeds box_high by >= sweep_beyond_pct * box_range (HIGH sweep)
        OR wick goes below box_low by the same threshold (LOW sweep)
      - AND candle CLOSES back inside the box

    'high' sweep → price swept liquidity ABOVE → signal is SHORT
    'low'  sweep → price swept liquidity BELOW → signal is LONG

    Returns first valid SweepEvent or None.
    """
    df = df_1h.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index, utc=True)
    elif df.index.tz is None:
        df.index = df.index.tz_localize("UTC")

    post_session = df[df.index.hour >= end_h].tail(8)  # look back max 8 candles
    threshold = instr_cfg["sweep_beyond_pct"] * box.box_range

    for _, candle in post_session.iterrows():
        # HIGH sweep: wick above box_high, close back inside
        if (
            candle["high"] >= box.box_high + threshold
            and candle["close"] <= box.box_high
        ):
            log.info(
                "[%s] HIGH sweep detected at %.5f (box_high=%.5f)",
                box.instrument, candle["high"], box.box_high,
            )
            return SweepEvent(direction="high", candle=candle)

        # LOW sweep: wick below box_low, close back inside
        if (
            candle["low"] <= box.box_low - threshold
            and candle["close"] >= box.box_low
        ):
            log.info(
                "[%s] LOW sweep detected at %.5f (box_low=%.5f)",
                box.instrument, candle["low"], box.box_low,
            )
            return SweepEvent(direction="low", candle=candle)

    return None


# ─────────────────────────────────────────────────────────────────────────────
# D. Master signal builder
# ─────────────────────────────────────────────────────────────────────────────

def build_session_signal(
    df_4h: pd.DataFrame,
    df_1h: pd.DataFrame,
    instrument: str,
    session_name: str,
    cfg: dict,
) -> Optional[SessionSignal]:
    """
    Full signal pipeline for one instrument × session combination.
    Returns SessionSignal or None if no valid setup found.
    """
    instr_cfg   = cfg["instruments"][instrument]
    session_cfg = cfg["sessions"][session_name]
    start_h     = session_cfg["start_h"]
    end_h       = session_cfg["end_h"]
    target_r    = cfg.get("asian", {}).get("target_r", 5.0)

    # ── 1. HTF bias gate ──────────────────────────────────────────────────
    bias = structure.get_bias(df_4h)
    if bias == "neutral":
        log.debug("[%s/%s] HTF bias neutral — skip", instrument, session_name)
        return None

    # ── 2. Build session box ──────────────────────────────────────────────
    try:
        box = build_session_box(df_1h, start_h, end_h, instrument, session_name)
    except ValueError as e:
        log.warning(str(e))
        return None

    if box.box_range == 0:
        log.debug("[%s/%s] box_range=0 — skip", instrument, session_name)
        return None

    # ── 3. Classify session ───────────────────────────────────────────────
    session_type = classify_session(box, session_cfg)

    # ── 4. Detect sweep ───────────────────────────────────────────────────
    sweep = detect_sweep(df_1h, box, instr_cfg, end_h)

    # ── 5. Route setup ────────────────────────────────────────────────────
    sl_dist = instr_cfg["sl_pct_of_range"] * box.box_range

    if sweep is not None:
        # SWEEP setup: bias direction confirmed by sweep direction
        if sweep.direction == "high":
            side  = "short"
            entry = float(sweep.candle["close"])
            sl    = box.box_high + sl_dist
            tp    = entry - (sl - entry) * target_r
        else:
            side  = "long"
            entry = float(sweep.candle["close"])
            sl    = box.box_low - sl_dist
            tp    = entry + (entry - sl) * target_r
        setup = "sweep"

    elif session_type == "range":
        # RANGE setup: fade box extremes in HTF bias direction
        if bias == "bullish":
            side  = "long"
            entry = box.box_low
            sl    = box.box_low - sl_dist
            tp    = entry + (entry - sl) * target_r
        else:
            side  = "short"
            entry = box.box_high
            sl    = box.box_high + sl_dist
            tp    = entry - (sl - entry) * target_r
        setup = "range"

    elif session_type == "trend":
        # TREND setup: midpoint pullback entry
        midpoint = (box.box_high + box.box_low) / 2
        if bias == "bullish":
            side  = "long"
            entry = midpoint
            sl    = box.box_low - sl_dist
            tp    = entry + (entry - sl) * target_r
        else:
            side  = "short"
            entry = midpoint
            sl    = box.box_high + sl_dist
            tp    = entry - (sl - entry) * target_r
        setup = "trend"

    else:
        # neutral + no sweep → no trade
        log.debug(
            "[%s/%s] session_type=%s, no sweep — no signal",
            instrument, session_name, session_type,
        )
        return None

    # ── 6. Spread validation ──────────────────────────────────────────────
    pip = instr_cfg["pip_size"]
    spread_pips = instr_cfg["spread_allowance_pips"]
    entry_dist_pips = abs(entry - box.box_low) / pip if side == "long" \
        else abs(box.box_high - entry) / pip

    if entry_dist_pips < spread_pips:
        log.info(
            "[%s/%s] Entry %.5f too close to box edge (%.1f pips < %.1f allowance) — skip",
            instrument, session_name, entry, entry_dist_pips, spread_pips,
        )
        return None

    # ── 7. Build mgmt dict ────────────────────────────────────────────────
    mgmt = {
        "first_close_pct":    session_cfg["first_close_pct"],
        "first_close_target": session_cfg["first_close_target"],
        "trail_remainder":    session_cfg["trail_remainder"],
        "first_close_done":   False,
    }

    # ── 8. R-plan via tp_engine ───────────────────────────────────────────
    plan = tp_engine.build_plan(entry=entry, sl=sl, target_r=target_r)
    tp   = plan["tp"]  # use tp_engine output for consistency

    log.info(
        "[%s/%s] Signal → %s %s | entry=%.5f sl=%.5f tp=%.5f setup=%s",
        instrument, session_name, side.upper(), instrument,
        entry, sl, tp, setup,
    )

    return SessionSignal(
        instrument=instrument,
        session=session_name,
        setup=setup,
        side=side,
        entry=round(entry, 6),
        sl=round(sl, 6),
        tp=round(tp, 6),
        box_high=box.box_high,
        box_low=box.box_low,
        signal_weight=instr_cfg.get("signal_weight", 1.0),
        mgmt=mgmt,
    )


# ─────────────────────────────────────────────────────────────────────────────
# E. Multi-instrument scanner
# ─────────────────────────────────────────────────────────────────────────────

def scan_all(
    data: dict,
    cfg: dict,
    utc_now: Optional[datetime] = None,
) -> list[SessionSignal]:
    """
    data = {
        'EURUSD': {'df_4h': pd.DataFrame, 'df_1h': pd.DataFrame},
        'GBPUSD': {...},
        'XAUUSD': {...},
    }

    For each instrument × session:
      - Skip if session not in instrument's sessions list
      - Skip if session end_h has not yet passed (box not complete)
      - Build signal; collect if not None

    Returns signals sorted by signal_weight DESC.
    Caps at cfg['risk']['max_concurrent_signals'] (default 3).
    """
    if utc_now is None:
        utc_now = datetime.now(timezone.utc)

    signals: list[SessionSignal] = []
    max_signals = cfg.get("risk", {}).get("max_concurrent_signals", 3)

    for instrument, frames in data.items():
        instr_cfg = cfg["instruments"].get(instrument)
        if instr_cfg is None:
            log.warning("No config for instrument %s — skip", instrument)
            continue

        df_4h = frames["df_4h"]
        df_1h = frames["df_1h"]

        for session_name, session_cfg in cfg["sessions"].items():
            # Gate 1: instrument must list this session
            if session_name not in instr_cfg.get("sessions", []):
                log.debug(
                    "[%s/%s] session not in instrument sessions list — skip",
                    instrument, session_name,
                )
                continue

            # Gate 2: session box must be complete (end_h passed)
            if utc_now.hour < session_cfg["end_h"]:
                log.debug(
                    "[%s/%s] session end_h=%d not yet reached (now=%d) — skip",
                    instrument, session_name,
                    session_cfg["end_h"], utc_now.hour,
                )
                continue

            try:
                sig = build_session_signal(
                    df_4h, df_1h, instrument, session_name, cfg
                )
                if sig is not None:
                    signals.append(sig)
            except Exception as e:
                log.error(
                    "[%s/%s] Unexpected error in build_session_signal: %s",
                    instrument, session_name, e, exc_info=True,
                )

    # Sort by signal_weight descending, cap at max_concurrent_signals
    signals.sort(key=lambda s: s.signal_weight, reverse=True)
    if len(signals) > max_signals:
        dropped = [f"{s.instrument}/{s.session}" for s in signals[max_signals:]]
        log.info("Signal cap %d reached — dropping: %s", max_signals, dropped)
        signals = signals[:max_signals]

    log.info(
        "scan_all complete: %d signal(s) at %s UTC",
        len(signals), utc_now.strftime("%H:%M"),
    )
    return signals

"""
pipeline/config.py
Single source of truth for all Phase-0 pipeline parameters.

IMPORTANT: Every parameter change = new trial row in docs/VERDICT_LOG.md.
Do NOT change values and re-run on the same trial ID.
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

# ── Pip constant ──────────────────────────────────────────────────────────────
PIP: float = 0.0001  # 5-digit EURUSD / GBPUSD


# ── Spread / cost models ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class SpreadConfig:
    """All costs in pips (1 pip = 0.0001)."""

    spread_pips: float  # one-way market spread (bid-ask)
    commission_pips: float  # round-trip commission converted to pips

    @property
    def total_cost_pips(self) -> float:
        return self.spread_pips + self.commission_pips


# VT Markets Standard account — from CLAUDE.md §1
SPREAD_STANDARD: Dict[str, SpreadConfig] = {
    "EURUSD": SpreadConfig(spread_pips=0.8, commission_pips=0.6),
    "GBPUSD": SpreadConfig(spread_pips=1.2, commission_pips=0.6),
}

# 2× spread stress test — required gate from CLAUDE.md §9
SPREAD_STRESS_2X: Dict[str, SpreadConfig] = {
    "EURUSD": SpreadConfig(spread_pips=1.6, commission_pips=0.6),
    "GBPUSD": SpreadConfig(spread_pips=2.4, commission_pips=0.6),
}


# ── Session windows (UTC hours) ───────────────────────────────────────────────


@dataclass(frozen=True)
class SessionWindow:
    name: str
    open_utc: int  # inclusive
    close_utc: int  # exclusive


# CLAUDE.md §1: London 07-10 UTC | NY 13-16 UTC
SESSIONS: list[SessionWindow] = [
    SessionWindow("london", open_utc=7, close_utc=10),
    SessionWindow("newyork", open_utc=13, close_utc=16),
]

# Asian session used to build the daily range that London sweeps
ASIAN_WINDOW = SessionWindow("asian", open_utc=0, close_utc=7)


# ── Signal chain parameters (CLAUDE.md §2) ───────────────────────────────────

SIGNAL_CONFIG: Dict = {
    # Phase 2 — HTF bias
    "swing_n": 3,
    # Phase 6 — CHoCH
    "choch_lookback": 8,
    # Phase 8 — Displacement
    "displacement_atr_mult": 1.5,
    # Phase 3 — Session range build
    "min_session_range_pips": 10.0,
    "session_range_bars": 8,  # 8 × 15M = 2 H initial range window
    # Phase 5 — Sweep (start searching after range is built)
    "sweep_start_bar": 8,
    # Phase 11 — Min bars remaining after entry
    "min_bars_remaining": 2,
    # Phase 10 — SL sizing
    "sl_range_pct": 0.25,  # 25% of session range
    "sl_buffer_pips": 3.0,  # buffer beyond wick extreme
    # Phase 10 — Take profit
    "tp1_r": 4.0,
    "tp2_r": 5.0,
    "atr_period": 14,
    # D2 daily context gates
    "d2_structure_gate": True,
    "d2_location_gate": True,
    "d2_poi_gate": True,
    "d2_poi_pips": 30.0,
}

# Phase-0 gate thresholds (CLAUDE.md §3, §9)
PHASE0_MIN_TRADES: int = 50
PHASE0_MIN_NET_PF: float = 1.0

# Symbols
SYMBOLS: list[str] = ["EURUSD", "GBPUSD"]

# ── Filesystem layout ─────────────────────────────────────────────────────────
DATA_DIR = Path("data/processed")  # {SYMBOL}/{SYMBOL}_{TF}.parquet
FEATURES_DIR = Path("data/features")  # {SYMBOL}/asian_range.parquet etc.
REPORTS_DIR = Path("reports")

"""
smc_bot/risk.py  (upgraded for Vantage MT5 forex lot sizing)
Supports: EURUSD, GBPUSD (pip-based) and XAUUSD (point-based).
Replaces the Bybit quantity calculator entirely.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

from smc_bot.session_range import SessionSignal

log = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
# Vantage MT5 standard-lot pip values (USD-account, EURUSD/GBPUSD quote in USD)
PIP_VALUE_PER_STD_LOT = {
    "EURUSD": 10.0,   # $10 per pip per standard lot
    "GBPUSD": 10.0,   # $10 per pip per standard lot (approx, GBPUSD quoted in USD)
    "XAUUSD": 1.0,    # $1 per 0.01-point move per standard lot ($100 per $1 move)
}

MIN_LOT  = 0.01
LOT_STEP = 0.01   # MT5 minimum increment


def calc_qty(
    signal:          SessionSignal,
    cfg:             dict,
    account_balance: float,
) -> float:
    """
    Calculate lot size for a SessionSignal based on configured risk.

    Risk sourcing (priority order):
      1. cfg['risk']['risk_usd']     — fixed USD risk per trade (overrides %)
      2. cfg['risk']['risk_pct_per_trade'] × account_balance — % of equity

    Lot sizing:
      EURUSD / GBPUSD:
        sl_pips = |entry - sl| / pip_size
        lots    = risk_usd / (sl_pips × pip_value_per_lot)

      XAUUSD:
        sl_points = |entry - sl| / pip_size   (pip_size=0.01 for gold)
        lots      = risk_usd / (sl_points × point_value_per_lot)
        where point_value_per_lot = 1.0  ($1 per point per standard lot)

    Enforces:
      - MIN_LOT  = 0.01
      - max_lots = cfg['risk']['max_lots_per_symbol']
      - Result rounded DOWN to nearest LOT_STEP
    """
    risk_cfg    = cfg.get("risk", {})
    instr_cfg   = cfg["instruments"][signal.instrument]
    pip_size    = instr_cfg["pip_size"]
    max_lots    = risk_cfg.get("max_lots_per_symbol", 1.0)

    # ── Resolve risk in USD ──────────────────────────────────────────────────
    if "risk_usd" in risk_cfg and risk_cfg["risk_usd"] > 0:
        risk_usd = float(risk_cfg["risk_usd"])
    elif "risk_pct_per_trade" in risk_cfg:
        risk_usd = float(risk_cfg["risk_pct_per_trade"]) * account_balance
    else:
        raise ValueError(
            "Neither risk.risk_usd nor risk.risk_pct_per_trade configured."
        )

    log.info(
        "[%s] risk_usd=%.2f balance=%.2f",
        signal.instrument, risk_usd, account_balance,
    )

    # ── SL distance ───────────────────────────────────────────────────────────
    sl_raw = abs(signal.entry - signal.sl)
    if sl_raw == 0:
        log.error("[%s] SL distance is zero — cannot size position", signal.instrument)
        return 0.0

    # ── Lot calc ──────────────────────────────────────────────────────────────
    pip_value = PIP_VALUE_PER_STD_LOT.get(signal.instrument, 10.0)

    if signal.instrument in ("EURUSD", "GBPUSD"):
        sl_pips = sl_raw / pip_size
        raw_lots = risk_usd / (sl_pips * pip_value)

    elif signal.instrument == "XAUUSD":
        # Gold: pip_size=0.01, pip_value=1.0 per lot per $0.01 move
        sl_points = sl_raw / pip_size   # number of $0.01 points
        raw_lots  = risk_usd / (sl_points * pip_value)

    else:
        # Generic fallback — pip-based
        sl_pips  = sl_raw / pip_size
        raw_lots = risk_usd / (sl_pips * pip_value)

    # ── Round down to LOT_STEP, enforce min/max ───────────────────────────────
    lots = math.floor(raw_lots / LOT_STEP) * LOT_STEP
    lots = max(MIN_LOT, lots)
    lots = min(max_lots, lots)
    lots = round(lots, 2)

    log.info(
        "[%s/%s] sl_raw=%.5f risk_usd=%.2f → lots=%.2f (raw=%.4f max=%.2f)",
        signal.instrument, signal.setup,
        sl_raw, risk_usd, lots, raw_lots, max_lots,
    )
    return lots


def check_daily_loss_limit(pnl_today: float, cfg: dict) -> bool:
    """
    Returns True if daily loss limit has been breached (bot should halt).
    pnl_today: sum of closed P&L for today (negative = loss).
    """
    limit = cfg.get("risk", {}).get("max_daily_loss_usd", 150.0)
    if pnl_today <= -abs(limit):
        log.warning(
            "DAILY LOSS LIMIT HIT: today_pnl=%.2f limit=%.2f — halting new signals",
            pnl_today, limit,
        )
        return True
    return False


def check_max_open_positions(open_positions: list, cfg: dict) -> bool:
    """
    Returns True if max concurrent open positions reached.
    """
    max_pos = cfg.get("risk", {}).get("max_open_positions", 3)
    if len(open_positions) >= max_pos:
        log.info(
            "Max open positions reached (%d/%d) — no new entries",
            len(open_positions), max_pos,
        )
        return True
    return False


def symbol_already_open(symbol: str, open_positions: list) -> bool:
    """
    Returns True if a position for this symbol is already open.
    One-position-per-instrument rule.
    """
    for p in open_positions:
        if p.get("symbol") == symbol:
            log.info(
                "Position already open for %s (positionId=%s) — skip",
                symbol, p.get("id"),
            )
            return True
    return False

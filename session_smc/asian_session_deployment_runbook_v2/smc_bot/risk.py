"""smc_bot/risk.py - lot sizing and guard rails for the V2 bundle."""

from __future__ import annotations

import logging
import math

from .session_range import SessionSignal

log = logging.getLogger(__name__)

PIP_VALUE_PER_STD_LOT = {
    "EURUSD": 10.0,
    "GBPUSD": 10.0,
    "XAUUSD": 1.0,
}

MIN_LOT = 0.01
LOT_STEP = 0.01


def calc_qty(signal: SessionSignal, cfg: dict, account_balance: float) -> float:
    risk_cfg = cfg.get("risk", {})
    instr_cfg = cfg["instruments"][signal.instrument]
    pip_size = instr_cfg["pip_size"]
    max_lots = risk_cfg.get("max_lots_per_symbol", 1.0)

    if "risk_usd" in risk_cfg and risk_cfg["risk_usd"] > 0:
        risk_usd = float(risk_cfg["risk_usd"])
    elif "risk_pct_per_trade" in risk_cfg:
        risk_usd = float(risk_cfg["risk_pct_per_trade"]) * account_balance
    else:
        raise ValueError(
            "Neither risk.risk_usd nor risk.risk_pct_per_trade configured."
        )

    log.info(
        "[%s] risk_usd=%.2f balance=%.2f", signal.instrument, risk_usd, account_balance
    )

    sl_raw = abs(signal.entry - signal.sl)
    if sl_raw == 0:
        log.error("[%s] SL distance is zero — cannot size position", signal.instrument)
        return 0.0

    pip_value = PIP_VALUE_PER_STD_LOT.get(signal.instrument, 10.0)
    if signal.instrument in ("EURUSD", "GBPUSD"):
        sl_pips = sl_raw / pip_size
        raw_lots = risk_usd / (sl_pips * pip_value)
    elif signal.instrument == "XAUUSD":
        sl_points = sl_raw / pip_size
        raw_lots = risk_usd / (sl_points * pip_value)
    else:
        sl_pips = sl_raw / pip_size
        raw_lots = risk_usd / (sl_pips * pip_value)

    lots = math.floor(raw_lots / LOT_STEP) * LOT_STEP
    lots = max(MIN_LOT, lots)
    lots = min(max_lots, lots)
    lots = round(lots, 2)

    log.info(
        "[%s/%s] sl_raw=%.5f risk_usd=%.2f → lots=%.2f (raw=%.4f max=%.2f)",
        signal.instrument,
        signal.setup,
        sl_raw,
        risk_usd,
        lots,
        raw_lots,
        max_lots,
    )
    return lots


def check_daily_loss_limit(pnl_today: float, cfg: dict) -> bool:
    limit = cfg.get("risk", {}).get("max_daily_loss_usd", 150.0)
    if pnl_today <= -abs(limit):
        log.warning(
            "DAILY LOSS LIMIT HIT: today_pnl=%.2f limit=%.2f — halting new signals",
            pnl_today,
            limit,
        )
        return True
    return False


def check_max_open_positions(open_positions: list, cfg: dict) -> bool:
    max_pos = cfg.get("risk", {}).get("max_open_positions", 3)
    if len(open_positions) >= max_pos:
        log.info(
            "Max open positions reached (%d/%d) — no new entries",
            len(open_positions),
            max_pos,
        )
        return True
    return False


def symbol_already_open(symbol: str, open_positions: list) -> bool:
    for p in open_positions:
        if p.get("symbol") == symbol:
            log.info(
                "Position already open for %s (positionId=%s) — skip",
                symbol,
                p.get("id"),
            )
            return True
    return False

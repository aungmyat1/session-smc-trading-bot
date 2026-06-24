"""
Demo Risk Manager — position sizing + daily guards for ST-A2 demo.

Isolated from execution/risk_manager.py (live bot).

Rules:
    risk_per_trade:           0.25% of balance
    max_trades_per_day:       4
    max_open_positions:       2
    daily_loss_limit:         1.5%
    max_consecutive_losses:   3

Public API:
    calculate_lots(balance, sl_pips, symbol, risk_pct) -> float
    new_state() -> dict
    check_limits(state) -> dict   {approved, reason}
    record_result(state, outcome, pnl_pct) -> dict
    reset_daily(state) -> dict
"""

from __future__ import annotations

import math

# Pip values per lot (approximate, USD-denominated account)
_PIP_VALUE_PER_LOT: dict[str, float] = {
    "EURUSD": 10.0,
    "GBPUSD": 10.0,
    "USDJPY": 9.09,   # approx at 110
}
_MIN_LOT  = 0.01
_MAX_LOT  = 0.5      # demo cap
_LOT_STEP = 0.01

DEFAULT_RISK_PCT = 0.0025   # 0.25%

LIMITS = {
    "max_trades_per_day":     4,
    "max_open_positions":     2,
    "daily_loss_limit":       0.015,
    "max_consecutive_losses": 3,
}


def calculate_lots(
    balance:  float,
    sl_pips:  float,
    symbol:   str = "EURUSD",
    risk_pct: float = DEFAULT_RISK_PCT,
) -> float:
    """
    Return lot size rounded to nearest step, clamped to [MIN_LOT, MAX_LOT].

    balance:  account balance in USD
    sl_pips:  stop-loss distance in pips
    """
    if sl_pips <= 0 or balance <= 0:
        return _MIN_LOT

    risk_usd     = balance * risk_pct
    pip_val      = _PIP_VALUE_PER_LOT.get(symbol, 10.0)
    raw_lots     = risk_usd / (sl_pips * pip_val)
    stepped      = math.floor(raw_lots / _LOT_STEP) * _LOT_STEP
    return max(_MIN_LOT, min(_MAX_LOT, round(stepped, 2)))


def new_state() -> dict:
    return {
        "trades_today":          0,
        "open_positions":        0,
        "daily_loss_pct":        0.0,
        "consecutive_losses":    0,
        "halted":                False,
        "halt_reason":           "",
        "last_reset":            "",
    }


def check_limits(state: dict) -> dict:
    """
    Returns {"approved": bool, "reason": str}.
    All limits checked; first failure is reported.
    """
    if state.get("halted"):
        return {"approved": False, "reason": state.get("halt_reason", "HALTED")}

    if state.get("trades_today", 0) >= LIMITS["max_trades_per_day"]:
        return {"approved": False, "reason": "MAX_TRADES_PER_DAY"}

    if state.get("open_positions", 0) >= LIMITS["max_open_positions"]:
        return {"approved": False, "reason": "MAX_OPEN_POSITIONS"}

    if state.get("daily_loss_pct", 0.0) >= LIMITS["daily_loss_limit"]:
        return {"approved": False, "reason": "DAILY_LOSS_LIMIT"}

    if state.get("consecutive_losses", 0) >= LIMITS["max_consecutive_losses"]:
        return {"approved": False, "reason": "CONSECUTIVE_LOSS_LIMIT"}

    return {"approved": True, "reason": ""}


def record_result(state: dict, outcome: str, pnl_pct: float = 0.0) -> dict:
    """
    Update state after a trade closes.
    outcome: "WIN" | "LOSS" | "BREAKEVEN"
    pnl_pct: signed fraction of account (negative = loss)
    """
    state["trades_today"] = state.get("trades_today", 0) + 1
    state["open_positions"] = max(0, state.get("open_positions", 1) - 1)

    if pnl_pct < 0:
        state["daily_loss_pct"] = state.get("daily_loss_pct", 0.0) + abs(pnl_pct)

    if outcome == "LOSS":
        state["consecutive_losses"] = state.get("consecutive_losses", 0) + 1
    else:
        state["consecutive_losses"] = 0

    # Engage halt
    if state["daily_loss_pct"] >= LIMITS["daily_loss_limit"]:
        state["halted"]      = True
        state["halt_reason"] = "DAILY_LOSS_LIMIT"
    elif state["consecutive_losses"] >= LIMITS["max_consecutive_losses"]:
        state["halted"]      = True
        state["halt_reason"] = "CONSECUTIVE_LOSS_LIMIT"

    return state


def reset_daily(state: dict) -> dict:
    from datetime import datetime, timezone
    state["trades_today"]       = 0
    state["daily_loss_pct"]     = 0.0
    state["consecutive_losses"] = 0
    state["halted"]             = False
    state["halt_reason"]        = ""
    state["last_reset"]         = datetime.now(timezone.utc).isoformat()
    return state

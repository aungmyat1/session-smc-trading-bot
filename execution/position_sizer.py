"""
Position sizer — lot sizing from the ST-A2 risk model.

Formula (RISK_SPEC.md §Position Sizing):
    lot_size = (equity × risk_pct) / (sl_pips × pip_value_per_lot)

Always floor to 0.01 precision (never round up — never risk more than intended).
Validate SL range per RISK_SPEC §Per-Trade Limits before sizing.
Log full calculation breakdown for audit trail.
"""

import logging
import math
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# RISK_SPEC §Per-Trade Limits
_MIN_SL_PIPS: float = 3.0    # reject: spread would consume the SL
_MAX_SL_PIPS: float = 50.0   # reject: degenerate setup

_DEFAULT_PIP_VALUE: dict[str, float] = {"EURUSD": 10.0, "GBPUSD": 10.0}
_DEFAULT_MIN_LOT: float = 0.01
_DEFAULT_MAX_LOT: float = 10.0


@dataclass
class SizingResult:
    """Full calculation breakdown returned by calculate_lots()."""
    lots: float           # final clamped lot size (0.0 if invalid)
    equity: float
    risk_pct: float
    risk_amount: float    # equity × risk_pct / 100
    sl_pips: float
    pip_value: float      # pip_value_per_lot used
    raw_lots: float       # before floor and clamping
    clamped: bool         # True if floor/clamp changed the raw value
    valid: bool           # False if SL range is out of spec
    reject_reason: str = ""


def calculate_lots(
    equity: float,
    sl_pips: float,
    symbol: str,
    risk_pct: float = 1.0,
    pip_value_per_lot: "float | None" = None,
    min_lot: float = _DEFAULT_MIN_LOT,
    max_lot: float = _DEFAULT_MAX_LOT,
) -> SizingResult:
    """
    Calculate lot size for a given risk % and SL distance.

    Validates SL range before computing. Floors to 0.01. Clamps to [min_lot, max_lot].
    Always logs the full calculation (equity, risk_amount, sl_pips, pip_value, lots).

    Returns SizingResult with valid=False and reject_reason if SL is out of range.
    """
    # ── SL range validation ───────────────────────────────────────────────────

    if sl_pips < _MIN_SL_PIPS:
        result = SizingResult(
            lots=0.0, equity=equity, risk_pct=risk_pct, risk_amount=0.0,
            sl_pips=sl_pips, pip_value=0.0, raw_lots=0.0, clamped=False,
            valid=False, reject_reason=f"sl_pips={sl_pips:.1f} < min={_MIN_SL_PIPS:.1f}",
        )
        logger.warning("Position sizing rejected: %s", result.reject_reason)
        return result

    if sl_pips > _MAX_SL_PIPS:
        result = SizingResult(
            lots=0.0, equity=equity, risk_pct=risk_pct, risk_amount=0.0,
            sl_pips=sl_pips, pip_value=0.0, raw_lots=0.0, clamped=False,
            valid=False, reject_reason=f"sl_pips={sl_pips:.1f} > max={_MAX_SL_PIPS:.1f}",
        )
        logger.warning("Position sizing rejected: %s", result.reject_reason)
        return result

    # ── Sizing formula ────────────────────────────────────────────────────────

    pv = pip_value_per_lot if pip_value_per_lot is not None else _DEFAULT_PIP_VALUE.get(symbol, 10.0)
    risk_amount = equity * (risk_pct / 100.0)
    raw_lots = risk_amount / (sl_pips * pv)

    # Floor to 0.01 — never overshoot the risk amount
    lots = math.floor(raw_lots * 100) / 100
    clamped = False

    if lots < min_lot:
        lots = min_lot
        clamped = True
    elif lots > max_lot:
        lots = max_lot
        clamped = True

    logger.info(
        "Position size: %s  equity=%.2f  risk=%.1f%% (%.2f)  "
        "sl=%.1fpip  pv=%.2f/lot  raw=%.4f → lots=%.2f%s",
        symbol, equity, risk_pct, risk_amount,
        sl_pips, pv, raw_lots, lots,
        " [CLAMPED]" if clamped else "",
    )

    return SizingResult(
        lots=lots,
        equity=equity,
        risk_pct=risk_pct,
        risk_amount=risk_amount,
        sl_pips=sl_pips,
        pip_value=pv,
        raw_lots=raw_lots,
        clamped=clamped,
        valid=True,
    )

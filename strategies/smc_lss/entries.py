"""
SMC-LSS_v0 — Supply/Demand Shift + Fair Value Gap components.

detect_fvg(candles, displacement_index, direction) -> (low, high) | None
detect_supply_demand_shift(...) -> SupplyDemandShiftEvent | None

Per spec:
    Bullish: Sweep low + displacement candle + previous swing high break
             + pullback into displacement FVG
    Bearish: mirror

FVG (Fair Value Gap) uses the standard 3-candle definition, with the
displacement candle as the middle candle:
    Bullish FVG: gap = [candles[d-1].high, candles[d+1].low], valid iff
                 candles[d+1].low > candles[d-1].high.
    Bearish FVG: gap = [candles[d+1].high, candles[d-1].low], valid iff
                 candles[d-1].low > candles[d+1].high.

A "pullback into the FVG" is confirmed on the first subsequent CLOSED
candle whose range overlaps the FVG zone — evaluated by scanning forward
only through candles already closed as of the caller's current index
(no lookahead).
"""

from __future__ import annotations

from dataclasses import dataclass

from .liquidity import LiquiditySweepEvent


@dataclass
class SupplyDemandShiftEvent:
    timestamp: object
    symbol: str
    direction: str          # 'long' | 'short'
    sweep_level: float
    structure_level: float  # the swing high/low broken by displacement
    fvg_low: float
    fvg_high: float
    pullback_price: float
    pullback_index: int


def detect_fvg(candles: list[dict], displacement_index: int, direction: str) -> "tuple[float, float] | None":
    """Return (fvg_low, fvg_high) for the 3-candle gap centered on the
    displacement candle, or None if no gap exists / insufficient bars."""
    if displacement_index - 1 < 0 or displacement_index + 1 >= len(candles):
        return None

    before = candles[displacement_index - 1]
    after = candles[displacement_index + 1]

    if direction == "long":
        gap_low = float(before["high"])
        gap_high = float(after["low"])
    elif direction == "short":
        gap_low = float(after["high"])
        gap_high = float(before["low"])
    else:
        return None

    if gap_high > gap_low:
        return gap_low, gap_high
    return None


def detect_supply_demand_shift(
    candles: list[dict],
    *,
    symbol: str,
    sweep: LiquiditySweepEvent,
    displacement_index: int,
    structure_level: float,
    direction: str,
    as_of_index: int,
) -> "SupplyDemandShiftEvent | None":
    """
    Confirm a supply/demand shift: sweep + displacement (already located by
    the caller) + a swing-structure break + a pullback into the
    displacement candle's FVG, observed by `as_of_index` (inclusive).
    """
    fvg = detect_fvg(candles, displacement_index, direction)
    if fvg is None:
        return None
    fvg_low, fvg_high = fvg

    scan_start = displacement_index + 2
    scan_end = min(as_of_index, len(candles) - 1)
    for i in range(scan_start, scan_end + 1):
        bar = candles[i]
        low = float(bar["low"])
        high = float(bar["high"])
        overlaps = low <= fvg_high and high >= fvg_low
        if not overlaps:
            continue
        pullback_price = max(low, fvg_low) if direction == "long" else min(high, fvg_high)
        return SupplyDemandShiftEvent(
            timestamp=bar.get("timestamp"),
            symbol=symbol,
            direction=direction,
            sweep_level=sweep.swept_level,
            structure_level=structure_level,
            fvg_low=fvg_low,
            fvg_high=fvg_high,
            pullback_price=pullback_price,
            pullback_index=i,
        )
    return None

"""
risk_model.py
Calculates R-multiple outcome for a trade.
"""

from typing import Dict, List, Optional
import polars as pl


def evaluate_r_multiple(
    future_candles: pl.DataFrame,
    entry: float,
    stop: float,
    target: float,
    direction: str,
) -> Optional[float]:
    """
    Walk forward through future price action and determine R-multiple outcome.

    Returns:
        result_r (float): positive for win, negative for loss, None if not resolved
    """
    if future_candles.is_empty():
        return None

    risk = abs(entry - stop)
    if risk == 0:
        return None

    for row in future_candles.iter_rows(named=True):
        high = row["high"]
        low = row["low"]

        if direction == "LONG":
            if low <= stop:
                return -1.0  # Hit stop loss
            if high >= target:
                return (target - entry) / risk
        else:  # SHORT
            if high >= stop:
                return -1.0
            if low <= target:
                return (entry - target) / risk

    return None  # Trade still open at end of data

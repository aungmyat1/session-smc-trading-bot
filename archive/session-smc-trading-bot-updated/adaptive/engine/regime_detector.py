"""
Adaptive Session Engine v1 — Market Regime Detector.

Classifies current market condition as TRENDING | BREAKOUT | RANGING | UNSAFE.
Pure Python — no numpy/pandas dependency.

Public API:
    detect_regime(candles, spread_pips) -> dict
"""

from __future__ import annotations

# ── Constants ─────────────────────────────────────────────────────────────────

ATR_PERIOD = 14
ADX_PERIOD = 14

ADX_TRENDING = 25.0
ADX_RANGING = 20.0
ATR_PCT_HIGH = 0.005  # > 0.5%  of price
ATR_PCT_LOW = 0.002  # < 0.2%  of price
MAX_SPREAD_PIPS = 3.0  # above this = UNSAFE


# ── Internal helpers ──────────────────────────────────────────────────────────


def _true_range(c: dict, prev_close: float) -> float:
    h, l, pc = c["high"], c["low"], prev_close
    return max(h - l, abs(h - pc), abs(l - pc))


def _wilder_smooth(values: list[float], period: int) -> list[float]:
    """Wilder smoothing (equivalent to EMA with alpha=1/period)."""
    if len(values) < period:
        return []
    result: list[float] = []
    # seed with simple mean of first `period` values
    seed = sum(values[:period]) / period
    result.append(seed)
    for v in values[period:]:
        result.append(result[-1] * (period - 1) / period + v / period)
    return result


def _compute_atr(candles: list[dict], period: int = ATR_PERIOD) -> list[float]:
    if len(candles) < period + 1:
        return []
    trs = [
        _true_range(candles[i], candles[i - 1]["close"]) for i in range(1, len(candles))
    ]
    return _wilder_smooth(trs, period)


def _compute_adx(
    candles: list[dict], period: int = ADX_PERIOD
) -> tuple[float, float, float]:
    """
    Returns (adx, plus_di, minus_di) for the final bar.
    Needs at least 2*period+1 candles for a stable reading.
    Returns (0, 0, 0) if insufficient data.
    """
    if len(candles) < 2 * period + 1:
        return 0.0, 0.0, 0.0

    plus_dms: list[float] = []
    minus_dms: list[float] = []
    trs: list[float] = []

    for i in range(1, len(candles)):
        h, l = candles[i]["high"], candles[i]["low"]
        ph, pl = candles[i - 1]["high"], candles[i - 1]["low"]
        pc = candles[i - 1]["close"]

        up_move = h - ph
        down_move = pl - l

        plus_dm = up_move if (up_move > down_move and up_move > 0) else 0.0
        minus_dm = down_move if (down_move > up_move and down_move > 0) else 0.0

        plus_dms.append(plus_dm)
        minus_dms.append(minus_dm)
        trs.append(_true_range(candles[i], pc))

    atr_s = _wilder_smooth(trs, period)
    pdm_s = _wilder_smooth(plus_dms, period)
    mdm_s = _wilder_smooth(minus_dms, period)

    if not atr_s or atr_s[-1] == 0:
        return 0.0, 0.0, 0.0

    plus_di = 100.0 * pdm_s[-1] / atr_s[-1]
    minus_di = 100.0 * mdm_s[-1] / atr_s[-1]
    di_sum = plus_di + minus_di

    if di_sum == 0:
        return 0.0, plus_di, minus_di

    dxs: list[float] = []
    n = min(len(atr_s), len(pdm_s), len(mdm_s))
    for j in range(n):
        if atr_s[j] == 0:
            dxs.append(0.0)
            continue
        pdi = 100.0 * pdm_s[j] / atr_s[j]
        mdi = 100.0 * mdm_s[j] / atr_s[j]
        s = pdi + mdi
        dxs.append(100.0 * abs(pdi - mdi) / s if s else 0.0)

    adx_s = _wilder_smooth(dxs, period)
    adx = adx_s[-1] if adx_s else 0.0

    return adx, plus_di, minus_di


# ── ATR expansion detection ───────────────────────────────────────────────────


def _atr_expanding(atr_series: list[float], lookback: int = 3) -> bool:
    """True if ATR has been rising for the last `lookback` readings."""
    if len(atr_series) < lookback + 1:
        return False
    return all(atr_series[-i] > atr_series[-i - 1] for i in range(1, lookback + 1))


# ── Public API ────────────────────────────────────────────────────────────────


def detect_regime(
    candles: list[dict],
    spread_pips: float = 0.0,
    atr_period: int = ATR_PERIOD,
    adx_period: int = ADX_PERIOD,
) -> dict:
    """
    Classify market regime from a list of OHLCV candle dicts.

    Args:
        candles:     List of dicts with keys: open, high, low, close, volume.
                     At least 2*(adx_period)+1 bars needed for a stable reading.
                     Pass candles in chronological order (oldest first).
        spread_pips: Current spread in pips. ≥ MAX_SPREAD_PIPS → UNSAFE.
        atr_period:  ATR smoothing period (default 14).
        adx_period:  ADX smoothing period (default 14).

    Returns:
        {
            "regime":     "TRENDING" | "BREAKOUT" | "RANGING" | "UNSAFE",
            "confidence": float (0.0–1.0),
            "adx":        float,
            "plus_di":    float,
            "minus_di":   float,
            "atr_pct":    float,   # ATR as % of close price
            "atr_expanding": bool,
        }
    """
    if spread_pips >= MAX_SPREAD_PIPS:
        return {
            "regime": "UNSAFE",
            "confidence": 1.0,
            "adx": 0.0,
            "plus_di": 0.0,
            "minus_di": 0.0,
            "atr_pct": 0.0,
            "atr_expanding": False,
        }

    min_bars = 2 * adx_period + 1
    if len(candles) < min_bars:
        return {
            "regime": "UNSAFE",
            "confidence": 0.5,
            "adx": 0.0,
            "plus_di": 0.0,
            "minus_di": 0.0,
            "atr_pct": 0.0,
            "atr_expanding": False,
        }

    adx, plus_di, minus_di = _compute_adx(candles, adx_period)
    atr_series = _compute_atr(candles, atr_period)
    atr_val = atr_series[-1] if atr_series else 0.0
    close = candles[-1]["close"]
    atr_pct = atr_val / close if close else 0.0
    expanding = _atr_expanding(atr_series)

    # ── Classification ────────────────────────────────────────────────────────
    if adx >= ADX_TRENDING and expanding:
        regime = "TRENDING"
        confidence = min(1.0, (adx - ADX_TRENDING) / 25.0 + 0.6)
    elif adx >= ADX_RANGING and atr_pct >= ATR_PCT_HIGH and expanding:
        regime = "BREAKOUT"
        confidence = min(1.0, (atr_pct - ATR_PCT_HIGH) / 0.005 + 0.6)
    elif adx < ADX_RANGING and ATR_PCT_LOW <= atr_pct < ATR_PCT_HIGH:
        regime = "RANGING"
        confidence = min(1.0, (ADX_RANGING - adx) / 20.0 + 0.5)
    else:
        regime = "UNSAFE"
        confidence = 0.4

    return {
        "regime": regime,
        "confidence": round(confidence, 4),
        "adx": round(adx, 4),
        "plus_di": round(plus_di, 4),
        "minus_di": round(minus_di, 4),
        "atr_pct": round(atr_pct, 6),
        "atr_expanding": expanding,
    }

"""
SA-02 — 4H Higher-Timeframe Bias Filter.

htf_bias(candles_4h, before_dt, swing_n=2)
  Returns 'bullish', 'bearish', or 'neutral'.

Lookahead rule (hard gate):
  A 4H bar opens at T and CLOSES at T + 4h.
  A bar may only be used once its close time <= before_dt.
  Cutoff: bar_open_time <= before_dt - timedelta(hours=4)
  Using bar_open_time alone would include a still-forming bar — that is lookahead.

Swing confirmation:
  Strict inequality (>) on every neighbour — equal highs or lows do NOT confirm a swing.
  Both sides (n left, n right) must be fully formed; the inner scan loop
  range(n, len-n) enforces this automatically.

Bias rules:
  Bullish: latest_SH > prev_SH  AND  latest_SL > prev_SL  (HH + HL)
  Bearish: latest_SH < prev_SH  AND  latest_SL < prev_SL  (LH + LL)
  Neutral: mixed, insufficient data, or equal swing values
"""

from datetime import datetime, timedelta, timezone

_UTC = timezone.utc


# ── Internal helpers ──────────────────────────────────────────────────────────

def _parse_utc(t) -> datetime:
    if isinstance(t, datetime):
        return t if t.tzinfo else t.replace(tzinfo=_UTC)
    return datetime.fromisoformat(str(t).replace("Z", "+00:00"))


def _swing_highs(highs: list[float], n: int) -> list[int]:
    """
    Return indices of confirmed swing highs.

    H[i] is a swing high iff:
      H[i] > H[i-k]  for k in 1..n  (n completed bars to the left)
      H[i] > H[i+k]  for k in 1..n  (n completed bars to the right)

    Strict inequality: equal highs do NOT qualify.
    """
    out: list[int] = []
    ln = len(highs)
    for i in range(n, ln - n):
        if (all(highs[i] > highs[i - k] for k in range(1, n + 1)) and
                all(highs[i] > highs[i + k] for k in range(1, n + 1))):
            out.append(i)
    return out


def _swing_lows(lows: list[float], n: int) -> list[int]:
    """
    Return indices of confirmed swing lows.

    L[i] is a swing low iff:
      L[i] < L[i-k]  for k in 1..n
      L[i] < L[i+k]  for k in 1..n

    Strict inequality: equal lows do NOT qualify.
    """
    out: list[int] = []
    ln = len(lows)
    for i in range(n, ln - n):
        if (all(lows[i] < lows[i - k] for k in range(1, n + 1)) and
                all(lows[i] < lows[i + k] for k in range(1, n + 1))):
            out.append(i)
    return out


# ── Public API ────────────────────────────────────────────────────────────────

def htf_bias(
    candles_4h: list[dict],
    before_dt: datetime,
    swing_n: int = 2,
) -> str:
    """
    Classify 4H structure as 'bullish', 'bearish', or 'neutral'.

    Args:
        candles_4h:  list of 4H bars, each with keys 'time', 'high', 'low'.
                     May be unsorted — sorted internally by open time.
        before_dt:   the timestamp of the current (M15) bar being evaluated.
                     Only 4H bars that have fully CLOSED by this time are used.
        swing_n:     number of bars required on each side of a swing pivot.
                     Default 2; larger values produce fewer but higher-quality swings.

    Returns:
        'bullish'  — HH (higher high) AND HL (higher low) on last two confirmed swings
        'bearish'  — LH (lower high)  AND LL (lower low)  on last two confirmed swings
        'neutral'  — mixed structure, equal pivots, or insufficient confirmed swings
    """
    # ── 1. Filter to fully closed 4H bars ────────────────────────────────────
    #   close_time = open_time + 4h  →  include if open_time <= before_dt - 4h
    cutoff = _parse_utc(before_dt) - timedelta(hours=4)
    bars = [c for c in candles_4h if _parse_utc(c["time"]) <= cutoff]

    # Minimum: need n bars each side of a pivot → at least 2n+1 bars for any swing
    if len(bars) < 2 * swing_n + 1:
        return "neutral"

    # ── 2. Sort chronologically (defensive — input may be unsorted) ───────────
    bars.sort(key=lambda c: _parse_utc(c["time"]))

    # ── 3. Swing detection ────────────────────────────────────────────────────
    highs = [c["high"] for c in bars]
    lows = [c["low"] for c in bars]

    sh_idx = _swing_highs(highs, swing_n)
    sl_idx = _swing_lows(lows, swing_n)

    if len(sh_idx) < 2 or len(sl_idx) < 2:
        return "neutral"

    # ── 4. Bias classification on last two confirmed pivots ───────────────────
    sh_prev, sh_last = highs[sh_idx[-2]], highs[sh_idx[-1]]
    sl_prev, sl_last = lows[sl_idx[-2]], lows[sl_idx[-1]]

    if sh_last > sh_prev and sl_last > sl_prev:
        return "bullish"
    if sh_last < sh_prev and sl_last < sl_prev:
        return "bearish"
    return "neutral"

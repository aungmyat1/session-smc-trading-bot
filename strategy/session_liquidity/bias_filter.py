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

from bisect import bisect_right
from collections import OrderedDict
from datetime import datetime, timedelta, timezone

_UTC = timezone.utc

# ── Per-call-site cache ────────────────────────────────────────────────────────
#
# Performance note (TASK-HTF-BIAS-OPTIMIZATION):
#   htf_bias() is invoked once per signal bar with the SAME `candles_4h` list
#   object held for the life of a run (verified across every caller: bias_filter's
#   sole consumers pass one fixed 4H dataset for the whole backtest/replay — see
#   strategy/session_liquidity/session_strategy.py, scripts/dry_run.py,
#   scripts/replay_st_a2_d1.py, scripts/replay_6m.py). The only thing that changes
#   call-to-call is `before_dt`. The original implementation re-filtered,
#   re-sorted, and re-scanned the ENTIRE candles_4h list on every call —
#   O(bars_total) per call, O(bars_total * calls) overall.
#
#   Swing-high/low confirmation at index i depends ONLY on the `swing_n` bars
#   immediately to its left and right (see _swing_highs/_swing_lows docstrings).
#   Because the "visible" bar set for any before_dt is always a chronological
#   PREFIX of the full sorted series (bars with open_time <= cutoff), a swing at
#   index i is confirmed within a given prefix of length `idx` iff i + swing_n <
#   idx — and, critically, that boolean is IDENTICAL to the boolean computed
#   against the full sorted series, because the check never reads past i +
#   swing_n. So we can sort + compute ALL swing points ONCE per (list identity,
#   swing_n), then answer any before_dt query in O(log n) via bisect on the
#   cutoff and on the precomputed swing-index lists. This is value-identical to
#   the original per-call full rescan (see
#   tests/session_liquidity/test_bias_filter_perf.py) and introduces no
#   lookahead: a swing is only used once every bar in its confirmation window
#   has itself closed by `before_dt`, exactly as in the original algorithm.
#
#   Cache key = id(candles_4h). Plain `list` objects cannot be weakly
#   referenced, so instead of a weakref-based eviction we hold a STRONG
#   reference to the original list in the cache entry itself (`entry["obj"]`)
#   and validate every lookup with an `is` identity check. Holding the strong
#   reference is what makes the identity check safe: as long as the entry is
#   cached, the object stays alive, so CPython can never reuse its id() for a
#   different object underneath us — the classic id-reuse hazard is
#   structurally impossible here, not just improbable. A small LRU cap bounds
#   memory (this module only ever sees a handful of distinct candles_4h
#   datasets per process — one per backtest/replay run).
_CACHE_MAXSIZE = 8
_cache: "OrderedDict[int, dict]" = OrderedDict()


def _get_cache(candles_4h: list[dict], swing_n: int) -> dict:
    key = id(candles_4h)
    entry = _cache.get(key)
    if (
        entry is not None
        and entry["swing_n"] == swing_n
        and entry["len"] == len(candles_4h)
        and entry["obj"] is candles_4h
    ):
        _cache.move_to_end(key)
        return entry

    parsed = sorted(
        ((_parse_utc(c["time"]), c["high"], c["low"]) for c in candles_4h),
        key=lambda p: p[0],
    )
    times = [p[0] for p in parsed]
    highs = [p[1] for p in parsed]
    lows = [p[2] for p in parsed]

    entry = {
        "swing_n": swing_n,
        "len": len(candles_4h),
        "obj": candles_4h,
        "times": times,
        "highs": highs,
        "lows": lows,
        "sh_idx": _swing_highs(highs, swing_n),
        "sl_idx": _swing_lows(lows, swing_n),
    }
    _cache[key] = entry
    _cache.move_to_end(key)
    if len(_cache) > _CACHE_MAXSIZE:
        _cache.popitem(last=False)
    return entry


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
    # ── 1. Locate fully closed 4H bars via the precomputed/cached structure ───
    #   close_time = open_time + 4h  →  include if open_time <= before_dt - 4h
    cache = _get_cache(candles_4h, swing_n)
    times, highs, lows = cache["times"], cache["highs"], cache["lows"]
    sh_idx_all, sl_idx_all = cache["sh_idx"], cache["sl_idx"]

    cutoff = _parse_utc(before_dt) - timedelta(hours=4)
    idx = bisect_right(times, cutoff)   # count of bars with open_time <= cutoff

    # Minimum: need n bars each side of a pivot → at least 2n+1 bars for any swing
    if idx < 2 * swing_n + 1:
        return "neutral"

    # ── 2/3. Swing visibility ───────────────────────────────────────────────
    #   A swing at index i (in the full sorted series) is confirmed within the
    #   first `idx` bars iff i + swing_n < idx — identical to the original
    #   per-call range(n, len(bars)-n) bound with len(bars) == idx.
    visible_bound = idx - swing_n   # i is visible iff i < visible_bound
    sh_count = bisect_right(sh_idx_all, visible_bound - 1)
    sl_count = bisect_right(sl_idx_all, visible_bound - 1)

    if sh_count < 2 or sl_count < 2:
        return "neutral"

    # ── 4. Bias classification on last two confirmed pivots ───────────────────
    sh_prev, sh_last = highs[sh_idx_all[sh_count - 2]], highs[sh_idx_all[sh_count - 1]]
    sl_prev, sl_last = lows[sl_idx_all[sl_count - 2]], lows[sl_idx_all[sl_count - 1]]

    if sh_last > sh_prev and sl_last > sl_prev:
        return "bullish"
    if sh_last < sh_prev and sl_last < sl_prev:
        return "bearish"
    return "neutral"

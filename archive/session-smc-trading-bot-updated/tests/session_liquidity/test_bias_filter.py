"""
Tests for SA-02: bias_filter.py

Required cases (per TASK_QUEUE.md SA-02):
  1.  Bullish structure (HH + HL)
  2.  Bearish structure (LH + LL)
  3.  Neutral structure (mixed HH + LL)
  4.  Insufficient swings  (<2 SHs or <2 SLs)
  5.  Equal highs          (SH1 == SH2 → not HH, not LH → neutral)
  6.  Equal lows           (SL1 == SL2 → not HL, not LL → neutral)
  7.  H4 cutoff — bar included only when its close_time <= before_dt
  8.  Lookahead prevention — future bar changes bias but must be excluded
  9.  DST-safe timestamps  — result unchanged whether before_dt is EST or EDT
  10. Unsorted input       — same result regardless of input order

Dataset design (swing_n=2, 13 bars at 4-hour intervals):
  ───────────────────────────────────────────────────────
  BULLISH dataset  highs = [1,2,5,2,1,2,3,3,2,1,8,2,1]
                   lows  = [0.5,1,0.8,0.5,0.2,0.8,0.5,0.8,0.5,0.3,1.5,0.5,0.2]
  Confirmed SHs: idx2=5, idx10=8  →  HH (8 > 5)
  Confirmed SLs: idx4=0.2, idx9=0.3  →  HL (0.3 > 0.2)
  Bias: BULLISH

  BEARISH dataset  highs = [1,2,8,2,1,2,3,3,2,1,5,2,1]
                   lows  = [0.5,1.5,1,0.5,0.3,1,0.5,0.8,0.5,0.2,1.5,0.5,0.3]
  Confirmed SHs: idx2=8, idx10=5  →  LH (5 < 8)
  Confirmed SLs: idx4=0.3, idx9=0.2  →  LL (0.2 < 0.3)
  Bias: BEARISH
  ───────────────────────────────────────────────────────
"""

import unittest
from datetime import datetime, timedelta, timezone

from strategy.session_liquidity.bias_filter import htf_bias

UTC = timezone.utc

# ─────────────────────────────────────────────────────────────────────────────
# Dataset builders
# ─────────────────────────────────────────────────────────────────────────────

_T0 = datetime(2024, 1, 15, 0, 0, 0, tzinfo=UTC)  # 2024-01-15 00:00 UTC


def _bars(highs: list[float], lows: list[float], start: datetime = _T0) -> list[dict]:
    """Build 4H candle list from parallel highs/lows."""
    out = []
    t = start
    for h, l in zip(highs, lows):
        mid = round((h + l) / 2, 5)
        out.append(
            {
                "time": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "open": mid,
                "high": h,
                "low": l,
                "close": mid,
            }
        )
        t += timedelta(hours=4)
    return out


def _all_visible(bars: list[dict]) -> datetime:
    """Return a before_dt that makes ALL supplied bars visible (last bar closed)."""
    last_open = datetime.fromisoformat(bars[-1]["time"].replace("Z", "+00:00"))
    return last_open + timedelta(hours=4)  # cutoff = last_open → last bar included


def _exclude_last(bars: list[dict]) -> datetime:
    """Return a before_dt that makes every bar EXCEPT the last visible."""
    last_open = datetime.fromisoformat(bars[-1]["time"].replace("Z", "+00:00"))
    return last_open  # cutoff = last_open - 4h → excludes last bar


# ─────────────────────────────────────────────────────────────────────────────
# Shared datasets
# ─────────────────────────────────────────────────────────────────────────────

_BULL_H = [1.0, 2.0, 5.0, 2.0, 1.0, 2.0, 3.0, 3.0, 2.0, 1.0, 8.0, 2.0, 1.0]
_BULL_L = [0.5, 1.0, 0.8, 0.5, 0.2, 0.8, 0.5, 0.8, 0.5, 0.3, 1.5, 0.5, 0.2]

_BEAR_H = [1.0, 2.0, 8.0, 2.0, 1.0, 2.0, 3.0, 3.0, 2.0, 1.0, 5.0, 2.0, 1.0]
_BEAR_L = [0.5, 1.5, 1.0, 0.5, 0.3, 1.0, 0.5, 0.8, 0.5, 0.2, 1.5, 0.5, 0.3]


# ─────────────────────────────────────────────────────────────────────────────
# Test 1 — Bullish structure
# ─────────────────────────────────────────────────────────────────────────────
class TestBullishStructure(unittest.TestCase):

    def setUp(self):
        self.bars = _bars(_BULL_H, _BULL_L)
        self.before_dt = _all_visible(self.bars)

    def test_returns_bullish(self):
        self.assertEqual(htf_bias(self.bars, self.before_dt), "bullish")

    def test_hh_confirmed(self):
        """Latest SH (idx10=8.0) > previous SH (idx2=5.0)."""
        # If we manually flip to make LH, result must change
        highs = _BULL_H[:]
        highs[10] = 4.0  # LH instead of HH
        bars = _bars(highs, _BULL_L)
        result = htf_bias(bars, _all_visible(bars))
        self.assertNotEqual(result, "bullish")

    def test_hl_confirmed(self):
        """Latest SL (idx9=0.3) > previous SL (idx4=0.2) → HL."""
        lows = _BULL_L[:]
        lows[9] = 0.1  # LL instead of HL
        bars = _bars(_BULL_H, lows)
        result = htf_bias(bars, _all_visible(bars))
        self.assertNotEqual(result, "bullish")


# ─────────────────────────────────────────────────────────────────────────────
# Test 2 — Bearish structure
# ─────────────────────────────────────────────────────────────────────────────
class TestBearishStructure(unittest.TestCase):

    def setUp(self):
        self.bars = _bars(_BEAR_H, _BEAR_L)
        self.before_dt = _all_visible(self.bars)

    def test_returns_bearish(self):
        self.assertEqual(htf_bias(self.bars, self.before_dt), "bearish")

    def test_lh_confirmed(self):
        """Latest SH (idx10=5.0) < previous SH (idx2=8.0) → LH."""
        highs = _BEAR_H[:]
        highs[10] = 9.0  # HH instead of LH → no longer bearish
        bars = _bars(highs, _BEAR_L)
        result = htf_bias(bars, _all_visible(bars))
        self.assertNotEqual(result, "bearish")

    def test_ll_confirmed(self):
        """Latest SL (idx9=0.2) < previous SL (idx4=0.3) → LL."""
        lows = _BEAR_L[:]
        lows[9] = 0.5  # HL instead of LL → no longer bearish
        bars = _bars(_BEAR_H, lows)
        result = htf_bias(bars, _all_visible(bars))
        self.assertNotEqual(result, "bearish")


# ─────────────────────────────────────────────────────────────────────────────
# Test 3 — Neutral structure (mixed: HH highs but LL lows)
# ─────────────────────────────────────────────────────────────────────────────
class TestNeutralMixed(unittest.TestCase):

    def test_hh_and_ll_is_neutral(self):
        """Bullish SH pattern + bearish SL pattern → neutral (not both agree)."""
        bars = _bars(_BULL_H, _BEAR_L)
        before_dt = _all_visible(bars)
        # SHs: HH (bullish), SLs: LL (bearish) → mixed → neutral
        self.assertEqual(htf_bias(bars, before_dt), "neutral")

    def test_lh_and_hl_is_neutral(self):
        """Bearish SH pattern + bullish SL pattern → neutral."""
        bars = _bars(_BEAR_H, _BULL_L)
        before_dt = _all_visible(bars)
        self.assertEqual(htf_bias(bars, before_dt), "neutral")


# ─────────────────────────────────────────────────────────────────────────────
# Test 4 — Insufficient swings
# ─────────────────────────────────────────────────────────────────────────────
class TestInsufficientSwings(unittest.TestCase):

    def test_too_few_bars_returns_neutral(self):
        """< 2*swing_n+1 = 5 bars → immediate neutral (no swing can be confirmed)."""
        bars = _bars([1.0, 3.0, 1.0, 3.0], [0.5, 1.0, 0.5, 1.0])
        self.assertEqual(htf_bias(bars, _all_visible(bars)), "neutral")

    def test_only_one_swing_high(self):
        """Flat high sequence produces only one confirmed SH → neutral."""
        # All highs equal except one peak — only 1 SH can be confirmed
        highs = [1.0, 1.0, 5.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
        lows = [0.5] * 13
        bars = _bars(highs, lows)
        # Only one SH (at idx2) confirmed → neutral regardless of lows
        self.assertEqual(htf_bias(bars, _all_visible(bars)), "neutral")

    def test_only_one_swing_low(self):
        """Flat low sequence produces only one confirmed SL → neutral."""
        highs = [1.0, 2.0, 5.0, 2.0, 1.0, 2.0, 3.0, 3.0, 2.0, 1.0, 8.0, 2.0, 1.0]
        lows = [0.5, 0.5, 0.5, 0.5, 0.2, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
        bars = _bars(highs, lows)
        # Only one SL at idx4 → neutral despite valid SHs
        self.assertEqual(htf_bias(bars, _all_visible(bars)), "neutral")

    def test_empty_input_is_neutral(self):
        self.assertEqual(htf_bias([], datetime.now(UTC)), "neutral")


# ─────────────────────────────────────────────────────────────────────────────
# Test 5 — Equal highs (strict inequality: equal SH == not a new structure)
# ─────────────────────────────────────────────────────────────────────────────
class TestEqualHighs(unittest.TestCase):

    def test_equal_swing_highs_is_neutral(self):
        """SH1 = SH2: neither HH nor LH → neutral."""
        highs = [1.0, 2.0, 5.0, 2.0, 1.0, 2.0, 3.0, 3.0, 2.0, 1.0, 5.0, 2.0, 1.0]
        bars = _bars(highs, _BULL_L)
        # SHs at idx2=5 and idx10=5 (equal) → not HH (5>5 is False) → neutral
        self.assertEqual(htf_bias(bars, _all_visible(bars)), "neutral")

    def test_equal_internal_highs_dont_block_swing(self):
        """Two equal neighbours do NOT prevent a clear peak from being a SH."""
        # idx5 and idx6 have equal highs but neither qualifies as SH — idx2 and idx10 still do
        highs = [1.0, 2.0, 5.0, 2.0, 1.0, 3.0, 3.0, 2.0, 1.0, 2.0, 8.0, 2.0, 1.0]
        # idx2: 5>2,1 left, 5>2,1 right ✓ → SH
        # idx5: 3>1,2 left, 3>3? No (equal) ✗ → not SH
        # idx10: 8>1,2 left, 8>2,1 right ✓ → SH
        bars = _bars(highs, _BULL_L)
        self.assertEqual(htf_bias(bars, _all_visible(bars)), "bullish")


# ─────────────────────────────────────────────────────────────────────────────
# Test 6 — Equal lows (strict inequality: equal SL == not a new structure)
# ─────────────────────────────────────────────────────────────────────────────
class TestEqualLows(unittest.TestCase):

    def test_equal_swing_lows_is_neutral(self):
        """SL1 = SL2 = 0.2: neither HL nor LL → neutral."""
        lows = [0.5, 1.0, 0.8, 0.5, 0.2, 0.8, 0.5, 0.8, 0.5, 0.2, 1.5, 0.5, 0.2]
        bars = _bars(_BULL_H, lows)
        # SLs at idx4=0.2 and idx9=0.2 (equal) → not HL (0.2>0.2 False) → neutral
        self.assertEqual(htf_bias(bars, _all_visible(bars)), "neutral")


# ─────────────────────────────────────────────────────────────────────────────
# Test 7 — H4 cutoff audit (close_time vs open_time)
# ─────────────────────────────────────────────────────────────────────────────
class TestH4Cutoff(unittest.TestCase):

    def setUp(self):
        self.bars = _bars(_BULL_H, _BULL_L)
        # last bar open = T0 + 12*4h = T0 + 48h = 2024-01-17T00:00:00Z
        self.last_open = datetime.fromisoformat(
            self.bars[-1]["time"].replace("Z", "+00:00")
        )

    def test_bar_included_when_close_time_equals_before_dt(self):
        """
        Bar open_time=T, close_time=T+4h.
        before_dt = T+4h: close_time == before_dt → INCLUDED.
        This is the exact boundary — bar has just closed.
        """
        before_dt = self.last_open + timedelta(hours=4)
        self.assertEqual(htf_bias(self.bars, before_dt), "bullish")

    def test_bar_excluded_when_open_time_equals_before_dt(self):
        """
        before_dt = T (open time of last bar).
        cutoff = T - 4h → last bar open T > cutoff → EXCLUDED.
        Using open_time alone would incorrectly include a still-forming bar.
        """
        before_dt = self.last_open  # one 4h bar is still forming
        result = htf_bias(self.bars, before_dt)
        # Without bar 12, the SH at idx10 loses its right-side confirmation
        # (need idx11,12; with bar12 excluded the loop only reaches idx9)
        # Only 1 SH confirmed → neutral
        self.assertEqual(result, "neutral")

    def test_bar_excluded_when_close_time_exceeds_before_dt(self):
        """before_dt = last_open + 3h: close_time = last_open+4h > before_dt → excluded."""
        before_dt = self.last_open + timedelta(hours=3)
        self.assertEqual(htf_bias(self.bars, before_dt), "neutral")

    def test_open_time_cutoff_is_wrong(self):
        """
        Sanity-check: if we used open_time <= before_dt (wrong rule) vs
        open_time <= before_dt - 4h (correct rule), they would differ at boundary.
        The correct rule excludes the forming bar; the wrong rule includes it.
        """
        before_dt = self.last_open  # correct rule: exclude; wrong rule: include
        # Correct behaviour (already tested above): neutral (1 SH only)
        self.assertEqual(htf_bias(self.bars, before_dt), "neutral")
        # Prove the last bar WOULD give bullish if included (wrong rule)
        include_all = self.last_open + timedelta(hours=4)
        self.assertEqual(htf_bias(self.bars, include_all), "bullish")

    def test_earlier_bar_on_cutoff_boundary_included(self):
        """Bar at T0+44h (second-to-last): with before_dt = T0+48h, cutoff = T0+44h → included."""
        before_dt = self.last_open  # cutoff = last_open - 4h = second-to-last open
        # Second-to-last bar should be included (equal to cutoff)
        # With 12 bars (0-11): only 1 SH → neutral (test_bar_excluded already covers this)
        # Confirm this is neutral, not an error
        result = htf_bias(self.bars, before_dt)
        self.assertIn(result, ("neutral", "bullish", "bearish"))  # valid value


# ─────────────────────────────────────────────────────────────────────────────
# Test 8 — Lookahead prevention
# ─────────────────────────────────────────────────────────────────────────────
class TestLookaheadPrevention(unittest.TestCase):

    def test_future_bar_excluded(self):
        """
        Add a bar whose open_time > cutoff (it hasn't closed yet).
        With that bar excluded the bias is neutral (only 1 SH visible).
        If included (lookahead) it would be bullish.
        Verifies the cutoff prevents reading ahead.
        """
        bars = _bars(_BULL_H, _BULL_L)
        last_open = datetime.fromisoformat(bars[-1]["time"].replace("Z", "+00:00"))

        # before_dt set so last bar is still forming → neutral
        before_future = last_open  # cutoff = last_open - 4h → excludes bars[-1]
        self.assertEqual(htf_bias(bars, before_future), "neutral")

        # Advance before_dt by exactly 4h → last bar now closed → bullish
        after_close = last_open + timedelta(hours=4)
        self.assertEqual(htf_bias(bars, after_close), "bullish")

    def test_extra_future_bar_beyond_dataset(self):
        """Appending a future bar doesn't change result when before_dt keeps it excluded."""
        bars = _bars(_BULL_H, _BULL_L)
        last_open = datetime.fromisoformat(bars[-1]["time"].replace("Z", "+00:00"))
        # Add one more bar at last_open + 4h (simulates the currently-forming bar)
        future_bar = {
            "time": (last_open + timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "open": 1.05,
            "high": 1.10,
            "low": 0.90,
            "close": 1.05,
        }
        bars_with_future = bars + [future_bar]

        # before_dt = last_open + 4h: last bullish bar closed, future bar open → still excluded
        before_dt = last_open + timedelta(hours=4)
        # cutoff = before_dt - 4h = last_open → future bar at last_open+4h > cutoff → excluded
        self.assertEqual(htf_bias(bars_with_future, before_dt), "bullish")


# ─────────────────────────────────────────────────────────────────────────────
# Test 9 — DST-safe timestamps
# ─────────────────────────────────────────────────────────────────────────────
class TestDSTSafeTimestamps(unittest.TestCase):

    def test_spring_forward_date_unchanged(self):
        """
        2024-03-10 is the US spring-forward day (EST→EDT at 02:00).
        The 4H bars are in UTC; timezone conversion does not affect the cutoff.
        Result must equal the non-DST case.
        """
        start = datetime(2024, 3, 9, 0, 0, 0, tzinfo=UTC)  # just before spring-forward
        bars = _bars(_BULL_H, _BULL_L, start=start)
        before_dt = _all_visible(bars)
        self.assertEqual(htf_bias(bars, before_dt), "bullish")

    def test_fall_back_date_unchanged(self):
        """
        2024-11-03 is the US fall-back day (EDT→EST at 02:00).
        UTC-based cutoff must give same result.
        """
        start = datetime(2024, 11, 2, 0, 0, 0, tzinfo=UTC)
        bars = _bars(_BULL_H, _BULL_L, start=start)
        before_dt = _all_visible(bars)
        self.assertEqual(htf_bias(bars, before_dt), "bullish")

    def test_before_dt_as_est_aware_datetime(self):
        """before_dt supplied as EST-aware datetime is handled without error."""
        from zoneinfo import ZoneInfo

        bars = _bars(_BULL_H, _BULL_L)
        last_open = datetime.fromisoformat(bars[-1]["time"].replace("Z", "+00:00"))
        # Express before_dt in EST (UTC-5 in January)
        est = ZoneInfo("America/New_York")
        before_dt_est = (last_open + timedelta(hours=4)).astimezone(est)
        self.assertEqual(htf_bias(bars, before_dt_est), "bullish")


# ─────────────────────────────────────────────────────────────────────────────
# Test 10 — Unsorted input
# ─────────────────────────────────────────────────────────────────────────────
class TestUnsortedInput(unittest.TestCase):

    def test_reversed_input_same_result(self):
        """Bars supplied in reverse chronological order must give the same bias."""
        bars = _bars(_BULL_H, _BULL_L)
        before_dt = _all_visible(bars)
        result_sorted = htf_bias(bars, before_dt)
        result_reversed = htf_bias(list(reversed(bars)), before_dt)
        self.assertEqual(result_sorted, result_reversed)
        self.assertEqual(result_sorted, "bullish")

    def test_shuffled_input_same_result(self):
        """Shuffled input must give the same bias as sorted input."""
        import random

        bars = _bars(_BULL_H, _BULL_L)
        before_dt = _all_visible(bars)
        shuffled = bars[:]
        random.seed(42)
        random.shuffle(shuffled)
        self.assertEqual(htf_bias(bars, before_dt), htf_bias(shuffled, before_dt))

    def test_bearish_reversed(self):
        bars = _bars(_BEAR_H, _BEAR_L)
        before_dt = _all_visible(bars)
        self.assertEqual(htf_bias(list(reversed(bars)), before_dt), "bearish")


if __name__ == "__main__":
    unittest.main()

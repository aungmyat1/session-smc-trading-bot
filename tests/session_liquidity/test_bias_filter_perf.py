"""
TASK-HTF-BIAS-OPTIMIZATION — regression tests.

Proves the cached/precomputed htf_bias() in
strategy/session_liquidity/bias_filter.py is VALUE-IDENTICAL to the original
O(bars_total) per-call algorithm, across:

  1. A full multi-year real dataset (EUR_USD_H4.csv / GBP_USD_H4.csv), queried
     at every single bar boundary in the file (not a handful of samples).
  2. Synthetic edge cases (unsorted input, empty input, exact cutoff boundary).
  3. An explicit no-lookahead check: results already computed for an earlier
     `before_dt` must not change after later (future-relative) bars are
     queried against the same cached list, and must not change if the cache
     is warmed in a different call order.

The OLD algorithm is preserved below as `_old_htf_bias` — a frozen,
uncached copy of the pre-optimization implementation — so this file
functions as the "before" reference without needing git stash.
"""

import csv
import os
import time
import unittest
from datetime import datetime, timedelta, timezone

from strategy.session_liquidity.bias_filter import htf_bias, _parse_utc as _new_parse_utc

UTC = timezone.utc
_DATA_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "historical"
)


# ─────────────────────────────────────────────────────────────────────────────
# Frozen reference implementation (pre-optimization algorithm, uncached)
# ─────────────────────────────────────────────────────────────────────────────

def _old_parse_utc(t) -> datetime:
    if isinstance(t, datetime):
        return t if t.tzinfo else t.replace(tzinfo=UTC)
    return datetime.fromisoformat(str(t).replace("Z", "+00:00"))


def _old_swing_highs(highs, n):
    out = []
    ln = len(highs)
    for i in range(n, ln - n):
        if (all(highs[i] > highs[i - k] for k in range(1, n + 1)) and
                all(highs[i] > highs[i + k] for k in range(1, n + 1))):
            out.append(i)
    return out


def _old_swing_lows(lows, n):
    out = []
    ln = len(lows)
    for i in range(n, ln - n):
        if (all(lows[i] < lows[i - k] for k in range(1, n + 1)) and
                all(lows[i] < lows[i + k] for k in range(1, n + 1))):
            out.append(i)
    return out


def _old_htf_bias(candles_4h, before_dt, swing_n=2) -> str:
    """Frozen copy of bias_filter.py's pre-optimization htf_bias()."""
    cutoff = _old_parse_utc(before_dt) - timedelta(hours=4)
    bars = [c for c in candles_4h if _old_parse_utc(c["time"]) <= cutoff]

    if len(bars) < 2 * swing_n + 1:
        return "neutral"

    bars.sort(key=lambda c: _old_parse_utc(c["time"]))

    highs = [c["high"] for c in bars]
    lows = [c["low"] for c in bars]

    sh_idx = _old_swing_highs(highs, swing_n)
    sl_idx = _old_swing_lows(lows, swing_n)

    if len(sh_idx) < 2 or len(sl_idx) < 2:
        return "neutral"

    sh_prev, sh_last = highs[sh_idx[-2]], highs[sh_idx[-1]]
    sl_prev, sl_last = lows[sl_idx[-2]], lows[sl_idx[-1]]

    if sh_last > sh_prev and sl_last > sl_prev:
        return "bullish"
    if sh_last < sh_prev and sl_last < sl_prev:
        return "bearish"
    return "neutral"


def _load_h4(symbol_file: str) -> list[dict]:
    path = os.path.join(_DATA_DIR, symbol_file)
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        return [
            {
                "time": row["time"],
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
            }
            for row in reader
        ]


# ─────────────────────────────────────────────────────────────────────────────
# Full-dataset equivalence — EUR_USD_H4 and GBP_USD_H4
# ─────────────────────────────────────────────────────────────────────────────

class TestFullDatasetEquivalence(unittest.TestCase):
    """
    For every bar-close boundary in a real multi-year 4H dataset, the cached
    htf_bias() must return exactly the same value as the frozen pre-optimization
    algorithm. Not sampled — every single bar boundary is checked.
    """

    def _assert_equivalent_across_dataset(self, filename: str):
        path = os.path.join(_DATA_DIR, filename)
        if not os.path.exists(path):
            self.skipTest(f"{filename} not present")

        candles = _load_h4(filename)
        self.assertGreater(len(candles), 200, f"{filename} too small for a meaningful check")

        mismatches = []
        for c in candles:
            before_dt = _new_parse_utc(c["time"]) + timedelta(hours=4)
            expected = _old_htf_bias(candles, before_dt)
            actual = htf_bias(candles, before_dt)
            if actual != expected:
                mismatches.append((c["time"], expected, actual))

        self.assertEqual(
            mismatches, [],
            f"{len(mismatches)} mismatches out of {len(candles)} query points "
            f"in {filename}: first few = {mismatches[:5]}",
        )

    def test_eurusd_h4_full_equivalence(self):
        self._assert_equivalent_across_dataset("EUR_USD_H4.csv")

    def test_gbpusd_h4_full_equivalence(self):
        self._assert_equivalent_across_dataset("GBP_USD_H4.csv")


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic edge-case equivalence
# ─────────────────────────────────────────────────────────────────────────────

class TestSyntheticEquivalence(unittest.TestCase):

    def _bars(self, n=40, start=datetime(2024, 1, 1, tzinfo=UTC)):
        import random
        random.seed(7)
        out = []
        t = start
        for _ in range(n):
            h = round(1.0 + random.random() * 0.5, 5)
            l = round(h - random.random() * 0.2, 5)
            out.append({
                "time": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "open": l, "high": h, "low": l, "close": l,
            })
            t += timedelta(hours=4)
        return out

    def test_every_cutoff_matches(self):
        bars = self._bars()
        for i, c in enumerate(bars):
            before_dt = _new_parse_utc(c["time"]) + timedelta(hours=4)
            self.assertEqual(
                htf_bias(bars, before_dt),
                _old_htf_bias(bars, before_dt),
                f"mismatch at bar {i}",
            )

    def test_unsorted_input_matches(self):
        bars = self._bars()
        shuffled = bars[::-1]
        before_dt = _new_parse_utc(bars[-1]["time"]) + timedelta(hours=4)
        self.assertEqual(htf_bias(shuffled, before_dt), _old_htf_bias(shuffled, before_dt))

    def test_empty_matches(self):
        self.assertEqual(htf_bias([], datetime.now(UTC)), _old_htf_bias([], datetime.now(UTC)))

    def test_different_swing_n_matches(self):
        bars = self._bars(n=60)
        for swing_n in (1, 2, 3, 5):
            before_dt = _new_parse_utc(bars[-1]["time"]) + timedelta(hours=4)
            self.assertEqual(
                htf_bias(bars, before_dt, swing_n=swing_n),
                _old_htf_bias(bars, before_dt, swing_n=swing_n),
                f"mismatch at swing_n={swing_n}",
            )

    def test_repeated_calls_on_same_list_are_stable(self):
        """Reusing the cache across many calls on the same list object must
        never drift from a fresh (uncached) computation."""
        bars = self._bars(n=80)
        for _ in range(3):  # repeat entire sweep multiple times to catch cache staleness
            for c in bars:
                before_dt = _new_parse_utc(c["time"]) + timedelta(hours=4)
                self.assertEqual(htf_bias(bars, before_dt), _old_htf_bias(bars, before_dt))


# ─────────────────────────────────────────────────────────────────────────────
# No-lookahead guarantee under caching
# ─────────────────────────────────────────────────────────────────────────────

class TestNoLookaheadUnderCache(unittest.TestCase):
    """
    Caching precomputes swing structure using the FULL supplied list, but must
    never let a bar's data leak into a bias computed for an earlier cutoff.
    This is the single highest-risk correctness property introduced by the
    optimization — verified independently of the full-equivalence tests above.
    """

    def _bars(self, highs, lows, start=datetime(2024, 1, 1, tzinfo=UTC)):
        out = []
        t = start
        for h, l in zip(highs, lows):
            out.append({
                "time": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "open": l, "high": h, "low": l, "close": l,
            })
            t += timedelta(hours=4)
        return out

    def test_result_for_early_cutoff_unaffected_by_later_query(self):
        """Querying a later before_dt (which warms/extends the cache) must not
        change the result previously obtained for an earlier before_dt."""
        highs = [1.0, 2.0, 5.0, 2.0, 1.0, 2.0, 3.0, 3.0, 2.0, 1.0, 8.0, 2.0, 1.0]
        lows = [0.5, 1.0, 0.8, 0.5, 0.2, 0.8, 0.5, 0.8, 0.5, 0.3, 1.5, 0.5, 0.2]
        bars = self._bars(highs, lows)

        early_before_dt = _new_parse_utc(bars[8]["time"]) + timedelta(hours=4)
        early_result_pre = htf_bias(bars, early_before_dt)

        # Now query a much later cutoff on the SAME list object — this forces
        # the cache to hold full-series swing data that extends well past the
        # early cutoff.
        late_before_dt = _new_parse_utc(bars[-1]["time"]) + timedelta(hours=4)
        htf_bias(bars, late_before_dt)

        early_result_post = htf_bias(bars, early_before_dt)

        self.assertEqual(early_result_pre, early_result_post)
        self.assertEqual(early_result_pre, _old_htf_bias(bars, early_before_dt))

    def test_appending_future_bar_never_changes_earlier_result(self):
        """A bar added past a given cutoff must never affect the bias computed
        for that (earlier) cutoff, even though it changes cache content
        (different list identity: new list = original append)."""
        highs = [1.0, 2.0, 5.0, 2.0, 1.0, 2.0, 3.0, 3.0, 2.0, 1.0, 8.0, 2.0, 1.0]
        lows = [0.5, 1.0, 0.8, 0.5, 0.2, 0.8, 0.5, 0.8, 0.5, 0.3, 1.5, 0.5, 0.2]
        bars = self._bars(highs, lows)
        before_dt = _new_parse_utc(bars[-1]["time"]) + timedelta(hours=4)
        baseline = htf_bias(bars, before_dt)

        # Extreme future bar that would flip the bias if it leaked in.
        future_bar = {
            "time": (_new_parse_utc(bars[-1]["time"]) + timedelta(hours=4))
                    .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "open": 0.01, "high": 0.01, "low": 0.005, "close": 0.01,
        }
        extended = bars + [future_bar]
        result_with_future = htf_bias(extended, before_dt)

        self.assertEqual(baseline, result_with_future)
        self.assertEqual(baseline, _old_htf_bias(extended, before_dt))


# ─────────────────────────────────────────────────────────────────────────────
# Benchmark — before/after wall-clock on a real multi-year dataset
# ─────────────────────────────────────────────────────────────────────────────

class TestBenchmark(unittest.TestCase):
    """
    Not a correctness test — measures and prints wall-clock speedup on a
    representative real dataset, and asserts a conservative minimum speedup
    to catch a regression back to the O(bars_total) per-call behavior.
    """

    def test_speedup_on_eurusd_h4(self):
        path = os.path.join(_DATA_DIR, "EUR_USD_H4.csv")
        if not os.path.exists(path):
            self.skipTest("EUR_USD_H4.csv not present")

        candles = _load_h4("EUR_USD_H4.csv")
        # Simulate realistic usage: one htf_bias() call per bar, walking forward.
        query_points = [
            _new_parse_utc(c["time"]) + timedelta(hours=4) for c in candles
        ]

        t0 = time.perf_counter()
        for dt in query_points:
            _old_htf_bias(candles, dt)
        old_elapsed = time.perf_counter() - t0

        t1 = time.perf_counter()
        for dt in query_points:
            htf_bias(candles, dt)
        new_elapsed = time.perf_counter() - t1

        speedup = old_elapsed / new_elapsed if new_elapsed > 0 else float("inf")
        print(
            f"\n[TASK-HTF-BIAS-OPTIMIZATION benchmark] "
            f"n_bars={len(candles)} n_calls={len(query_points)} "
            f"old={old_elapsed:.4f}s new={new_elapsed:.4f}s speedup={speedup:.1f}x"
        )

        # Conservative floor — real speedup is much larger; this just guards
        # against a future regression back toward O(bars_total) per call.
        self.assertGreater(speedup, 5.0)


if __name__ == "__main__":
    unittest.main()

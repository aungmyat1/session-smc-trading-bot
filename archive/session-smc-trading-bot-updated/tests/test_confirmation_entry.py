"""
Integration tests for session_smc/confirmation_entry.py.

Strategy: build carefully crafted synthetic session candles where each phase
of the signal chain is satisfied, verify a Signal is returned, then break one
phase at a time and verify None is returned.
"""
import pytest
from session_smc.confirmation_entry import generate_signal_A, DEFAULT_CONFIG

# ── Helpers ──────────────────────────────────────────────────────────────────

def c(o, h, l, cl, t="2024-01-01T07:00:00Z"):
    return {"open": o, "high": h, "low": l, "close": cl, "time": t, "volume": 100}


def flat_candles(price, n, start_hour=7):
    return [c(price, price + 0.0001, price - 0.0001, price,
              f"2024-01-01T{start_hour + i:02d}:00:00Z") for i in range(n)]


def bullish_htf(n=20):
    """4H/1H candles that produce bullish classify_structure with n=1.
    HH: idx 1(2)→idx 3(3); HL: idx 2(0.5)→idx 4(0.7); trailing bar at idx 5
    confirms idx 4 as swing low (needs right neighbor).
    """
    highs = [1.0, 2.0, 1.0, 3.0, 1.0, 4.0]
    lows  = [0.5, 1.5, 0.5, 1.7, 0.7, 1.8]
    base = [c(l, h, l, h) for h, l in zip(highs, lows)]
    filler = flat_candles(2.0, max(0, n - len(base)))
    return base + filler


def bearish_htf(n=20):
    """4H/1H candles that produce bearish classify_structure with n=1.
    LH: peaks 5→4→3 (idx 1,3,5); LL: valleys 1.5→1.0 (idx 2,4).
    """
    highs = [1.0, 5.0, 2.0, 4.0, 1.5, 3.0, 1.0]
    lows  = [0.5, 4.0, 1.5, 3.0, 1.0, 2.0, 0.5]
    base = [c(l, h, l, h) for h, l in zip(highs, lows)]
    filler = flat_candles(1.5, max(0, n - len(base)))
    return base + filler


# ── Synthetic full-signal session ────────────────────────────────────────────

def build_bullish_session():
    """
    Construct session_candles where ALL phases fire for a BULLISH trade.

    Layout (15M bars, indices 0-19, atr_period=5, swing_n=1):
      0-2, 4-7 : range bars: h=1.0915, l=1.0900
      3         : embedded swing high: h=1.0930, l=1.0900
                  → last_swing_high(sess[:8], n=1) = price 1.0930 at idx 3
                  → session_range.high = 1.0930, session_range.low = 1.0900 (30 pips)
                  → CHoCH reference = max(highs[0:8]) = 1.0930
                  → BOS level = 1.0930
      8         : sweep bar: l=1.0895 < s_low=1.0900, close=1.0908 > 1.0900
      9         : CHoCH: close=1.0933 > reference=1.0930 → CHoCH at idx 9
      10        : displacement + BOS: range=0.0045, close=1.0968 > 1.0930
                  ATR[10] ≈ 0.0023, threshold ≈ 0.0035 < 0.0045 ✓
      11        : FVG bar: low=1.0945 > high[9]=1.0936 → gap exists
                  FVG zone: bottom=high[9]=1.0936, top=low[11]=1.0945
      12        : retest: low=1.0938 ≤ top=1.0945 ✓, close=1.0970 ≥ bottom=1.0936 ✓
      13-19     : remaining (bars_remaining = 20-1-12 = 7 ≥ 2)
    """
    sess = []

    # Range bars 0-2 (h=1.0915, l=1.0900)
    for _ in range(3):
        sess.append(c(1.0905, 1.0915, 1.0900, 1.0908))

    # Bar 3: embedded swing high (h=1.0930 > h of adjacent bars=1.0915)
    sess.append(c(1.0905, 1.0930, 1.0900, 1.0925))

    # Range bars 4-7 (h=1.0915, l=1.0900)
    for _ in range(4):
        sess.append(c(1.0905, 1.0915, 1.0900, 1.0908))

    # Bar 8: sweep — wick below s_low=1.0900, close above it
    sess.append(c(1.0905, 1.0910, 1.0895, 1.0908))

    # Bar 9: CHoCH — close=1.0933 > reference=max(highs[0:8])=1.0930
    sess.append(c(1.0905, 1.0936, 1.0910, 1.0933))

    # Bar 10: displacement + BOS
    # range = 1.0970-1.0925 = 0.0045; ATR[10]≈0.0023 → threshold≈0.0035 < 0.0045 ✓
    # close=1.0968 > BOS level=1.0930 → BOS fires at idx 10
    sess.append(c(1.0925, 1.0970, 1.0925, 1.0968))

    # Bar 11: FVG confirming bar
    # FVG bottom = high[9]=1.0936; FVG top = low[11] — must be > 1.0936
    sess.append(c(1.0968, 1.0985, 1.0945, 1.0978))

    # Bar 12: retest — low=1.0938 ≤ top=1.0945 ✓, close=1.0970 ≥ bottom=1.0936 ✓
    sess.append(c(1.0978, 1.0982, 1.0938, 1.0970))

    # Bars 13-19: remaining (bars_remaining = 20-1-12 = 7 ≥ 2)
    for _ in range(7):
        sess.append(c(1.0970, 1.0982, 1.0965, 1.0975))

    return sess


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestGenerateSignalA:
    _cfg = {**DEFAULT_CONFIG, "atr_period": 5, "swing_n": 1}

    def test_full_bullish_signal_fires(self):
        sess = build_bullish_session()
        sig = generate_signal_A(
            symbol="EURUSD",
            candles_4h=bullish_htf(),
            candles_1h=bullish_htf(),
            session_candles=sess,
            session_name="london",
            config=self._cfg,
        )
        assert sig is not None
        assert sig.direction == "long"
        assert sig.setup_type == "A"
        assert sig.session == "london"
        assert sig.sl < sig.entry < sig.tp1 < sig.tp2
        assert sig.sl_pips > 0

    def test_neutral_htf_returns_none(self):
        sess = build_bullish_session()
        sig = generate_signal_A(
            symbol="EURUSD",
            candles_4h=flat_candles(1.0, 20),
            candles_1h=flat_candles(1.0, 20),
            session_candles=sess,
            session_name="london",
            config=self._cfg,
        )
        assert sig is None

    def test_too_few_session_bars_returns_none(self):
        sess = build_bullish_session()[:5]
        sig = generate_signal_A(
            symbol="EURUSD",
            candles_4h=bullish_htf(),
            candles_1h=bullish_htf(),
            session_candles=sess,
            session_name="london",
            config=self._cfg,
        )
        assert sig is None

    def test_no_sweep_returns_none(self):
        # Range bars only — no sweep because prices stay inside range
        sess = [c(1.0910, 1.0920, 1.0900, 1.0915)] * 20
        sig = generate_signal_A(
            symbol="EURUSD",
            candles_4h=bullish_htf(),
            candles_1h=bullish_htf(),
            session_candles=sess,
            session_name="london",
            config=self._cfg,
        )
        assert sig is None

    def test_signal_entry_equals_retest_close(self):
        sess = build_bullish_session()
        sig = generate_signal_A(
            symbol="EURUSD",
            candles_4h=bullish_htf(),
            candles_1h=bullish_htf(),
            session_candles=sess,
            session_name="london",
            config=self._cfg,
        )
        if sig is not None:
            assert sig.entry == pytest.approx(sess[sig.retest_idx]["close"])

    def test_sl_pips_positive_and_consistent(self):
        sess = build_bullish_session()
        sig = generate_signal_A(
            symbol="EURUSD",
            candles_4h=bullish_htf(),
            candles_1h=bullish_htf(),
            session_candles=sess,
            session_name="london",
            config=self._cfg,
        )
        if sig is not None:
            assert sig.sl_pips > 0
            expected_dist = (sig.entry - sig.sl) / 0.0001
            assert sig.sl_pips == pytest.approx(expected_dist, rel=0.01)

    def test_tp1_equals_4r(self):
        sess = build_bullish_session()
        sig = generate_signal_A(
            symbol="EURUSD",
            candles_4h=bullish_htf(),
            candles_1h=bullish_htf(),
            session_candles=sess,
            session_name="london",
            config=self._cfg,
        )
        if sig is not None:
            expected_tp1 = sig.entry + 4.0 * sig.sl_pips * 0.0001
            assert sig.tp1 == pytest.approx(expected_tp1, rel=0.01)

    def test_min_bars_remaining_gate(self):
        # Pass exactly min_bars_remaining - 1 bars after retest → None
        sess = build_bullish_session()
        # retest_idx = 12; keep bars 0..13 (length=14)
        # bars_remaining = 14-1-12 = 1 < min_bars_remaining=2 → None
        short = sess[:14]
        cfg = {**self._cfg, "min_bars_remaining": 2}
        sig = generate_signal_A(
            symbol="EURUSD",
            candles_4h=bullish_htf(),
            candles_1h=bullish_htf(),
            session_candles=short,
            session_name="london",
            config=cfg,
        )
        assert sig is None

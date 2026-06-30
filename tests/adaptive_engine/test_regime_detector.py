"""Tests for bot/engine/regime_detector.py"""

from adaptive.engine.regime_detector import detect_regime, _compute_atr, _compute_adx


def _make_candles(
    n: int, high_offset: float = 0.002, low_offset: float = 0.002
) -> list[dict]:
    """Generate synthetic OHLCV candles centred around 1.1000."""
    base = 1.1000
    candles = []
    for i in range(n):
        close = base + i * 0.0001
        candles.append(
            {
                "open": close - 0.0005,
                "high": close + high_offset,
                "low": close - low_offset,
                "close": close,
                "volume": 1000,
            }
        )
    return candles


def _make_ranging_candles(n: int = 60) -> list[dict]:
    """Oscillating candles — low ADX, normal ATR."""
    import math

    candles = []
    base = 1.1000
    for i in range(n):
        close = base + 0.0005 * math.sin(i * 0.3)
        candles.append(
            {
                "open": close - 0.0003,
                "high": close + 0.0015,
                "low": close - 0.0015,
                "close": close,
                "volume": 1000,
            }
        )
    return candles


class TestDetectRegime:
    def test_returns_unsafe_when_spread_too_high(self):
        candles = _make_candles(60)
        result = detect_regime(candles, spread_pips=5.0)
        assert result["regime"] == "UNSAFE"
        assert result["confidence"] == 1.0

    def test_returns_unsafe_when_insufficient_bars(self):
        candles = _make_candles(5)
        result = detect_regime(candles, spread_pips=0.5)
        assert result["regime"] == "UNSAFE"

    def test_result_has_required_keys(self):
        candles = _make_candles(60)
        result = detect_regime(candles, spread_pips=0.5)
        for key in (
            "regime",
            "confidence",
            "adx",
            "plus_di",
            "minus_di",
            "atr_pct",
            "atr_expanding",
        ):
            assert key in result, f"Missing key: {key}"

    def test_regime_is_valid_value(self):
        candles = _make_candles(60)
        result = detect_regime(candles, spread_pips=0.5)
        assert result["regime"] in {"TRENDING", "BREAKOUT", "RANGING", "UNSAFE"}

    def test_confidence_in_range(self):
        candles = _make_candles(60)
        result = detect_regime(candles, spread_pips=0.5)
        assert 0.0 <= result["confidence"] <= 1.0

    def test_ranging_candles_classify_as_ranging_or_unsafe(self):
        candles = _make_ranging_candles(60)
        result = detect_regime(candles, spread_pips=0.5)
        assert result["regime"] in {"RANGING", "UNSAFE"}

    def test_trending_candles_not_ranging(self):
        # Strong directional move
        candles = []
        for i in range(60):
            close = 1.1 + i * 0.0005
            candles.append(
                {
                    "open": close - 0.0002,
                    "high": close + 0.0003,
                    "low": close - 0.0003,
                    "close": close,
                    "volume": 1000,
                }
            )
        result = detect_regime(candles, spread_pips=0.5)
        assert result["regime"] in {"TRENDING", "BREAKOUT", "UNSAFE"}

    def test_adx_non_negative(self):
        candles = _make_candles(60)
        result = detect_regime(candles)
        assert result["adx"] >= 0


class TestComputeATR:
    def test_returns_empty_for_insufficient_data(self):
        candles = _make_candles(5)
        assert _compute_atr(candles, period=14) == []

    def test_returns_list_for_sufficient_data(self):
        candles = _make_candles(30)
        result = _compute_atr(candles, period=14)
        assert len(result) > 0

    def test_atr_values_positive(self):
        candles = _make_candles(30)
        result = _compute_atr(candles, period=14)
        assert all(v > 0 for v in result)


class TestComputeADX:
    def test_returns_zeros_for_insufficient_data(self):
        candles = _make_candles(5)
        adx, pdi, mdi = _compute_adx(candles, period=14)
        assert adx == 0.0
        assert pdi == 0.0
        assert mdi == 0.0

    def test_returns_non_negative_for_sufficient_data(self):
        candles = _make_candles(60)
        adx, pdi, mdi = _compute_adx(candles, period=14)
        assert adx >= 0
        assert pdi >= 0
        assert mdi >= 0

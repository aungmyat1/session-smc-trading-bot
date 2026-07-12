"""
Unit tests for strategies/st_b1_simple_pullback.py — all synthetic,
deterministic OHLC fixtures. No external data, no network, no real market
data required (consistent with the "computationally lightweight, easy to
audit" design goal in config/strategies/ST-B1_v1.yaml).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from strategies.st_b1_simple_pullback import (
    PullbackSetup,
    calculate_position_size,
    compute_stop_and_target,
    compute_trend,
    detect_pullback,
    ema,
    generate_orders,
    validate_entry,
)

_UTC = timezone.utc


def _candle(ts, o, hi, lo, c, session=""):
    return {"timestamp": ts, "open": o, "high": hi, "low": lo, "close": c, "session": session}


def _h1_series(n, *, start=1.1000, step=0.0002, base_time=None):
    """n candles trending upward by `step` each bar."""
    base_time = base_time or datetime(2026, 1, 1, tzinfo=_UTC)
    out = []
    price = start
    for i in range(n):
        ts = base_time + timedelta(hours=i)
        out.append(_candle(ts, price, price + 0.0003, price - 0.0003, price + step))
        price += step
    return out


class TestEma:
    def test_insufficient_history_returns_none_prefix(self):
        result = ema([1.0, 2.0, 3.0], period=5)
        assert result == [None, None, None]

    def test_seed_is_simple_mean(self):
        values = [1.0, 2.0, 3.0, 4.0]
        result = ema(values, period=4)
        assert result[3] == pytest.approx(2.5)

    def test_constant_series_ema_equals_the_constant(self):
        values = [5.0] * 10
        result = ema(values, period=5)
        assert result[-1] == pytest.approx(5.0)

    def test_recursive_values_move_toward_new_price(self):
        values = [1.0] * 5 + [2.0] * 5
        result = ema(values, period=5)
        assert result[5] > result[4]  # trending toward 2.0
        assert result[-1] < 2.0        # hasn't fully caught up yet
        assert result[-1] > 1.0


class TestComputeTrend:
    def test_insufficient_history_is_neutral(self):
        candles = _h1_series(50)
        assert compute_trend(candles, symbol="EURUSD") == "neutral"

    def test_strong_uptrend_is_bullish(self):
        candles = _h1_series(250, start=1.1000, step=0.0005)
        assert compute_trend(candles, symbol="EURUSD") == "bullish"

    def test_strong_downtrend_is_bearish(self):
        candles = _h1_series(250, start=1.1000, step=-0.0005)
        assert compute_trend(candles, symbol="EURUSD") == "bearish"

    def test_flat_price_near_ema_is_neutral(self):
        candles = _h1_series(250, start=1.1000, step=0.0)
        assert compute_trend(candles, symbol="EURUSD") == "neutral"

    def test_neutral_threshold_is_configurable(self):
        candles = _h1_series(250, start=1.1000, step=0.00001)
        # With a very large threshold, even a real (tiny) trend reads neutral.
        assert compute_trend(candles, symbol="EURUSD", neutral_threshold_pips=1000.0) == "neutral"


class TestDetectPullback:
    def _bullish_pullback_series(self):
        # Build a long, gentle uptrend so EMA20 sits below recent price,
        # then a sharp one-candle dip that tags EMA20 and closes back above
        # the prior candle's high.
        candles = _h1_series(25, start=1.1000, step=0.0004)
        prior = candles[-1]
        ema20 = ema([c["close"] for c in candles], 20)[-1]
        rejection = _candle(
            prior["timestamp"] + timedelta(minutes=15),
            o=prior["close"], hi=prior["close"] + 0.0002,
            lo=ema20 - 0.0001,                      # tags/dips below EMA20
            c=prior["high"] + 0.0001,               # closes above prior high
        )
        return candles + [rejection]

    def _bearish_pullback_series(self):
        candles = _h1_series(25, start=1.1000, step=-0.0004)
        prior = candles[-1]
        ema20 = ema([c["close"] for c in candles], 20)[-1]
        rejection = _candle(
            prior["timestamp"] + timedelta(minutes=15),
            o=prior["close"], hi=ema20 + 0.0001,     # pokes above EMA20
            lo=prior["close"] - 0.0002,
            c=prior["low"] - 0.0001,                # closes below prior low
        )
        return candles + [rejection]

    def test_long_setup_detected_in_bullish_trend(self):
        setup = detect_pullback(self._bullish_pullback_series(), "bullish")
        assert setup is not None
        assert setup.direction == "long"

    def test_short_setup_detected_in_bearish_trend(self):
        setup = detect_pullback(self._bearish_pullback_series(), "bearish")
        assert setup is not None
        assert setup.direction == "short"

    def test_no_setup_when_trend_is_neutral(self):
        assert detect_pullback(self._bullish_pullback_series(), "neutral") is None

    def test_no_setup_without_rejection_close(self):
        candles = _h1_series(25, start=1.1000, step=0.0004)
        prior = candles[-1]
        ema20 = ema([c["close"] for c in candles], 20)[-1]
        # Tags EMA20 but closes BELOW the prior high — no rejection confirmation.
        weak = _candle(
            prior["timestamp"] + timedelta(minutes=15),
            o=prior["close"], hi=prior["close"], lo=ema20 - 0.0001, c=prior["close"] - 0.0001,
        )
        assert detect_pullback(candles + [weak], "bullish") is None

    def test_no_setup_without_retrace_to_ema(self):
        candles = _h1_series(25, start=1.1000, step=0.0004)
        prior = candles[-1]
        # Closes above prior high (rejection-shaped) but never dips near EMA20.
        far = _candle(
            prior["timestamp"] + timedelta(minutes=15),
            o=prior["close"], hi=prior["close"] + 0.0005,
            lo=prior["close"] - 0.00005, c=prior["high"] + 0.0001,
        )
        assert detect_pullback(candles + [far], "bullish") is None

    def test_insufficient_history_returns_none(self):
        assert detect_pullback(_h1_series(5), "bullish") is None


class TestValidateEntry:
    def _setup(self, direction="long"):
        return PullbackSetup(
            direction=direction,
            rejection_candle=_candle(datetime(2026, 1, 1, tzinfo=_UTC), 1.1, 1.1005, 1.0995, 1.1002),
            prior_candle=_candle(datetime(2026, 1, 1, tzinfo=_UTC) - timedelta(minutes=15), 1.1, 1.1003, 1.0997, 1.1001),
            swing_low=1.0995,
            swing_high=1.1005,
            ema20_at_rejection=1.0999,
        )

    def test_valid_long_entry(self):
        next_candle = _candle(None, 1.1003, 1.1010, 1.1001, 1.1006)
        assert validate_entry(self._setup("long"), next_candle) is True

    def test_valid_short_entry(self):
        next_candle = _candle(None, 1.1003, 1.1005, 1.0998, 1.1000)
        assert validate_entry(self._setup("short"), next_candle) is True

    def test_none_setup_rejected(self):
        assert validate_entry(None, _candle(None, 1.1, 1.1, 1.1, 1.1)) is False

    def test_none_next_candle_rejected(self):
        assert validate_entry(self._setup("long"), None) is False

    def test_long_entry_already_through_stop_rejected(self):
        # Open has already gapped below the swing low — stop already violated.
        next_candle = _candle(None, 1.0990, 1.0995, 1.0985, 1.0992)
        assert validate_entry(self._setup("long"), next_candle) is False

    def test_short_entry_already_through_stop_rejected(self):
        next_candle = _candle(None, 1.1010, 1.1015, 1.1005, 1.1012)
        assert validate_entry(self._setup("short"), next_candle) is False


class TestComputeStopAndTarget:
    def _setup(self, direction, swing_low, swing_high):
        return PullbackSetup(
            direction=direction,
            rejection_candle={}, prior_candle={},
            swing_low=swing_low, swing_high=swing_high,
            ema20_at_rejection=0.0,
        )

    def test_long_uses_swing_low_when_wider_than_minimum(self):
        setup = self._setup("long", swing_low=1.0980, swing_high=1.1000)
        sl, tp = compute_stop_and_target(setup, entry_price=1.1000, symbol="EURUSD")
        assert sl == pytest.approx(1.0980)
        distance = 1.1000 - 1.0980
        assert tp == pytest.approx(1.1000 + distance * 2.0)

    def test_long_enforces_minimum_stop_when_swing_too_tight(self):
        # Swing distance is only 2 pips; EURUSD minimum is 8 pips.
        setup = self._setup("long", swing_low=1.09998, swing_high=1.1000)
        sl, tp = compute_stop_and_target(setup, entry_price=1.1000, symbol="EURUSD")
        expected_distance = 8.0 * 0.0001
        assert sl == pytest.approx(1.1000 - expected_distance)
        assert tp == pytest.approx(1.1000 + expected_distance * 2.0)

    def test_short_enforces_minimum_stop_gbpusd(self):
        setup = self._setup("short", swing_low=1.2700, swing_high=1.27005)
        sl, tp = compute_stop_and_target(setup, entry_price=1.2700, symbol="GBPUSD")
        expected_distance = 10.0 * 0.0001
        assert sl == pytest.approx(1.2700 + expected_distance)
        assert tp == pytest.approx(1.2700 - expected_distance * 2.0)

    def test_xauusd_uses_atr_based_minimum(self):
        setup = self._setup("long", swing_low=1999.5, swing_high=2000.0)
        # 15 flat-ish H1 candles -> ATR should be small and positive.
        candles = [
            _candle(datetime(2026, 1, 1, tzinfo=_UTC) + timedelta(hours=i),
                    2000.0, 2001.0, 1999.0, 2000.0 + (0.1 if i % 2 else -0.1))
            for i in range(20)
        ]
        sl, tp = compute_stop_and_target(
            setup, entry_price=2000.0, symbol="XAUUSD",
            entry_tf_candles=candles, xauusd_broker_minimum=0.5,
        )
        assert sl < 2000.0
        assert tp > 2000.0
        assert (2000.0 - sl) == pytest.approx((tp - 2000.0) / 2.0)

    def test_xauusd_falls_back_to_broker_minimum_without_atr_history(self):
        setup = self._setup("long", swing_low=1999.9, swing_high=2000.0)
        sl, _ = compute_stop_and_target(
            setup, entry_price=2000.0, symbol="XAUUSD",
            entry_tf_candles=[], xauusd_broker_minimum=1.0,
        )
        assert sl == pytest.approx(2000.0 - 1.0)


class TestCalculatePositionSize:
    def test_normal_calculation(self):
        lots = calculate_position_size(10000.0, 0.25, 0.0010, pip_value_per_lot=10.0, pip_size=0.0001)
        # risk_amount = 25, stop_distance_pips = 10, lots = 25 / (10*10) = 0.25
        assert lots == pytest.approx(0.25)

    def test_risk_pct_clamped_to_max(self):
        uncapped = calculate_position_size(10000.0, 5.0, 0.0010, max_risk_pct=0.50)
        capped = calculate_position_size(10000.0, 0.50, 0.0010, max_risk_pct=0.50)
        assert uncapped == capped

    def test_zero_equity_returns_zero(self):
        assert calculate_position_size(0.0, 0.25, 0.0010) == 0.0

    def test_zero_stop_distance_returns_zero(self):
        assert calculate_position_size(10000.0, 0.25, 0.0) == 0.0

    def test_negative_stop_distance_returns_zero(self):
        assert calculate_position_size(10000.0, 0.25, -0.001) == 0.0


class TestGenerateOrders:
    def _long_setup(self):
        return PullbackSetup(
            direction="long",
            rejection_candle={}, prior_candle={},
            swing_low=1.0980, swing_high=1.1000,
            ema20_at_rejection=1.0995,
        )

    def _next_candle(self):
        return _candle(datetime(2026, 1, 1, 1, 0, tzinfo=_UTC), 1.1002, 1.1010, 1.1000, 1.1006, session="london")

    def test_happy_path_produces_buy_signal(self):
        signal = generate_orders(
            symbol="EURUSD", trend="bullish", setup=self._long_setup(),
            next_candle=self._next_candle(), equity=10000.0, risk_pct=0.25,
        )
        assert signal is not None
        assert signal.action == "BUY"
        assert signal.symbol == "EURUSD"
        assert signal.strategy_name == "ST-B1"
        assert signal.stop_loss < signal.entry_price < signal.take_profit
        assert signal.metadata["lots"] > 0

    def test_no_setup_returns_none(self):
        assert generate_orders(
            symbol="EURUSD", trend="bullish", setup=None,
            next_candle=self._next_candle(), equity=10000.0,
        ) is None

    def test_existing_open_position_blocks_new_signal(self):
        assert generate_orders(
            symbol="EURUSD", trend="bullish", setup=self._long_setup(),
            next_candle=self._next_candle(), equity=10000.0,
            open_position_count=1,
        ) is None

    def test_invalid_entry_blocks_signal(self):
        gapped = _candle(datetime(2026, 1, 1, 1, 0, tzinfo=_UTC), 1.0970, 1.0975, 1.0965, 1.0972)
        assert generate_orders(
            symbol="EURUSD", trend="bullish", setup=self._long_setup(),
            next_candle=gapped, equity=10000.0,
        ) is None

    def test_short_signal_has_sell_action_and_correct_ordering(self):
        short_setup = PullbackSetup(
            direction="short", rejection_candle={}, prior_candle={},
            swing_low=1.2695, swing_high=1.2705, ema20_at_rejection=1.2700,
        )
        next_candle = _candle(datetime(2026, 1, 1, 1, 0, tzinfo=_UTC), 1.2698, 1.2699, 1.2690, 1.2692, session="new_york")
        signal = generate_orders(
            symbol="GBPUSD", trend="bearish", setup=short_setup,
            next_candle=next_candle, equity=10000.0, risk_pct=0.25,
        )
        assert signal is not None
        assert signal.action == "SELL"
        assert signal.take_profit < signal.entry_price < signal.stop_loss

"""Tests for bot/engine/signal_scorer.py"""

from adaptive.engine.signal_scorer import MIN_SCORE, score_signal
from adaptive.strategies import AdaptiveSignal


def _make_signal(
    strategy: str = "smc_session",
    pair: str = "EURUSD",
    direction: str = "LONG",
    session: str = "london",
    liquidity_swept: bool = True,
    structure_confirmed: bool = True,
) -> AdaptiveSignal:
    return AdaptiveSignal(
        strategy=strategy,
        pair=pair,
        direction=direction,
        entry_price=1.1000,
        sl_price=1.0950,
        tp_price=1.1150,
        session=session,
        timestamp="2026-06-24T07:30:00+00:00",
        reason="test signal",
        metadata={
            "liquidity_swept": liquidity_swept,
            "structure_confirmed": structure_confirmed,
        },
    )


def _full_context(
    direction: str = "LONG",
    htf_bias: str = "BULLISH",
    utc_hour: int = 7,
    spread_pips: float = 1.0,
    atr_pct: float = 0.003,
    news_event: bool = False,
) -> dict:
    return {
        "htf_bias": htf_bias,
        "utc_hour": utc_hour,
        "spread_pips": spread_pips,
        "atr_pct": atr_pct,
        "news_event": news_event,
    }


class TestScoreSignal:
    def test_max_score_all_criteria_met(self):
        sig = _make_signal(direction="LONG", session="london")
        ctx = _full_context(direction="LONG", htf_bias="BULLISH", utc_hour=7)
        result = score_signal(sig, ctx)
        assert result["score"] == 10

    def test_approved_when_score_gte_min(self):
        sig = _make_signal(direction="LONG", session="london")
        ctx = _full_context()
        result = score_signal(sig, ctx)
        assert result["approved"] is True

    def test_rejected_when_score_below_min(self):
        # No HTF bias alignment, no liquidity, no structure, wrong session
        sig = _make_signal(
            direction="LONG",
            session="asian",
            liquidity_swept=False,
            structure_confirmed=False,
        )
        ctx = {
            "htf_bias": "BEARISH",
            "utc_hour": 3,  # asian session — not in active windows
            "spread_pips": 5.0,  # too wide
            "atr_pct": 0.0001,  # too low
            "news_event": True,
        }
        result = score_signal(sig, ctx)
        assert result["score"] < MIN_SCORE
        assert result["approved"] is False

    def test_breakdown_keys_present(self):
        sig = _make_signal()
        ctx = _full_context()
        result = score_signal(sig, ctx)
        expected = {
            "htf_bias_aligned",
            "liquidity_event",
            "structure_confirmation",
            "active_session",
            "spread_acceptable",
            "volatility_acceptable",
            "news_clear",
        }
        assert set(result["breakdown"].keys()) == expected

    def test_bearish_bias_short_signal_aligned(self):
        sig = _make_signal(direction="SHORT", session="new_york")
        ctx = _full_context(direction="SHORT", htf_bias="BEARISH", utc_hour=13)
        result = score_signal(sig, ctx)
        assert result["breakdown"]["htf_bias_aligned"] == 2

    def test_neutral_bias_not_aligned(self):
        sig = _make_signal(direction="LONG")
        ctx = _full_context(htf_bias="NEUTRAL")
        result = score_signal(sig, ctx)
        assert result["breakdown"]["htf_bias_aligned"] == 0

    def test_spread_too_wide_penalised(self):
        sig = _make_signal()
        ctx = _full_context(spread_pips=3.0)
        result = score_signal(sig, ctx)
        assert result["breakdown"]["spread_acceptable"] == 0

    def test_news_event_penalised(self):
        sig = _make_signal()
        ctx = _full_context(news_event=True)
        result = score_signal(sig, ctx)
        assert result["breakdown"]["news_clear"] == 0

    def test_score_non_negative(self):
        sig = _make_signal(liquidity_swept=False, structure_confirmed=False)
        ctx = {
            "htf_bias": "NEUTRAL",
            "utc_hour": 3,
            "spread_pips": 10.0,
            "atr_pct": 0.0,
            "news_event": True,
        }
        result = score_signal(sig, ctx)
        assert result["score"] >= 0

    def test_no_liquidity_loses_2_points(self):
        sig_with = _make_signal(liquidity_swept=True)
        sig_without = _make_signal(liquidity_swept=False)
        ctx = _full_context()
        r1 = score_signal(sig_with, ctx)
        r2 = score_signal(sig_without, ctx)
        assert r1["score"] - r2["score"] == 2

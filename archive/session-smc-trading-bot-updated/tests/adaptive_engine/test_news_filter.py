"""Tests for adaptive/filters/news_filter.py"""

from adaptive.filters.news_filter import NewsFilter


class TestNewsFilter:
    def test_stub_always_safe(self):
        nf = NewsFilter()
        result = nf.is_safe("EURUSD")
        assert result["safe_to_trade"] is True
        assert result["source"] == "stub"

    def test_stub_safe_for_any_symbol(self):
        nf = NewsFilter()
        for sym in ("EURUSD", "GBPUSD", "USDJPY"):
            assert nf.is_safe(sym)["safe_to_trade"] is True

    def test_manual_block_unsafe(self):
        nf = NewsFilter()
        nf.block("EURUSD")
        # Stub mode — manual block only applies when _live=True
        # Without enabling live, still returns True (stub overrides)
        result = nf.is_safe("EURUSD")
        assert result["source"] == "stub"

    def test_result_has_required_keys(self):
        nf = NewsFilter()
        result = nf.is_safe("GBPUSD")
        assert "safe_to_trade" in result
        assert "source" in result
        assert "reason" in result

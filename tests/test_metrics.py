"""Tests for monitoring/metrics.py"""

import json

import pytest

from monitoring.metrics import TradeJournal


@pytest.fixture
def journal(tmp_path) -> TradeJournal:
    return TradeJournal(path=tmp_path / "trades.jsonl")


def _log(journal, symbol="EURUSD", direction="long", result_r=None, **kwargs):
    journal.log_trade(
        symbol=symbol,
        direction=direction,
        entry=1.08000,
        sl=1.07500,
        tp=1.09000,
        risk_pct=0.5,
        lot=0.10,
        result_r=result_r,
        **kwargs,
    )


class TestTradeJournal:
    def test_log_creates_file(self, journal):
        _log(journal)
        assert journal._path.exists()

    def test_each_log_appends_a_line(self, journal):
        _log(journal)
        _log(journal)
        lines = journal._path.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_logged_fields(self, journal):
        _log(journal, symbol="GBPUSD", direction="short", result_r=2.5)
        record = json.loads(journal._path.read_text().strip())
        assert record["symbol"] == "GBPUSD"
        assert record["direction"] == "short"
        assert record["result_r"] == 2.5

    def test_get_all_trades(self, journal):
        _log(journal, result_r=1.0)
        _log(journal, result_r=-0.5)
        trades = journal.get_all_trades()
        assert len(trades) == 2

    def test_empty_stats_when_no_trades(self, journal):
        stats = journal.get_all_stats()
        assert stats["trades"] == 0
        assert stats["win_rate"] == 0.0

    def test_stats_win_rate(self, journal):
        _log(journal, result_r=2.0)
        _log(journal, result_r=1.5)
        _log(journal, result_r=-1.0)
        stats = journal.get_all_stats()
        assert stats["trades"] == 3
        assert stats["wins"] == 2
        assert stats["losses"] == 1
        assert stats["win_rate"] == pytest.approx(66.7, rel=0.01)

    def test_stats_total_r(self, journal):
        _log(journal, result_r=3.0)
        _log(journal, result_r=-1.0)
        stats = journal.get_all_stats()
        assert stats["total_r"] == pytest.approx(2.0)

    def test_open_trades_excluded_from_stats(self, journal):
        _log(journal, result_r=None)  # open trade — no result yet
        _log(journal, result_r=2.0)
        stats = journal.get_all_stats()
        assert stats["trades"] == 1  # only the closed one counts

    def test_daily_stats_filters_by_date(self, journal, monkeypatch):

        # Inject a fixed "today" for get_daily_stats
        monkeypatch.setattr(
            "monitoring.metrics.datetime",
            type(
                "FakeDT",
                (),
                {
                    "now": staticmethod(
                        lambda tz=None: __import__("datetime").datetime(
                            2026, 6, 19, 12, 0, tzinfo=tz
                        )
                    ),
                    "strptime": __import__("datetime").datetime.strptime,
                },
            ),
        )
        journal.log_trade("EURUSD", "long", 1.08, 1.07, 1.09, 0.5, 0.1, result_r=1.0)

        stats = journal.get_daily_stats("2026-06-19")
        assert stats["trades"] >= 1

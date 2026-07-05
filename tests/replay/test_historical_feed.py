from datetime import datetime, timezone

import pandas as pd
import pytest

from replay.historical_feed import HistoricalFeed


def test_feed_rejects_missing_schema_fields(tmp_path) -> None:
    path = tmp_path / "bad.csv"
    pd.DataFrame([{"symbol": "EURUSD", "timestamp": "2024-01-01T00:00:00Z"}]).to_csv(path, index=False)
    with pytest.raises(ValueError, match="missing required fields"):
        HistoricalFeed(path)


def test_feed_returns_timestamp_order_and_queries(sample_candles) -> None:
    feed = HistoricalFeed(sample_candles)
    first = feed.get_next_bar()
    second = feed.get_next_bar()
    assert first is not None and second is not None
    assert first.timestamp < second.timestamp
    assert feed.get_bar_at(datetime(2024, 1, 1, 0, 1, tzinfo=timezone.utc)) == second
    assert list(feed.stream_between(first.timestamp, second.timestamp)) == [first, second]


def test_feed_reads_parquet_in_timestamp_order(sample_candles, tmp_path) -> None:
    parquet_path = tmp_path / "candles.parquet"
    pd.read_csv(sample_candles).to_parquet(parquet_path, index=False)

    feed = HistoricalFeed(parquet_path)

    assert [bar.timestamp for bar in feed.bars] == sorted(bar.timestamp for bar in feed.bars)
    assert len(feed.bars) == 2

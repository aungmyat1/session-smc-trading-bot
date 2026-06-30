from __future__ import annotations

import pandas as pd

from src.analytics.duckdb_store import DuckDBStore
from src.analytics.queries import ResearchQueries


def test_duckdb_queries(tmp_path):
    store = DuckDBStore(tmp_path / "research.db")
    candles = pd.DataFrame(
        {"timestamp": pd.to_datetime(["2024-01-01T00:00:00Z"], utc=True)}
    )
    sessions = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2024-01-01T00:00:00Z"], utc=True),
            "session": ["asian"],
        }
    )
    signals = pd.DataFrame(
        {
            "signal_id": ["sig-1"],
            "timestamp": pd.to_datetime(["2024-01-01T00:00:00Z"], utc=True),
            "pair": ["EURUSD"],
            "session": ["asian"],
            "direction": ["LONG"],
            "strategy_name": ["ST-A2"],
            "sweep": [True],
            "bos": [False],
            "choch": [False],
            "fvg": [False],
            "order_block": [False],
            "entry_price": [1.1],
        }
    )
    trades = pd.DataFrame(
        {
            "trade_id": ["tr-1"],
            "signal_id": ["sig-1"],
            "pair": ["EURUSD"],
            "strategy_name": ["ST-A2"],
            "entry_time": pd.to_datetime(["2024-01-01T00:01:00Z"], utc=True),
            "exit_time": pd.to_datetime(["2024-01-01T00:05:00Z"], utc=True),
            "entry_price": [1.1],
            "exit_price": [1.12],
            "stop_loss": [1.08],
            "take_profit": [1.14],
            "result_r": [1.0],
            "result_money": [50.0],
        }
    )
    store.create_tables(
        {
            "candles": candles,
            "sessions": sessions,
            "signals": signals,
            "trades": trades,
        }
    )
    queries = ResearchQueries(store)
    assert not queries.performance_by_pair().empty
    assert not queries.performance_by_strategy().empty
    assert not queries.performance_by_session().empty
    assert not queries.win_loss_distribution().empty

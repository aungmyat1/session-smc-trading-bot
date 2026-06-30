from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .duckdb_store import DuckDBStore


@dataclass
class ResearchQueries:
    store: DuckDBStore

    def performance_by_pair(self) -> pd.DataFrame:
        return self.store.query("""
            SELECT pair,
                   COUNT(*) AS n_trades,
                   AVG(result_r) AS avg_r,
                   SUM(CASE WHEN result_r > 0 THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS win_rate
            FROM trades
            GROUP BY pair
            ORDER BY n_trades DESC
            """)

    def performance_by_strategy(self) -> pd.DataFrame:
        return self.store.query("""
            SELECT COALESCE(strategy_name, 'unknown') AS strategy_name,
                   COUNT(*) AS n_trades,
                   AVG(result_r) AS avg_r,
                   SUM(CASE WHEN result_r > 0 THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS win_rate
            FROM trades
            GROUP BY 1
            ORDER BY n_trades DESC
            """)

    def performance_by_session(self) -> pd.DataFrame:
        return self.store.query("""
            SELECT s.session,
                   COUNT(*) AS n_signals,
                   AVG(t.result_r) AS avg_r
            FROM signals s
            JOIN trades t USING(signal_id)
            GROUP BY s.session
            ORDER BY n_signals DESC
            """)

    def performance_by_setup(self) -> pd.DataFrame:
        return self.store.query("""
            SELECT CASE
                     WHEN sweep THEN 'sweep'
                     WHEN bos THEN 'bos'
                     WHEN choch THEN 'choch'
                     WHEN fvg THEN 'fvg'
                     WHEN order_block THEN 'order_block'
                     ELSE 'other'
                   END AS setup,
                   COUNT(*) AS n_signals
            FROM signals
            GROUP BY 1
            ORDER BY n_signals DESC
            """)

    def monthly_performance(self) -> pd.DataFrame:
        return self.store.query("""
            SELECT DATE_TRUNC('month', entry_time) AS month,
                   COUNT(*) AS n_trades,
                   AVG(result_r) AS avg_r
            FROM trades
            GROUP BY 1
            ORDER BY 1
            """)

    def drawdown_analysis(self) -> pd.DataFrame:
        return self.store.query("""
            WITH eq AS (
              SELECT entry_time,
                     SUM(result_money) OVER (ORDER BY entry_time) AS equity
              FROM trades
            ),
            dd AS (
              SELECT entry_time,
                     equity,
                     MAX(equity) OVER (ORDER BY entry_time) AS peak
              FROM eq
            )
            SELECT entry_time,
                   equity,
                   peak,
                   (equity - peak) / NULLIF(peak, 0) AS drawdown
            FROM dd
            ORDER BY entry_time
            """)

    def win_loss_distribution(self) -> pd.DataFrame:
        return self.store.query("""
            SELECT CASE WHEN result_r > 0 THEN 'win' ELSE 'loss' END AS outcome,
                   COUNT(*) AS n_trades,
                   AVG(result_r) AS avg_r
            FROM trades
            GROUP BY 1
            ORDER BY 1
            """)

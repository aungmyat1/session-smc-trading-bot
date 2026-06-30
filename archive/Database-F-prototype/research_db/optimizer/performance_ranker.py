"""
performance_ranker.py
Ranks strategies by multiple metrics.
"""

import polars as pl
from pathlib import Path


def rank_strategies(trades_df: pl.DataFrame) -> pl.DataFrame:
    """Rank all strategies by Edge Score + stability."""
    grouped = trades_df.group_by("strategy_id").agg(
        [
            pl.count().alias("trades"),
            pl.col("result_r").mean().alias("avg_r"),
            pl.col("result_r").sum().alias("total_r"),
            ((pl.col("result_r") > 0).mean() * 100).alias("win_rate"),
        ]
    )

    # Calculate Edge Score (simplified)
    grouped = grouped.with_columns(
        (
            pl.col("win_rate") / 100 * pl.col("avg_r") / (pl.col("trades").log() + 1)
        ).alias("edge_score")
    )

    return grouped.sort("edge_score", descending=True)

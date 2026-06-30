"""
elimination_engine.py
Professional strategy pruning system.
"""

import polars as pl


def eliminate_bad_strategies(ranking_df: pl.DataFrame) -> pl.DataFrame:
    """
    Remove weak strategies using strict professional filters.
    """
    return ranking_df.filter(
        (pl.col("avg_r") > 0.1) & (pl.col("trades") >= 300) & (pl.col("win_rate") >= 48)
    ).sort("edge_score", descending=True)

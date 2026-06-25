"""
pattern_miner.py
Discovers statistical patterns in winning vs losing trades.
"""

import polars as pl
from pathlib import Path

TRADES_PATH = Path("research_db/trades/trades.parquet")


def load_trades() -> pl.DataFrame:
    if not TRADES_PATH.exists():
        raise FileNotFoundError("trades.parquet not found. Run Stage 4 first.")
    return pl.read_parquet(TRADES_PATH)


def create_winner_loser_pools(df: pl.DataFrame):
    """Split trades into winner and loser pools."""
    winners = df.filter(pl.col("result_r") > 0)
    losers = df.filter(pl.col("result_r") <= 0)

    winners.write_parquet("research_db/distillation/winner_pool.parquet")
    losers.write_parquet("research_db/distillation/loser_pool.parquet")

    print(f"Winners: {len(winners):,} | Losers: {len(losers):,}")
    return winners, losers


def mine_patterns(df: pl.DataFrame) -> pl.DataFrame:
    """Compute win rate, loss rate and expectancy per feature combination."""
    patterns = (
        df.group_by(["sweep", "has_ob", "has_fvg", "session", "direction"])
        .agg([
            pl.count().alias("trades"),
            pl.col("result_r").mean().alias("avg_r"),
            ((pl.col("result_r") > 0).mean() * 100).alias("win_rate"),
            ((pl.col("result_r") <= 0).mean() * 100).alias("loss_rate"),
        ])
        .with_columns(
            (pl.col("avg_r") * (pl.col("win_rate") / 100)).alias("expectancy")
        )
        .sort("expectancy", descending=True)
    )
    return patterns
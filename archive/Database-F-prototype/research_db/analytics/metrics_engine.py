"""
metrics_engine.py
Core reusable analytics functions for the trading system.
"""

from pathlib import Path
import polars as pl

TRADES_PATH = Path("research_db/trades/trades.parquet")


def load_trades() -> pl.DataFrame:
    """Load the trade database."""
    if not TRADES_PATH.exists():
        raise FileNotFoundError("trades.parquet not found. Run Stage 4 first.")
    return pl.read_parquet(TRADES_PATH)


def session_stats(df: pl.DataFrame) -> pl.DataFrame:
    """Session performance breakdown."""
    return (
        df.group_by("session")
        .agg([
            pl.count().alias("trades"),
            pl.col("result_r").mean().alias("avg_r"),
            pl.col("result_r").sum().alias("total_r"),
            ((pl.col("result_r") > 0).mean() * 100).alias("win_rate"),
        ])
        .sort("avg_r", descending=True)
    )


def pair_stats(df: pl.DataFrame) -> pl.DataFrame:
    """Pair performance breakdown."""
    return (
        df.group_by("pair")
        .agg([
            pl.count().alias("trades"),
            pl.col("result_r").mean().alias("avg_r"),
            pl.col("result_r").sum().alias("total_r"),
            ((pl.col("result_r") > 0).mean() * 100).alias("win_rate"),
        ])
        .sort("avg_r", descending=True)
    )


def setup_stats(df: pl.DataFrame) -> pl.DataFrame:
    """Setup fingerprint analysis (most important edge detector)."""
    return (
        df.group_by(["sweep", "has_ob", "has_fvg", "direction"])
        .agg([
            pl.count().alias("trades"),
            pl.col("result_r").mean().alias("avg_r"),
            pl.col("result_r").sum().alias("total_r"),
            ((pl.col("result_r") > 0).mean() * 100).alias("win_rate"),
        ])
        .sort("avg_r", descending=True)
    )


def win_rate(df: pl.DataFrame) -> float:
    """Overall win rate."""
    return (df["result_r"] > 0).mean() * 100


def calculate_drawdown(df: pl.DataFrame) -> float:
    """Maximum drawdown in R-multiples (equity curve)."""
    equity = 0.0
    peak = 0.0
    max_dd = 0.0

    for r in df["result_r"].to_list():
        equity += r
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd

    return max_dd


def edge_score(df: pl.DataFrame) -> float:
    """
    Professional Edge Score:
    Edge = (Win Rate × Avg R) / Max Drawdown
    """
    wr = win_rate(df) / 100
    avg_r = df["result_r"].mean()
    dd = calculate_drawdown(df)

    if dd == 0:
        return 0.0
    return (wr * avg_r) / dd
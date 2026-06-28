"""
regime_detector.py
Classifies each trade into market regime.
"""

import polars as pl


def detect_regime(df: pl.DataFrame) -> pl.DataFrame:
    """
    Simple regime classification based on R variance and direction consistency.
    """
    # Calculate rolling volatility proxy (std of result_r over last 50 trades)
    df = df.with_columns(
        pl.col("result_r").rolling_std(window_size=50).alias("r_volatility")
    )

    df = df.with_columns(
        pl.when(pl.col("r_volatility") > 2.0).then(pl.lit("high_volatility"))
        .when(pl.col("direction").is_in(["LONG", "SHORT"]))
        .then(pl.lit("trending"))
        .otherwise(pl.lit("ranging"))
        .alias("regime")
    )

    return df.select(["signal_id", "regime"])
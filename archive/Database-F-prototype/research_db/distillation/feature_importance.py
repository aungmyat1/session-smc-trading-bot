"""
feature_importance.py
Ranks SMC features by statistical importance.
"""

import polars as pl


def compute_feature_importance(df: pl.DataFrame) -> pl.DataFrame:
    """Calculate correlation-style importance of each feature with result_r."""
    features = ["sweep", "has_ob", "has_fvg", "session", "pair", "direction"]

    importance = []
    for feat in features:
        # Simple proxy: groupby mean difference from overall mean
        overall_mean = df["result_r"].mean()
        grouped = df.group_by(feat).agg(pl.col("result_r").mean().alias("mean_r"))
        grouped = grouped.with_columns(
            ((pl.col("mean_r") - overall_mean).abs()).alias("importance")
        )
        score = grouped["importance"].mean()
        importance.append({"feature": feat, "importance_score": round(score, 4)})

    return pl.DataFrame(importance).sort("importance_score", descending=True)
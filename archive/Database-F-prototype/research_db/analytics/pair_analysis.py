"""
pair_analysis.py
Pair-by-pair performance analysis.
"""

from .metrics_engine import load_trades, pair_stats


def run_pair_analysis():
    print("=" * 60)
    print("Pair Performance Analysis")
    print("=" * 60)

    df = load_trades()
    stats = pair_stats(df)

    print(stats)
    return stats
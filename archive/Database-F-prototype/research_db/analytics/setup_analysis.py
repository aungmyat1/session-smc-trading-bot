"""
setup_analysis.py
Setup fingerprint analysis — the most powerful edge detector.
"""

from .metrics_engine import load_trades, setup_stats


def run_setup_analysis():
    print("=" * 60)
    print("Setup Fingerprint Analysis (Edge Discovery)")
    print("=" * 60)

    df = load_trades()
    stats = setup_stats(df)

    print(stats.head(15))
    print("\nTop 3 setups with highest expectancy:")
    print(stats.head(3))
    return stats

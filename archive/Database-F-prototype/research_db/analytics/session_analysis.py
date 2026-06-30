"""
session_analysis.py
Session performance analysis.
"""

from .metrics_engine import load_trades, session_stats


def run_session_analysis():
    print("=" * 60)
    print("Session Performance Analysis")
    print("=" * 60)

    df = load_trades()
    stats = session_stats(df)

    print(stats)
    print(f"\nBest session by avg R: {stats['session'][0]}")
    return stats

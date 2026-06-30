"""
edge_score.py
Calculates the single most important metric: Edge Score
"""

from .metrics_engine import load_trades, edge_score


def run_edge_score():
    print("=" * 60)
    print("Edge Score Calculation")
    print("=" * 60)

    df = load_trades()
    score = edge_score(df)

    print(f"System Edge Score: {score:.4f}")
    print("Higher = better risk-adjusted edge")

    return score

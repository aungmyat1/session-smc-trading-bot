"""
report_generator.py
Generates a comprehensive performance report.
"""

from .drawdown_analysis import run_drawdown_analysis
from .edge_score import run_edge_score
from .metrics_engine import (calculate_drawdown, edge_score, load_trades,
                             pair_stats, session_stats, setup_stats, win_rate)
from .pair_analysis import run_pair_analysis
from .session_analysis import run_session_analysis
from .setup_analysis import run_setup_analysis


def generate_full_report():
    print("\n" + "=" * 70)
    print("STAGE 5 — FULL ANALYTICS REPORT")
    print("=" * 70)

    df = load_trades()

    print(f"\nTotal Trades Analyzed: {len(df):,}")
    print(f"Overall Win Rate: {win_rate(df):.1f}%")
    print(f"Overall Edge Score: {edge_score(df):.4f}")

    print("\n" + "-" * 50)
    run_session_analysis()

    print("\n" + "-" * 50)
    run_pair_analysis()

    print("\n" + "-" * 50)
    run_setup_analysis()

    print("\n" + "-" * 50)
    run_drawdown_analysis()

    print("\n" + "-" * 50)
    run_edge_score()

    print("\n" + "=" * 70)
    print("Report Complete — Use insights to refine strategy")
    print("=" * 70)


if __name__ == "__main__":
    generate_full_report()

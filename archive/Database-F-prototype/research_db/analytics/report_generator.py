"""
report_generator.py
Generates a comprehensive performance report.
"""

from .metrics_engine import (
    load_trades,
    session_stats,
    pair_stats,
    setup_stats,
    win_rate,
    calculate_drawdown,
    edge_score,
)
from .session_analysis import run_session_analysis
from .pair_analysis import run_pair_analysis
from .setup_analysis import run_setup_analysis
from .drawdown_analysis import run_drawdown_analysis
from .edge_score import run_edge_score


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

"""
drawdown_analysis.py
Risk stability and drawdown analysis.
"""

from .metrics_engine import calculate_drawdown, load_trades


def run_drawdown_analysis():
    print("=" * 60)
    print("Risk & Drawdown Analysis")
    print("=" * 60)

    df = load_trades()
    max_dd = calculate_drawdown(df)

    print(f"Maximum Drawdown: {max_dd:.2f}R")
    print(f"Total R generated: {df['result_r'].sum():.2f}R")
    print(f"Number of trades: {len(df)}")

    return {"max_drawdown": max_dd}

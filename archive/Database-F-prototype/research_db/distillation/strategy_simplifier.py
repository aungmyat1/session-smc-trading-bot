"""
strategy_simplifier.py
Converts discovered patterns into simple, readable trading rules.
"""

import polars as pl

from .pattern_miner import load_trades, mine_patterns


def simplify_strategies(patterns: pl.DataFrame, top_n: int = 10) -> list:
    """Convert top patterns into human-readable IF-THEN rules."""
    rules = []

    for row in patterns.head(top_n).iter_rows(named=True):
        condition = []
        if row["sweep"]:
            condition.append("sweep=True")
        if row["has_ob"]:
            condition.append("OB=True")
        if row["has_fvg"]:
            condition.append("FVG=True")
        if row["session"] != "Any":
            condition.append(f"session={row['session']}")

        rule = f"IF {' AND '.join(condition)}: expected_edge = {row['expectancy']:.2f}R"
        rules.append(rule)

    return rules

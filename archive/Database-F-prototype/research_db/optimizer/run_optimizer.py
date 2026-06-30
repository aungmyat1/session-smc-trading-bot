#!/usr/bin/env python3
"""
run_optimizer.py
Main Stage 6 Strategy Optimizer runner.
"""

from pathlib import Path
import json
import polars as pl

from strategy_generator import generate_strategies
from performance_ranker import rank_strategies
from elimination_engine import eliminate_bad_strategies

TRADES_PATH = Path("research_db/trades/trades.parquet")
EXPERIMENTS_DIR = Path("research_db/experiments")


def load_trades():
    if not TRADES_PATH.exists():
        raise FileNotFoundError("Run Stage 4 first to generate trades.parquet")
    return pl.read_parquet(TRADES_PATH)


def main():
    print("=" * 70)
    print("STAGE 6 — STRATEGY OPTIMIZER")
    print("=" * 70)

    # 1. Generate strategy population
    strategies = generate_strategies()

    # 2. Load trades (from Stage 4)
    trades = load_trades()
    print(f"Loaded {len(trades):,} trades")

    # 3. For demonstration, assign random strategy_ids to trades
    # In real use, you would run the simulator per strategy
    trades = trades.with_columns(
        pl.col("signal_id").mod(len(strategies)).cast(pl.Utf8).alias("strategy_id")
    )

    # 4. Rank strategies
    ranking = rank_strategies(trades)
    print(f"\nTop 10 Strategies by Edge Score:")
    print(ranking.head(10))

    # 5. Eliminate weak strategies
    survivors = eliminate_bad_strategies(ranking)
    print(f"\nSurviving strategies after elimination: {len(survivors)}")

    # Save results
    ranking.write_parquet(EXPERIMENTS_DIR / "strategy_ranking.parquet")
    survivors.write_parquet(EXPERIMENTS_DIR / "surviving_strategies.parquet")

    print("\n✅ Strategy optimization complete.")
    print(f"Results saved in {EXPERIMENTS_DIR}")


if __name__ == "__main__":
    main()

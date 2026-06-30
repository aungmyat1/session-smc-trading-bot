#!/usr/bin/env python3
"""
tests/database_test.py
Validation tests for the Trading Research Database.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from datetime import date, datetime

from research_database.database import SessionLocal
from research_database.models import ReplayRun, Strategy, Trade
from sqlalchemy import create_engine, text


def test_connection():
    """Test 1: Database connection"""
    print("Test 1: Database Connection")
    try:
        db = SessionLocal()
        result = db.execute(text("SELECT version();"))
        version = result.scalar()
        print(f"  ✅ Connected to: {version}")
        db.close()
        return True
    except Exception as e:
        print(f"  ❌ Connection failed: {e}")
        return False


def test_insert_trade():
    """Test 2: Insert a test trade"""
    print("\nTest 2: Insert Test Trade")
    db = SessionLocal()
    try:
        # Create test strategy
        strategy = Strategy(
            strategy_name="ST-A2",
            version="v1",
            description="Test strategy",
            status="active",
        )
        db.add(strategy)
        db.commit()

        # Create replay run
        run = ReplayRun(
            run_id="TEST_RUN_001",
            strategy_id=strategy.id,
            symbol="EURUSD",
            start_date=date(2024, 6, 1),
            end_date=date(2024, 6, 30),
            data_source="parquet",
        )
        db.add(run)
        db.commit()

        # Create test trade
        trade = Trade(
            trade_id="T-TEST-001",
            run_id=run.run_id,
            strategy_id=strategy.id,
            symbol="EURUSD",
            direction="LONG",
            entry_time=datetime(2024, 6, 12, 9, 15),
            exit_time=datetime(2024, 6, 12, 10, 45),
            entry_price=1.0850,
            stop_price=1.0820,
            take_profit=1.0910,
            risk_reward=2.0,
            result_r=2.4,
            profit_loss=240.0,
            exit_reason="TP_HIT",
            session="London",
        )
        db.add(trade)
        db.commit()

        print(f"  ✅ Trade inserted: {trade.trade_id} (+{trade.result_r}R)")
        db.close()
        return True
    except Exception as e:
        print(f"  ❌ Insert failed: {e}")
        db.rollback()
        db.close()
        return False


def test_query_trades():
    """Test 3: Query trades"""
    print("\nTest 3: Query Trades")
    db = SessionLocal()
    try:
        trades = db.query(Trade).filter(Trade.result_r > 0).all()
        print(f"  ✅ Found {len(trades)} winning trades")
        db.close()
        return True
    except Exception as e:
        print(f"  ❌ Query failed: {e}")
        db.close()
        return False


def test_replay_run():
    """Test 4: Save and retrieve replay run"""
    print("\nTest 4: Replay Run Integration")
    db = SessionLocal()
    try:
        runs = db.query(ReplayRun).all()
        print(f"  ✅ Found {len(runs)} replay runs")
        db.close()
        return True
    except Exception as e:
        print(f"  ❌ Replay test failed: {e}")
        db.close()
        return False


def main():
    print("=" * 60)
    print("DATABASE VALIDATION TESTS")
    print("=" * 60)

    results = [
        test_connection(),
        test_insert_trade(),
        test_query_trades(),
        test_replay_run(),
    ]

    print("\n" + "=" * 60)
    if all(results):
        print("✅ ALL TESTS PASSED — Database is ready for historical replay")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 60)


if __name__ == "__main__":
    main()

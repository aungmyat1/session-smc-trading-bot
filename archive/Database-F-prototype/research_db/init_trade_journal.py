#!/usr/bin/env python3
"""
Stage 8 Infrastructure — Trade Journal Database (SQLite)
Creates the professional trade_journal.db with all recommended tables.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("research_db/trade_journal.db")


def create_connection():
    """Create SQLite connection with foreign keys enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def create_tables(conn: sqlite3.Connection):
    """Create all professional tables for the trade journal."""

    cursor = conn.cursor()

    # ====================== TRADES ======================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trades (
        trade_id TEXT PRIMARY KEY,
        strategy TEXT NOT NULL,
        pair TEXT NOT NULL,
        session TEXT,
        
        open_time TIMESTAMP NOT NULL,
        close_time TIMESTAMP,
        
        direction TEXT CHECK(direction IN ('LONG', 'SHORT')),
        
        entry_price REAL,
        stop_price REAL,
        take_profit REAL,
        
        risk_reward REAL,
        
        result_r REAL,
        pnl REAL,
        
        exit_reason TEXT,
        
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # ====================== SMC EVENTS ======================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS smc_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP NOT NULL,
        pair TEXT NOT NULL,
        timeframe TEXT,
        event_type TEXT NOT NULL,
        price REAL,
        
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # ====================== REPLAY RUNS ======================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS replay_runs (
        run_id TEXT PRIMARY KEY,
        strategy TEXT NOT NULL,
        
        start_date TEXT,
        end_date TEXT,
        
        trade_count INTEGER,
        win_rate REAL,
        profit_factor REAL,
        expectancy REAL,
        max_drawdown REAL,
        net_r REAL,
        
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # ====================== DAILY EQUITY ======================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS daily_equity (
        date TEXT PRIMARY KEY,
        starting_balance REAL,
        ending_balance REAL,
        drawdown REAL,
        daily_r REAL,
        
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # ====================== STRATEGY METRICS ======================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS strategy_metrics (
        strategy TEXT PRIMARY KEY,
        total_trades INTEGER,
        win_rate REAL,
        avg_r REAL,
        total_r REAL,
        max_drawdown REAL,
        profit_factor REAL,
        expectancy REAL,
        
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # ====================== INDEXES ======================
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_pair ON trades(pair);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_session ON trades(session);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_open_time ON trades(open_time);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_smc_events_pair_time ON smc_events(pair, timestamp);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_smc_events_type ON smc_events(event_type);")

    conn.commit()
    print("✅ All tables created successfully.")


def insert_sample_data(conn: sqlite3.Connection):
    """Insert some example data for testing."""
    cursor = conn.cursor()

    # Sample trades
    sample_trades = [
        ("T001", "London_Sweep_OB", "EURUSD", "London", "2024-06-12 09:15:00", "2024-06-12 10:45:00",
         "LONG", 1.0850, 1.0820, 1.0910, 2.0, 2.4, 240.0, "TP_HIT"),
        ("T002", "NY_Breakout", "GBPUSD", "NewYork", "2024-06-13 14:30:00", "2024-06-13 15:50:00",
         "SHORT", 1.2700, 1.2740, 1.2620, 2.0, -1.8, -180.0, "SL_HIT"),
    ]

    cursor.executemany("""
        INSERT OR IGNORE INTO trades 
        (trade_id, strategy, pair, session, open_time, close_time, direction, 
         entry_price, stop_price, take_profit, risk_reward, result_r, pnl, exit_reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, sample_trades)

    # Sample SMC events
    sample_events = [
        ("2024-06-12 09:10:00", "EURUSD", "M5", "BOS_BULL", 1.0842),
        ("2024-06-12 09:12:00", "EURUSD", "M5", "SWEEP", 1.0828),
        ("2024-06-12 09:14:00", "EURUSD", "M5", "FVG", 1.0835),
    ]

    cursor.executemany("""
        INSERT INTO smc_events (timestamp, pair, timeframe, event_type, price)
        VALUES (?, ?, ?, ?, ?)
    """, sample_events)

    conn.commit()
    print("✅ Sample data inserted.")


def main():
    print("=" * 60)
    print("Trade Journal Database Initializer")
    print("=" * 60)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = create_connection()
    create_tables(conn)

    # Uncomment the line below if you want sample data
    # insert_sample_data(conn)

    conn.close()
    print(f"\n✅ Database ready at: {DB_PATH}")


if __name__ == "__main__":
    main()
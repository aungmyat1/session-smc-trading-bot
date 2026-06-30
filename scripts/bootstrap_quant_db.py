#!/usr/bin/env python3
"""Bootstrap the quantitative research database.

This is the one-shot initializer for a clean PostgreSQL instance on the
research VPS. It:
  1. Applies `db/schema_v2.sql`
  2. Applies `db/schema_v3.sql`
  3. Seeds the core instruments and strategy rows
  4. Verifies that the main schemas are reachable

Usage:
    python3 scripts/bootstrap_quant_db.py
    python3 scripts/bootstrap_quant_db.py --database-url postgresql://...
    python3 scripts/bootstrap_quant_db.py --dry-run

The script is safe to re-run. All seed inserts use ON CONFLICT DO NOTHING.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from db.runtime import resolve_database_url

SCHEMA_PATHS = [
    ROOT / "db" / "schema_v2.sql",
    ROOT / "db" / "schema_v3.sql",
]

DEFAULT_DATABASE_URL = resolve_database_url()

INSTRUMENTS = [
    ("EURUSD", "fx", "EURUSD", "EUR", "USD", 0.0001),
    ("GBPUSD", "fx", "GBPUSD", "GBP", "USD", 0.0001),
    ("USDJPY", "fx", "USDJPY", "USD", "JPY", 0.01),
    ("XAUUSD", "metal", "XAUUSD", "XAU", "USD", 0.01),
]

STRATEGIES = [
    (
        "ST-A2",
        "1.0",
        "Session Liquidity Reversal: HTF bias + session sweep + displacement + FVG",
        "active",
    ),
    (
        "ST-D2-E3-OPT2",
        "1.0",
        "D2 E3 research branch: PDH/PDL sweep + MSS + pullback limit",
        "research",
    ),
]


def _read_schemas() -> list[tuple[Path, str]]:
    payloads: list[tuple[Path, str]] = []
    for path in SCHEMA_PATHS:
        if not path.exists():
            raise FileNotFoundError(f"missing schema file: {path}")
        payloads.append((path, path.read_text(encoding="utf-8")))
    return payloads


def _apply_schema(conn) -> None:
    with conn.cursor() as cur:
        for _path, schema_sql in _read_schemas():
            cur.execute(schema_sql)


def _seed(conn) -> None:
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO market.instruments
                (symbol, asset_type, broker_symbol, base_currency, quote_currency, pip_size)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (symbol) DO NOTHING
            """,
            INSTRUMENTS,
        )
        cur.executemany(
            """
            INSERT INTO research.strategies
                (strategy_name, version, description, status)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (strategy_name, version) DO NOTHING
            """,
            STRATEGIES,
        )


def _verify(conn) -> dict[str, int]:
    checks = {}
    with conn.cursor() as cur:
        for label, table in [
            ("market_instruments", "market.instruments"),
            ("research_strategies", "research.strategies"),
            ("research_runs", "research.replay_runs"),
            ("research_trades", "research.trades"),
            ("analytics_metrics", "analytics.strategy_metrics"),
            ("strategy_entities", "strategy.strategy"),
            ("governance_stage_state", "governance.stage_state"),
            ("evidence_artifacts", "evidence.artifact"),
        ]:
            schema_name, table_name = table.split(".", 1)
            cur.execute(
                sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
                    sql.Identifier(schema_name),
                    sql.Identifier(table_name),
                )
            )
            checks[label] = int(cur.fetchone()[0])
    return checks


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap quant research DB")
    parser.add_argument("--database-url", default=DEFAULT_DATABASE_URL)
    parser.add_argument("--dry-run", action="store_true", help="Parse schema only, do not execute SQL")
    args = parser.parse_args()

    if args.dry_run:
        for path in SCHEMA_PATHS:
            print(f"Schema file: {path}")
        print("Dry run requested; no database changes made.")
        return

    if not args.database_url:
        raise SystemExit(
            "DATABASE_URL is required for bootstrap_quant_db; set it explicitly or pass --database-url"
        )

    conn = psycopg2.connect(args.database_url)
    conn.autocommit = False
    try:
        _apply_schema(conn)
        _seed(conn)
        conn.commit()
        checks = _verify(conn)
        print("✅ Quant research database bootstrapped.")
        for name, count in checks.items():
            print(f"  {name}: {count}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()

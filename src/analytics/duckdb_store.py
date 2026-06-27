from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd


@dataclass
class DuckDBStore:
    path: Path

    def connect(self) -> duckdb.DuckDBPyConnection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        return duckdb.connect(str(self.path))

    def create_tables(self, tables: dict[str, pd.DataFrame]) -> None:
        with self.connect() as conn:
            for name, frame in tables.items():
                conn.register(f"tmp_{name}", frame)
                conn.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM tmp_{name}")
                conn.unregister(f"tmp_{name}")

    def register_parquet(self, table: str, path: str | Path) -> None:
        with self.connect() as conn:
            conn.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_parquet(?)", [str(path)])

    def query(self, sql: str, params: list[Any] | None = None) -> pd.DataFrame:
        with self.connect() as conn:
            return conn.execute(sql, params or []).fetchdf()


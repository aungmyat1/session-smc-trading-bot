from __future__ import annotations

import argparse
from pathlib import Path

from src.research_feature_database import FeatureDatabasePaths, build_feature_database
from shared.configuration.symbols import enabled_symbols


def _discover_default_symbols(raw_root: Path, processed_root: Path) -> list[str]:
    symbols: set[str] = set()
    if raw_root.exists():
        for path in raw_root.glob("**/*M1*.csv"):
            name = path.name.upper()
            for candidate in enabled_symbols("research"):
                if candidate in name:
                    symbols.add(candidate)
    if processed_root.exists():
        for sym_dir in processed_root.iterdir():
            if sym_dir.is_dir():
                symbols.add(sym_dir.name.upper())
    if not symbols:
        symbols.update(enabled_symbols("research"))
    return sorted(symbols)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the M1 research feature database")
    parser.add_argument("--symbols", nargs="+", default=None, help="Research symbols to include, e.g. EURUSD GBPUSD XAUUSD BTCUSDT")
    parser.add_argument("--swing-lookback", type=int, default=5, help="Centered swing lookback on each side")
    parser.add_argument("--raw-root", default="data/raw", help="Input raw data root")
    parser.add_argument("--processed-root", default="data/processed", help="Fallback processed data root")
    parser.add_argument("--output-root", default="research_db", help="Output research database root")
    args = parser.parse_args()

    paths = FeatureDatabasePaths(
        raw_root=Path(args.raw_root),
        processed_root=Path(args.processed_root),
        output_root=Path(args.output_root),
    )
    symbols = args.symbols or _discover_default_symbols(paths.raw_root, paths.processed_root)
    outputs = build_feature_database(symbols, paths=paths, swing_lookback=args.swing_lookback)

    print("Built feature database")
    for name, frame in outputs.items():
        print(f"  {name}: {len(frame):,} rows")
    print(f"Parquet: {paths.parquet_path}")
    print(f"DuckDB:  {paths.duckdb_path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest.simulator import TradeSimulationConfig
from src.pipeline import ResearchEngine, ResearchPaths
from src.signals.generator import SignalConfig
from src.signals.london_breakout import LondonBreakoutConfig
from src.signals.ny_momentum import NYMomentumConfig
from src.signals.vwap_mean_reversion import VWAPMeanReversionConfig


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the research-engine feature stack")
    parser.add_argument("--symbol", action="append", dest="symbols", help="Symbol to process (repeatable)")
    parser.add_argument("--timeframe", default="M1")
    parser.add_argument("--config", default="config/research_engine.yaml")
    args = parser.parse_args()

    cfg = _load_yaml(Path(args.config))
    raw_root = Path(cfg.get("data", {}).get("raw_root", "data/raw"))
    parquet_root = Path(cfg.get("data", {}).get("parquet_root", "data"))
    duckdb_path = Path(cfg.get("analytics", {}).get("duckdb_path", "research.db"))
    symbols = args.symbols or cfg.get("data", {}).get("symbols", ["EURUSD", "GBPUSD", "XAUUSD"])

    signal_cfg = SignalConfig(**cfg.get("signals", {}))
    trade_cfg = TradeSimulationConfig(**cfg.get("risk", {}))
    breakout_cfg = LondonBreakoutConfig(**cfg.get("breakout", {}))
    ny_cfg = NYMomentumConfig(**cfg.get("ny", {}))
    vwap_cfg = VWAPMeanReversionConfig(**cfg.get("vwap", {}))
    engine = ResearchEngine(ResearchPaths(raw_root=raw_root, parquet_root=parquet_root, duckdb_path=duckdb_path),
                            signal_config=signal_cfg,
                            trade_config=trade_cfg,
                            breakout_config=breakout_cfg,
                            ny_config=ny_cfg,
                            vwap_config=vwap_cfg)

    for symbol in symbols:
        try:
            result = engine.build_symbol(symbol, timeframe=args.timeframe)
        except FileNotFoundError as exc:
            print(f"{symbol}: skipped ({exc})")
            continue
        print(f"{symbol}: candles={len(result['candles'])} signals={len(result['signals'])} trades={len(result['trades'])}")

    q = engine.queries()
    print("performance_by_pair")
    print(q.performance_by_pair())
    print("performance_by_strategy")
    print(q.performance_by_strategy())


if __name__ == "__main__":
    main()

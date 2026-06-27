from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.analytics.duckdb_store import DuckDBStore
from src.analytics.queries import ResearchQueries
from src.backtest.simulator import TradeSimulator, TradeSimulationConfig
from src.data.loader import load_symbol_history
from src.data.parquet_store import save_parquet
from src.data.validator import validate_candles
from src.features.fvg import detect_fvg
from src.features.liquidity import detect_liquidity_sweeps
from src.features.order_blocks import detect_order_blocks
from src.features.sessions import label_sessions
from src.features.structure import build_structure
from src.features.swings import detect_swings
from src.signals.generator import SignalGenerator, SignalConfig
from src.signals.london_breakout import LondonBreakoutConfig, generate_london_breakout_signals
from src.signals.ny_momentum import NYMomentumConfig, generate_ny_momentum_signals
from src.signals.vwap_mean_reversion import VWAPMeanReversionConfig, generate_vwap_mean_reversion_signals


@dataclass
class ResearchPaths:
    raw_root: Path
    parquet_root: Path
    duckdb_path: Path


class ResearchEngine:
    """End-to-end research pipeline for SMC-style feature engineering."""

    def __init__(
        self,
        paths: ResearchPaths,
        signal_config: SignalConfig | None = None,
        trade_config: TradeSimulationConfig | None = None,
        breakout_config: LondonBreakoutConfig | None = None,
        ny_config: NYMomentumConfig | None = None,
        vwap_config: VWAPMeanReversionConfig | None = None,
    ) -> None:
        self.paths = paths
        self.signal_generator = SignalGenerator(signal_config)
        self.trade_simulator = TradeSimulator(trade_config)
        self.breakout_config = breakout_config or LondonBreakoutConfig()
        self.ny_config = ny_config or NYMomentumConfig()
        self.vwap_config = vwap_config or VWAPMeanReversionConfig()
        self.store = DuckDBStore(paths.duckdb_path)

    def build_symbol(self, symbol: str, timeframe: str = "M1") -> dict[str, pd.DataFrame]:
        loaded = load_symbol_history(symbol, self.paths.raw_root, timeframe=timeframe, validate=False)
        report = validate_candles(loaded.frame, expected_freq=self._freq_for_timeframe(loaded.timeframe))
        if not report.ok:
            raise ValueError(f"{symbol} validation failed: {report.errors}")

        candles = loaded.frame.copy()
        candles["pair"] = symbol

        sessions = label_sessions(candles, pair=symbol)
        swings = detect_swings(candles, pair=symbol)
        structure = build_structure(candles, swings, pair=symbol)
        liquidity = detect_liquidity_sweeps(candles, pair=symbol)
        fvg = detect_fvg(candles, pair=symbol)
        order_blocks = detect_order_blocks(candles, structure, pair=symbol)
        smc_signals = self.signal_generator.generate(candles, sessions, structure, liquidity, fvg, order_blocks)
        breakout_signals = generate_london_breakout_signals(candles, pair=symbol, config=self.breakout_config)
        ny_signals = generate_ny_momentum_signals(candles, pair=symbol, config=self.ny_config)
        vwap_signals = generate_vwap_mean_reversion_signals(candles, pair=symbol, config=self.vwap_config)
        signals = pd.concat([smc_signals, breakout_signals, ny_signals, vwap_signals], ignore_index=True, sort=False)
        if not signals.empty:
            signals = signals.drop_duplicates(subset=["pair", "timestamp", "strategy_name", "direction"], keep="first")
            signals = signals.sort_values(["pair", "timestamp", "strategy_name"]).reset_index(drop=True)
        trades = self.trade_simulator.simulate(candles, signals)

        out_dir = self.paths.parquet_root / symbol
        out_dir.mkdir(parents=True, exist_ok=True)
        save_parquet(candles, out_dir / "candles.parquet")
        save_parquet(sessions, out_dir / "sessions.parquet")
        save_parquet(swings, out_dir / "swings.parquet")
        save_parquet(structure, out_dir / "structure.parquet")
        save_parquet(liquidity, out_dir / "liquidity.parquet")
        save_parquet(fvg, out_dir / "fvg.parquet")
        save_parquet(order_blocks, out_dir / "order_blocks.parquet")
        save_parquet(signals, out_dir / "signals.parquet")
        save_parquet(trades, out_dir / "trades.parquet")

        self.store.create_tables({
            "candles": candles,
            "sessions": sessions,
            "swings": swings,
            "structure": structure,
            "liquidity": liquidity,
            "fvg": fvg,
            "order_blocks": order_blocks,
            "signals": signals,
            "trades": trades,
        })

        return {
            "candles": candles,
            "sessions": sessions,
            "swings": swings,
            "structure": structure,
            "liquidity": liquidity,
            "fvg": fvg,
            "order_blocks": order_blocks,
            "signals": signals,
            "trades": trades,
        }

    def queries(self) -> ResearchQueries:
        return ResearchQueries(self.store)

    @staticmethod
    def _freq_for_timeframe(timeframe: str) -> str:
        tf = timeframe.upper().strip()
        if tf.startswith("M"):
            return f"{tf[1:]}min"
        if tf.startswith("H"):
            return f"{tf[1:]}h"
        if tf.startswith("D"):
            return f"{tf[1:]}d"
        return "1min"

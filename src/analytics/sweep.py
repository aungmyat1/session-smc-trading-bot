from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from src.backtest.simulator import TradeSimulationConfig
from src.pipeline import ResearchEngine, ResearchPaths
from src.signals.generator import SignalConfig
from src.signals.london_breakout import LondonBreakoutConfig
from src.signals.ny_momentum import NYMomentumConfig
from src.signals.vwap_mean_reversion import VWAPMeanReversionConfig


@dataclass(frozen=True)
class SweepCandidate:
    name: str
    signal: dict[str, Any] = field(default_factory=dict)
    breakout: dict[str, Any] = field(default_factory=dict)
    ny: dict[str, Any] = field(default_factory=dict)
    vwap: dict[str, Any] = field(default_factory=dict)
    risk: dict[str, Any] = field(default_factory=dict)


def run_parameter_sweep(
    raw_root: str | Path,
    symbol: str,
    candidates: list[SweepCandidate],
    parquet_root: str | Path = "research_sweep",
    duckdb_path: str | Path = "research_sweep.db",
) -> pd.DataFrame:
    """Run a small strategy-parameter sweep and summarize trade expectancy."""
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        engine = ResearchEngine(
            ResearchPaths(raw_root=Path(raw_root), parquet_root=Path(parquet_root) / candidate.name, duckdb_path=Path(duckdb_path)),
            signal_config=SignalConfig(**candidate.signal),
            trade_config=TradeSimulationConfig(**candidate.risk),
            breakout_config=LondonBreakoutConfig(**candidate.breakout),
            ny_config=NYMomentumConfig(**candidate.ny),
            vwap_config=VWAPMeanReversionConfig(**candidate.vwap),
        )
        result = engine.build_symbol(symbol)
        trades = result["trades"]
        if trades.empty:
            rows.append({
                "candidate": candidate.name,
                "symbol": symbol,
                "n_trades": 0,
                "win_rate": 0.0,
                "avg_r": 0.0,
                "expectancy": 0.0,
                "profit_factor": 0.0,
            })
            continue

        wins = trades[trades["result_r"] > 0]
        losses = trades[trades["result_r"] <= 0]
        gross_win = float(wins["result_r"].sum())
        gross_loss = float(abs(losses["result_r"].sum()))
        profit_factor = gross_win / gross_loss if gross_loss > 0 else float("inf")
        rows.append({
            "candidate": candidate.name,
            "symbol": symbol,
            "n_trades": int(len(trades)),
            "win_rate": round(float((trades["result_r"] > 0).mean()), 4),
            "avg_r": round(float(trades["result_r"].mean()), 4),
            "expectancy": round(float(trades["result_r"].mean()), 4),
            "profit_factor": round(float(profit_factor), 4) if profit_factor != float("inf") else profit_factor,
        })

    return pd.DataFrame.from_records(rows)

from __future__ import annotations

import pandas as pd

from src.backtest.simulator import TradeSimulationConfig, TradeSimulator
from src.features.fvg import detect_fvg
from src.features.liquidity import detect_liquidity_sweeps
from src.features.order_blocks import detect_order_blocks
from src.features.sessions import label_sessions
from src.features.structure import build_structure
from src.features.swings import detect_swings
from src.signals.generator import SignalGenerator
from src.signals.london_breakout import (
    LondonBreakoutConfig,
    generate_london_breakout_signals,
)
from src.signals.ny_momentum import NYMomentumConfig, generate_ny_momentum_signals
from src.signals.vwap_mean_reversion import (
    VWAPMeanReversionConfig,
    generate_vwap_mean_reversion_signals,
)


def _candles() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2024-01-01T08:00:00Z",
                    "2024-01-01T08:01:00Z",
                    "2024-01-01T08:02:00Z",
                    "2024-01-01T08:03:00Z",
                    "2024-01-01T08:04:00Z",
                    "2024-01-01T08:05:00Z",
                ],
                utc=True,
            ),
            "pair": ["EURUSD"] * 6,
            "open": [1.0, 1.0, 1.01, 1.02, 1.03, 1.04],
            "high": [1.01, 1.02, 1.05, 1.06, 1.07, 1.08],
            "low": [0.99, 0.97, 1.00, 1.01, 1.02, 1.03],
            "close": [1.0, 1.015, 1.035, 1.045, 1.055, 1.065],
            "volume": [100] * 6,
            "spread": [1.0] * 6,
        }
    )


def test_signal_generator_produces_opportunity():
    candles = _candles()
    sessions = label_sessions(candles, pair="EURUSD")
    swings = detect_swings(candles, pair="EURUSD")
    structure = build_structure(candles, swings, pair="EURUSD")
    liquidity = detect_liquidity_sweeps(candles, pair="EURUSD")
    fvg = detect_fvg(candles, pair="EURUSD")
    ob = detect_order_blocks(candles, structure, pair="EURUSD")
    signals = SignalGenerator().generate(
        candles, sessions, structure, liquidity, fvg, ob
    )
    assert not signals.empty
    assert set(
        [
            "signal_id",
            "timestamp",
            "pair",
            "session",
            "direction",
            "strategy_name",
            "entry_price",
        ]
    ).issubset(signals.columns)


def test_trade_simulator_executes_trades():
    candles = _candles()
    sessions = label_sessions(candles, pair="EURUSD")
    swings = detect_swings(candles, pair="EURUSD")
    structure = build_structure(candles, swings, pair="EURUSD")
    liquidity = detect_liquidity_sweeps(candles, pair="EURUSD")
    fvg = detect_fvg(candles, pair="EURUSD")
    ob = detect_order_blocks(candles, structure, pair="EURUSD")
    signals = SignalGenerator().generate(
        candles, sessions, structure, liquidity, fvg, ob
    )
    trades = TradeSimulator(TradeSimulationConfig(rr_multiple=1.5)).simulate(
        candles, signals
    )
    assert not trades.empty
    assert set(
        ["trade_id", "signal_id", "pair", "strategy_name", "result_r", "result_money"]
    ).issubset(trades.columns)


def test_london_breakout_generator_produces_signal():
    candles = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2024-01-02T00:00:00Z",
                    "2024-01-02T00:15:00Z",
                    "2024-01-02T00:30:00Z",
                    "2024-01-02T00:45:00Z",
                    "2024-01-02T01:00:00Z",
                    "2024-01-02T08:00:00Z",
                    "2024-01-02T08:15:00Z",
                    "2024-01-02T08:30:00Z",
                ],
                utc=True,
            ),
            "pair": ["EURUSD"] * 8,
            "open": [1.0, 1.0, 1.0, 1.0, 1.0, 1.021, 1.022, 1.024],
            "high": [1.01, 1.01, 1.01, 1.01, 1.02, 1.03, 1.029, 1.033],
            "low": [0.99, 0.99, 0.99, 0.99, 0.985, 1.01997, 1.01996, 1.021],
            "close": [1.0, 1.0, 1.0, 1.0, 1.01, 1.025, 1.024, 1.03],
            "volume": [100] * 8,
            "spread": [1.0] * 8,
        }
    )
    signals = generate_london_breakout_signals(
        candles,
        pair="EURUSD",
        config=LondonBreakoutConfig(
            min_asian_range_pips=5.0, max_asian_range_pips=500.0
        ),
    )
    assert not signals.empty
    assert signals.iloc[0]["strategy_name"] == "LondonBreakout"


def test_disabled_vwap_generator_returns_empty():
    candles = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2024-01-02T08:00:00Z", "2024-01-02T08:15:00Z"], utc=True
            ),
            "pair": ["EURUSD", "EURUSD"],
            "open": [1.0, 1.0],
            "high": [1.01, 1.01],
            "low": [0.99, 0.99],
            "close": [1.0, 1.0],
            "volume": [1000, 1000],
            "spread": [1.0, 1.0],
        }
    )
    signals = generate_vwap_mean_reversion_signals(
        candles,
        pair="EURUSD",
        config=VWAPMeanReversionConfig(enabled=False),
    )
    assert signals.empty


def test_ny_momentum_generator_produces_signal():
    candles = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2024-01-02T08:00:00Z",
                    "2024-01-02T08:15:00Z",
                    "2024-01-02T08:30:00Z",
                    "2024-01-02T08:45:00Z",
                    "2024-01-02T09:00:00Z",
                    "2024-01-02T13:00:00Z",
                    "2024-01-02T13:15:00Z",
                    "2024-01-02T13:30:00Z",
                ],
                utc=True,
            ),
            "pair": ["EURUSD"] * 8,
            "open": [1.1000, 1.1001, 1.1000, 1.1001, 1.1000, 1.1060, 1.1012, 1.1010],
            "high": [1.1008, 1.1008, 1.1009, 1.1010, 1.1008, 1.1115, 1.1014, 1.1013],
            "low": [1.0992, 1.0993, 1.0992, 1.0994, 1.0993, 1.1058, 1.1007, 1.1005],
            "close": [1.1000, 1.1001, 1.1000, 1.1001, 1.1000, 1.1110, 1.1010, 1.1011],
            "volume": [1000] * 8,
            "spread": [1.0] * 8,
        }
    )
    signals = generate_ny_momentum_signals(
        candles,
        pair="EURUSD",
        config=NYMomentumConfig(enabled=True, max_signals_per_day=1),
    )
    assert not signals.empty
    assert signals.iloc[0]["strategy_name"] == "NYMomentum"


def test_disabled_ny_momentum_generator_returns_empty():
    candles = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2024-01-02T08:00:00Z", "2024-01-02T13:00:00Z"], utc=True
            ),
            "pair": ["EURUSD", "EURUSD"],
            "open": [1.0, 1.0],
            "high": [1.01, 1.02],
            "low": [0.99, 0.98],
            "close": [1.0, 1.01],
            "volume": [1000, 1000],
            "spread": [1.0, 1.0],
        }
    )
    signals = generate_ny_momentum_signals(
        candles,
        pair="EURUSD",
        config=NYMomentumConfig(enabled=False),
    )
    assert signals.empty


def test_vwap_mean_reversion_generator_produces_signal():
    candles = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2024-01-02T08:00:00Z",
                    "2024-01-02T08:15:00Z",
                    "2024-01-02T08:30:00Z",
                    "2024-01-02T08:45:00Z",
                    "2024-01-02T09:00:00Z",
                    "2024-01-02T09:15:00Z",
                    "2024-01-02T09:30:00Z",
                    "2024-01-02T09:45:00Z",
                    "2024-01-02T10:00:00Z",
                    "2024-01-02T10:15:00Z",
                    "2024-01-02T10:30:00Z",
                    "2024-01-02T10:45:00Z",
                ],
                utc=True,
            ),
            "pair": ["EURUSD"] * 12,
            "open": [
                1.1000,
                1.1001,
                1.1002,
                1.1001,
                1.1000,
                1.1002,
                1.1001,
                1.1000,
                1.1001,
                1.1000,
                1.0996,
                1.0959,
            ],
            "high": [
                1.1008,
                1.1008,
                1.1009,
                1.1009,
                1.1008,
                1.1009,
                1.1008,
                1.1009,
                1.1008,
                1.1008,
                1.1001,
                1.0992,
            ],
            "low": [
                1.0992,
                1.0993,
                1.0992,
                1.0994,
                1.0993,
                1.0992,
                1.0994,
                1.0993,
                1.0992,
                1.0994,
                1.0954,
                1.0946,
            ],
            "close": [
                1.1000,
                1.1001,
                1.1000,
                1.1001,
                1.1000,
                1.1001,
                1.1000,
                1.1001,
                1.1000,
                1.1001,
                1.0958,
                1.0976,
            ],
            "volume": [1000] * 12,
            "spread": [1.0] * 12,
        }
    )
    signals = generate_vwap_mean_reversion_signals(
        candles,
        pair="EURUSD",
        config=VWAPMeanReversionConfig(
            min_bars=8,
            min_session_bars=8,
            sweep_buffer_mult=0.0,
            extreme_atr_mult=0.1,
            reclaim_atr_mult=0.1,
            tp_rr=1.2,
            max_signals_per_day=1,
        ),
    )
    assert not signals.empty
    assert signals.iloc[0]["strategy_name"] == "VWAPMeanReversion"

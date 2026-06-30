from __future__ import annotations

import pandas as pd

from src.features.fvg import detect_fvg
from src.features.liquidity import detect_liquidity_sweeps
from src.features.order_blocks import detect_order_blocks
from src.features.sessions import label_sessions
from src.features.structure import build_structure
from src.features.swings import detect_swings


def _candles() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2024-01-01T07:00:00Z",
                    "2024-01-01T07:01:00Z",
                    "2024-01-01T07:02:00Z",
                    "2024-01-01T07:03:00Z",
                    "2024-01-01T07:04:00Z",
                ],
                utc=True,
            ),
            "pair": ["EURUSD"] * 5,
            "open": [1.0, 1.0, 1.01, 1.02, 1.03],
            "high": [1.01, 1.02, 1.04, 1.03, 1.05],
            "low": [0.99, 0.98, 1.0, 1.01, 1.02],
            "close": [1.0, 1.01, 1.03, 1.02, 1.04],
            "volume": [100] * 5,
            "spread": [1.0] * 5,
        }
    )


def test_sessions_labeling():
    out = label_sessions(_candles(), pair="EURUSD")
    assert out["session"].tolist()[0] == "asian"
    assert out["session"].tolist()[-1] == "asian"


def test_swings_detect_local_extrema():
    candles = _candles()
    candles.loc[2, "high"] = 1.10
    candles.loc[2, "low"] = 0.90
    swings = detect_swings(candles, pair="EURUSD")
    assert not swings.empty
    assert {"swing_high", "swing_low"} & set(swings["swing_type"])


def test_liquidity_sweep_detection():
    candles = _candles()
    candles.loc[1, "low"] = 0.97
    candles.loc[1, "close"] = 0.995
    sweeps = detect_liquidity_sweeps(candles, pair="EURUSD")
    assert not sweeps.empty
    assert sweeps.iloc[0]["sweep_type"] in {"bullish", "bearish"}


def test_fvg_detection():
    candles = _candles()
    candles.loc[2, "low"] = 1.03
    fvgs = detect_fvg(candles, pair="EURUSD")
    assert not fvgs.empty
    assert fvgs.iloc[0]["direction"] == "bullish"


def test_structure_and_order_blocks():
    candles = _candles()
    candles.loc[2, "high"] = 1.10
    candles.loc[2, "close"] = 1.11
    candles.loc[1, "close"] = 0.99
    swings = detect_swings(candles, pair="EURUSD")
    structure = build_structure(candles, swings, pair="EURUSD")
    assert not structure.empty
    assert {"HH", "HL", "BOS", "CHOCH"} & set(structure["structure"])
    order_blocks = detect_order_blocks(candles, structure, pair="EURUSD")
    assert isinstance(order_blocks, pd.DataFrame)
